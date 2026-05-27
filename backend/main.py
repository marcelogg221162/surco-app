"""
Surco SII Backend
-----------------
API FastAPI para integración con el Servicio de Impuestos Internos de Chile.

Ejecutar:
    cd backend
    uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.session import init_db
from routers import auth_router, dte_router, rcv_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Surco — Integración SII Chile",
    version="1.0.0",
    description="API para autenticación, envío de DTE y consulta del RCV.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción limitar al dominio de Surco
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/sii/auth",  tags=["Autenticación SII"])
app.include_router(dte_router.router,  prefix="/sii/dte",   tags=["DTE"])
app.include_router(rcv_router.router,  prefix="/sii/rcv",   tags=["RCV"])


@app.get("/health")
async def health():
    return {"status": "ok", "servicio": "Surco SII Backend"}
