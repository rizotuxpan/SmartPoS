# empresa.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Empresa.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional, List                               # Tipos para anotaciones
from uuid import UUID, uuid4                                    # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, insert, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
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
class Empresa(Base):
    __tablename__ = "empresa"  # Nombre de la tabla en la BD

    id_empresa = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    razon_social = Column(String(255), nullable=False)
    nombre_comercial = Column(String(150))
    rfc = Column(CITEXT, nullable=False)
    email_contacto = Column(CITEXT)
    telefono = Column(String(30))
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
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
    created_by = Column(PG_UUID(as_uuid=True), nullable=True)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=True)

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class EmpresaBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Empresa.
    """
    razon_social: str
    nombre_comercial: Optional[str] = None
    rfc: str
    email_contacto: Optional[str] = None
    telefono: Optional[str] = None

class EmpresaCreate(EmpresaBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class EmpresaUpdate(EmpresaBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class EmpresaRead(EmpresaBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_empresa: UUID
    id_estado: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]
    modified_by: Optional[UUID]

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_empresas(
    razon_social: Optional[str] = Query(None),  # Filtro por razón social (ilike)
    skip: int = 0,                              # Paginación: offset
    limit: int = 100,                           # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)    # Sesión RLS inyectada
):
    """
    Lista empresas en estado "activo" con paginación y filtro opcional.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(Empresa.id_estado == estado_activo_id)
    if razon_social:
        stmt = stmt.where(Empresa.razon_social.ilike(f"%{razon_social}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [EmpresaRead.model_validate(e) for e in data]
    }

@router.get("/{id_empresa}", response_model=EmpresaRead)
async def obtener_empresa(
    id_empresa: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una empresa por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(
        Empresa.id_empresa == id_empresa,
        Empresa.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return EmpresaRead.model_validate(empresa)

@router.post("/", response_model=dict, status_code=201)
async def crear_empresa(
    entrada: EmpresaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva empresa. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)

    nueva = Empresa(
        razon_social      = entrada.razon_social,
        nombre_comercial  = entrada.nombre_comercial,
        rfc               = entrada.rfc,
        email_contacto    = entrada.email_contacto,
        telefono          = entrada.telefono,
        created_by        = ctx["user_id"],
        modified_by       = ctx["user_id"]
    )
    db.add(nueva)

    await db.flush()
    await db.refresh(nueva)
    await db.commit()

    return {"success": True, "data": EmpresaRead.model_validate(nueva)}

@router.put("/{id_empresa}", response_model=dict)
async def actualizar_empresa(
    id_empresa: UUID,
    entrada: EmpresaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de una empresa en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(
        Empresa.id_empresa == id_empresa,
        Empresa.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    ctx = await obtener_contexto(db)
    empresa.razon_social     = entrada.razon_social
    empresa.nombre_comercial = entrada.nombre_comercial
    empresa.rfc              = entrada.rfc
    empresa.email_contacto   = entrada.email_contacto
    empresa.telefono         = entrada.telefono
    empresa.modified_by      = ctx["user_id"]

    await db.flush()
    await db.refresh(empresa)
    await db.commit()

    return {"success": True, "data": EmpresaRead.model_validate(empresa)}

@router.delete("/{id_empresa}", status_code=200)
async def eliminar_empresa(
    id_empresa: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una empresa. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Empresa).where(Empresa.id_empresa == id_empresa)
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    await db.execute(delete(Empresa).where(Empresa.id_empresa == id_empresa))
    await db.commit()

    return {"success": True, "message": "Empresa eliminada permanentemente"}
