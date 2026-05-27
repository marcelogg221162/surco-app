"""
Autenticación con el SII de Chile mediante Certificado Digital.

Flujo:
  1. Obtener semilla (seed) desde SII → GET /cgi_dte/UF/GetSeed.cgi
  2. Firmar la semilla con la clave privada del certificado
  3. Enviar la semilla firmada → POST /cgi_dte/UF/GetTokenFromSeed.cgi
  4. Extraer el token de la respuesta XML
  5. Cachear el token (~60 min de validez)
"""

import base64
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree

from .config import get_settings

logger = logging.getLogger(__name__)

# Cache simple en memoria: (token, expira_en_timestamp)
_token_cache: tuple[str, float] | None = None
TOKEN_TTL_SECONDS = 55 * 60  # 55 min (SII renueva cada 60 min)


# ── Carga del certificado ──────────────────────────────────────────────────────

def _load_private_key_from_pfx(pfx_path: str, password: str):
    """Carga clave privada y certificado desde un archivo .pfx (PKCS#12)."""
    data = Path(pfx_path).read_bytes()
    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        data,
        password.encode() if password else None,
    )
    return private_key, certificate


def _load_private_key_from_pem(key_path: str, cert_path: str):
    """Carga clave privada y certificado desde archivos .pem separados."""
    key_data = Path(key_path).read_bytes()
    cert_data = Path(cert_path).read_bytes()

    private_key = serialization.load_pem_private_key(key_data, password=None)
    from cryptography import x509
    certificate = x509.load_pem_x509_certificate(cert_data)
    return private_key, certificate


def load_certificate():
    """
    Devuelve (private_key, certificate) usando la configuración del .env.
    Soporta .pfx o par de .pem.
    """
    settings = get_settings()

    if settings.cert_pem_path and settings.key_pem_path:
        return _load_private_key_from_pem(settings.key_pem_path, settings.cert_pem_path)

    return _load_private_key_from_pfx(settings.cert_path, settings.cert_password)


# ── Paso 1: Obtener semilla ────────────────────────────────────────────────────

async def _get_seed() -> str:
    """Solicita una semilla al SII. Retorna el valor de <SEMILLA>."""
    settings = get_settings()
    url = f"{settings.sii_base_url}/cgi_dte/UF/GetSeed.cgi"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    root = etree.fromstring(resp.content)
    semilla = root.findtext(".//SEMILLA")
    if not semilla:
        raise ValueError(f"No se encontró SEMILLA en la respuesta SII: {resp.text}")

    logger.debug("Semilla obtenida: %s", semilla)
    return semilla


# ── Paso 2: Firmar la semilla ──────────────────────────────────────────────────

def _build_signed_seed_xml(semilla: str, private_key, certificate) -> bytes:
    """
    Construye el XML con la semilla firmada según el esquema del SII.

    Estructura esperada por SII:
      <getToken>
        <item>
          <Semilla>VALOR</Semilla>
        </item>
        <Signature>...</Signature>  ← firma XMLDSig
      </getToken>
    """
    # 1. XML canónico del elemento a firmar
    seed_xml = (
        f'<item><Semilla>{semilla}</Semilla></item>'
    ).encode()

    # 2. Digest SHA1 del elemento (SII usa SHA1 en su esquema legacy)
    digest = hashes.Hash(hashes.SHA1())
    digest.update(seed_xml)
    digest_value = base64.b64encode(digest.finalize()).decode()

    # 3. SignedInfo (lo que realmente se firma)
    signed_info = (
        '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        '<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
        '<Reference URI="">'
        '<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
        f'<DigestValue>{digest_value}</DigestValue>'
        '</Reference>'
        '</SignedInfo>'
    ).encode()

    # 4. Firma RSA-SHA1
    signature_bytes = private_key.sign(signed_info, padding.PKCS1v15(), hashes.SHA1())
    signature_value = base64.b64encode(signature_bytes).decode()

    # 5. Certificado público en base64
    cert_der = certificate.public_bytes(serialization.Encoding.DER)
    cert_b64 = base64.b64encode(cert_der).decode()

    # 6. XML final
    xml = (
        '<getToken>'
        f'<item><Semilla>{semilla}</Semilla></item>'
        '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
        f'{signed_info.decode()}'
        f'<SignatureValue>{signature_value}</SignatureValue>'
        '<KeyInfo>'
        '<KeyValue/>'
        '<X509Data>'
        f'<X509Certificate>{cert_b64}</X509Certificate>'
        '</X509Data>'
        '</KeyInfo>'
        '</Signature>'
        '</getToken>'
    )
    return xml.encode()


# ── Paso 3: Obtener token ──────────────────────────────────────────────────────

async def _request_token(signed_xml: bytes) -> str:
    """Envía el XML firmado al SII y extrae el token de la respuesta."""
    settings = get_settings()
    url = f"{settings.sii_base_url}/cgi_dte/UF/GetTokenFromSeed.cgi"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            url,
            content=signed_xml,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()

    root = etree.fromstring(resp.content)
    estado = root.findtext(".//ESTADO")
    token = root.findtext(".//TOKEN")

    if estado != "00" or not token:
        glosa = root.findtext(".//GLOSA", "sin descripción")
        raise RuntimeError(f"SII rechazó la autenticación [{estado}]: {glosa}")

    logger.info("Token SII obtenido correctamente")
    return token


# ── API pública ────────────────────────────────────────────────────────────────

async def get_sii_token(force_refresh: bool = False) -> str:
    """
    Devuelve un token SII válido.
    Usa caché en memoria; renueva automáticamente si está por expirar.
    """
    global _token_cache

    now = time.monotonic()
    if not force_refresh and _token_cache:
        token, expires_at = _token_cache
        if now < expires_at:
            return token

    private_key, certificate = load_certificate()
    semilla = await _get_seed()
    signed_xml = _build_signed_seed_xml(semilla, private_key, certificate)
    token = await _request_token(signed_xml)

    _token_cache = (token, now + TOKEN_TTL_SECONDS)
    return token
