from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from .models import Base
from ..sii.config import get_settings


def _make_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


engine = _make_engine()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Crea las tablas si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency de FastAPI para inyectar la sesión de base de datos."""
    async with AsyncSessionLocal() as session:
        yield session
