# db.py
# ---------------------------
# Configuracion de la conexion y sesion a PostgreSQL con soporte RLS
# Usando SQLAlchemy Async y FastAPI para inyectar variables de sesion.
# ---------------------------

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Header
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

# URL de conexión a la base de datos PostgreSQL.
# Incluye usuario, contrase�a, host, puerto y nombre de la base.
db_user     = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host     = os.getenv("DB_HOST")
db_port     = os.getenv("DB_PORT")
db_name     = os.getenv("DB_NAME")

if not db_password:
    raise ValueError("Se requiere DB_PASSWORD")

DATABASE_URL = (
    f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
)

# ---------------------------
# Motor de base de datos asíncrono
# ---------------------------
# create_async_engine crea un Engine que entiende peticiones Async
# Se configura pool_size y demás parámetros para controlar concurrencia.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,       # No imprimir SQL en consola (set True para debugging)
    pool_size=50,     # Máximo de conexiones persistentes en el pool
    max_overflow=0,   # No crear conexiones fuera del límite del pool
    pool_timeout=30,  # Tiempo (seg) que espera al pedir conexión antes de error
    pool_recycle=1800 # Recicla conexiones cada 30 min para evitar timeouts en el servidor
)

# ---------------------------
# Generador de sesiones asíncronas
# ---------------------------
# async_sessionmaker crea un factory para AsyncSession
# expire_on_commit=False para que los objetos ORM no pierdan atributos tras commit
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

# ---------------------------
# Base declarativa para modelos ORM
# ---------------------------
# Todos los modelos (clases) heredan de Base para mapear tablas
Base = declarative_base()

# ---------------------------
# Lifespan hook para FastAPI
# ---------------------------
# Permite ejecutar código al arrancar y cerrar la app.
# En este caso, al shutdown cerramos el engine y liberamos pool.
@asynccontextmanager
async def lifespan(app):
    # Código antes de arrancar la aplicación
    yield  # Aquí se ejecuta startup y se atienden peticiones
    # Al terminar la aplicación:
    await engine.dispose()  # Cierra conexiones y termina el pool

# ---------------------------
# Dependencia para obtener sesión y establecer RLS
# ---------------------------
async def get_async_db(
    tenant_id: UUID = Header(..., alias="Tenant_ID"),  # Leer header Tenant_ID
    user_id: UUID   = Header(..., alias="User_ID")     # Leer header User_ID
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provee una sesión de base de datos por request,
    e inyecta las variables de contexto RLS en PostgreSQL:
      - app.current_tenant = tenant_id
      - app.usuario        = user_id

    Estas variables luego son usadas en las políticas RLS definidas en la BD.
    """
    # Abrir contexto de sesión (AsyncSessionLocal())
    async with AsyncSessionLocal() as db:
        # Ejecutar comandos SET LOCAL en la misma transacción
        # Garantiza que cada transacción tenga sus variables aisladas.
        await db.execute(
            text(f"SET LOCAL app.current_tenant = '{str(tenant_id)}'"))
        await db.execute(
            text(f"SET LOCAL app.usuario        = '{str(user_id)}'"))
        # Ceder la sesión al endpoint
        yield db
    # Al salir del async with, la sesión se cierra automáticamente

get_async_session = get_async_db
