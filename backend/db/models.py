from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EstadoDTE(str, PyEnum):
    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    ACEPTADO = "ACEPTADO"
    ACEPTADO_CON_REPAROS = "ACEPTADO_CON_REPAROS"
    RECHAZADO = "RECHAZADO"
    ERROR = "ERROR"


class DTE(Base):
    """Registro de cada Documento Tributario Electrónico enviado al SII."""
    __tablename__ = "dte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificación del documento
    tipo_dte: Mapped[int] = mapped_column(Integer, nullable=False)          # 33=Factura, 39=Boleta
    folio: Mapped[int] = mapped_column(Integer, nullable=False)
    rut_emisor: Mapped[str] = mapped_column(String(12), nullable=False)
    rut_receptor: Mapped[str] = mapped_column(String(12), nullable=False)
    razon_social_receptor: Mapped[str] = mapped_column(String(100), nullable=False)

    # Montos
    monto_neto: Mapped[int] = mapped_column(Integer, default=0)
    monto_iva: Mapped[int] = mapped_column(Integer, default=0)
    monto_total: Mapped[int] = mapped_column(Integer, nullable=False)

    # Seguimiento SII
    track_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estado: Mapped[EstadoDTE] = mapped_column(
        Enum(EstadoDTE), default=EstadoDTE.PENDIENTE, nullable=False
    )
    glosa_estado: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # XML almacenado para auditoría
    xml_enviado: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<DTE tipo={self.tipo_dte} folio={self.folio} estado={self.estado}>"


class ConsultaRCV(Base):
    """Caché de las consultas al Registro de Compras y Ventas."""
    __tablename__ = "consulta_rcv"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rut_empresa: Mapped[str] = mapped_column(String(12), nullable=False)
    periodo: Mapped[str] = mapped_column(String(7), nullable=False)         # "YYYY-MM"
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)           # "compras" | "ventas"
    cantidad_documentos: Mapped[int] = mapped_column(Integer, default=0)
    monto_total: Mapped[int] = mapped_column(Integer, default=0)
    datos_json: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON completo
    consultado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
