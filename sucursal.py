# sucursal.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Sucursal.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional                                      # Tipos para anotaciones
from uuid import UUID                                            # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID       # Tipo UUID específico de PostgreSQL
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Sucursal(Base):
    __tablename__ = "sucursal"  # Nombre de la tabla en la BD

    id_sucursal = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False
    )
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    codigo = Column(String(30), nullable=False)
    nombre = Column(String(120), nullable=False)
    direccion = Column(Text)
    telefono = Column(String(30))
    created_by = Column(PG_UUID(as_uuid=True), nullable=True)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class SucursalBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Sucursal.
    """
    codigo: str
    nombre: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None

class SucursalCreate(SucursalBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class SucursalUpdate(SucursalBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class SucursalRead(SucursalBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_sucursal: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: Optional[UUID]
    modified_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_sucursales(
    codigo: Optional[str] = Query(None),         # Filtro por código (ilike)
    nombre: Optional[str] = Query(None),         # Filtro por nombre (ilike)
    skip: int = 0,                               # Paginación: offset
    limit: int = 100,                            # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)     # Sesión RLS inyectada
):
    """
    Lista sucursales en estado "activo" con paginación y filtros opcionales.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Sucursal).where(Sucursal.id_estado == estado_activo_id)
    if codigo:
        stmt = stmt.where(Sucursal.codigo.ilike(f"%{codigo}%"))
    if nombre:
        stmt = stmt.where(Sucursal.nombre.ilike(f"%{nombre}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [SucursalRead.model_validate(s) for s in data]
    }

@router.get("/{id_sucursal}", response_model=SucursalRead)
async def obtener_sucursal(
    id_sucursal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una sucursal por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Sucursal).where(
        Sucursal.id_sucursal == id_sucursal,
        Sucursal.id_estado    == estado_activo_id
    )
    result = await db.execute(stmt)
    suc = result.scalar_one_or_none()

    if not suc:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    return SucursalRead.model_validate(suc)

@router.post("/", response_model=dict, status_code=201)
async def crear_sucursal(
    entrada: SucursalCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva sucursal. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)

    nueva = Sucursal(
        codigo      = entrada.codigo,
        nombre      = entrada.nombre,
        direccion   = entrada.direccion,
        telefono    = entrada.telefono,
        id_empresa  = ctx["tenant_id"],
        created_by  = ctx["user_id"],
        modified_by = ctx["user_id"]
    )
    db.add(nueva)

    await db.flush()
    await db.refresh(nueva)
    await db.commit()

    return {"success": True, "data": SucursalRead.model_validate(nueva)}

@router.put("/{id_sucursal}", response_model=dict)
async def actualizar_sucursal(
    id_sucursal: UUID,
    entrada: SucursalUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de una sucursal en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Sucursal).where(
        Sucursal.id_sucursal == id_sucursal,
        Sucursal.id_estado    == estado_activo_id
    )
    result = await db.execute(stmt)
    suc = result.scalar_one_or_none()
    if not suc:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    ctx = await obtener_contexto(db)
    suc.codigo      = entrada.codigo
    suc.nombre      = entrada.nombre
    suc.direccion   = entrada.direccion
    suc.telefono    = entrada.telefono
    suc.modified_by = ctx["user_id"]

    await db.flush()
    await db.refresh(suc)
    await db.commit()

    return {"success": True, "data": SucursalRead.model_validate(suc)}

@router.delete("/{id_sucursal}", status_code=200)
async def eliminar_sucursal(
    id_sucursal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una sucursal. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Sucursal).where(Sucursal.id_sucursal == id_sucursal)
    )
    suc = result.scalar_one_or_none()
    if not suc:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    await db.execute(delete(Sucursal).where(Sucursal.id_sucursal == id_sucursal))
    await db.commit()

    return {"success": True, "message": "Sucursal eliminada permanentemente"}
