from pydantic_settings import BaseSettings
from functools import lru_cache


class SIISettings(BaseSettings):
    # Certificado
    cert_path: str = "certs/empresa.pfx"
    cert_password: str = ""
    cert_pem_path: str = ""
    key_pem_path: str = ""

    # Empresa
    empresa_rut: str = ""
    empresa_razon_social: str = ""
    empresa_giro: str = ""
    empresa_direccion: str = ""
    empresa_comuna: str = ""
    empresa_ciudad: str = ""
    empresa_region: str = ""

    # Ambiente SII: "certificacion" | "produccion"
    sii_ambiente: str = "certificacion"

    # DB
    database_url: str = "sqlite+aiosqlite:///./surco_sii.db"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def sii_base_url(self) -> str:
        if self.sii_ambiente == "produccion":
            return "https://palena.sii.cl"
        return "https://maullin.sii.cl"

    @property
    def sii_rcv_url(self) -> str:
        if self.sii_ambiente == "produccion":
            return "https://www4.sii.cl"
        return "https://www4c.sii.cl"


@lru_cache
def get_settings() -> SIISettings:
    return SIISettings()
