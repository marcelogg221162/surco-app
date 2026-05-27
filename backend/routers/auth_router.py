from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sii.auth import get_sii_token, load_certificate

router = APIRouter()


class TokenResponse(BaseModel):
    token: str
    mensaje: str = "Token obtenido correctamente"


@router.get("/token", response_model=TokenResponse)
async def obtener_token(force_refresh: bool = False):
    """
    Obtiene (o renueva) el token SII usando el certificado digital configurado.
    Pasar ?force_refresh=true para forzar un nuevo ciclo semilla → firma → token.
    """
    try:
        token = await get_sii_token(force_refresh=force_refresh)
        return TokenResponse(token=token)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Certificado no encontrado: {e}. Revisa CERT_PATH en .env",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/certificado/info")
async def info_certificado():
    """Retorna información pública del certificado cargado (sin exponer la clave privada)."""
    try:
        _, certificate = load_certificate()
        subject = certificate.subject.rfc4514_string()
        not_after = certificate.not_valid_after_utc.isoformat()
        return {
            "subject": subject,
            "valido_hasta": not_after,
            "numero_serie": str(certificate.serial_number),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
