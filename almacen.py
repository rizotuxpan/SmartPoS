# almacen.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Almacén.
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
class Almacen(Base):
    __tablename__ = "almacen"  # Nombre de la tabla en la BD

    id_almacen = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_sucursal = Column(
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
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
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
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class AlmacenBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Almacén.
    """
    id_sucursal: UUID
    codigo: str
    nombre: str
    direccion: Optional[str] = None
    telefono: Optional[str] = None

class AlmacenCreate(AlmacenBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class AlmacenUpdate(AlmacenBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class AlmacenRead(AlmacenBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_almacen: UUID
    id_estado: UUID
    id_empresa: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_almacenes(
    id_sucursal: Optional[UUID] = Query(None),  # Filtro por sucursal
    codigo: Optional[str]    = Query(None),     # Filtro por código (ilike)
    nombre: Optional[str]    = Query(None),     # Filtro por nombre (ilike)
    skip: int                = 0,              # Paginación: offset
    limit: int               = 100,            # Paginación: máximo de registros
    db: AsyncSession         = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista almacenes en estado "activo" con paginación y filtros opcionales.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Almacen).where(Almacen.id_estado == estado_activo_id)
    if id_sucursal:
        stmt = stmt.where(Almacen.id_sucursal == id_sucursal)
    if codigo:
        stmt = stmt.where(Almacen.codigo.ilike(f"%{codigo}%"))
    if nombre:
        stmt = stmt.where(Almacen.nombre.ilike(f"%{nombre}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [AlmacenRead.model_validate(a) for a in data]
    }

@router.get("/{id_almacen}", response_model=AlmacenRead)
async def obtener_almacen(
    id_almacen: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un almacén por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Almacen).where(
        Almacen.id_almacen == id_almacen,
        Almacen.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    almacen = result.scalar_one_or_none()

    if not almacen:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    return AlmacenRead.model_validate(almacen)

@router.post("/", response_model=dict, status_code=201)
async def crear_almacen(
    entrada: AlmacenCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo almacén. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)

    nuevo = Almacen(
        id_sucursal  = entrada.id_sucursal,
        codigo       = entrada.codigo,
        nombre       = entrada.nombre,
        direccion    = entrada.direccion,
        telefono     = entrada.telefono,
        id_empresa   = ctx["tenant_id"],
        created_by   = ctx["user_id"],
        modified_by  = ctx["user_id"]
    )
    db.add(nuevo)

    await db.flush()
    await db.refresh(nuevo)
    await db.commit()

    return {"success": True, "data": AlmacenRead.model_validate(nuevo)}

@router.put("/{id_almacen}", response_model=dict)
async def actualizar_almacen(
    id_almacen: UUID,
    entrada: AlmacenUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un almacén en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Almacen).where(
        Almacen.id_almacen == id_almacen,
        Almacen.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    almacen = result.scalar_one_or_none()
    if not almacen:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    ctx = await obtener_contexto(db)
    almacen.id_sucursal  = entrada.id_sucursal
    almacen.codigo       = entrada.codigo
    almacen.nombre       = entrada.nombre
    almacen.direccion    = entrada.direccion
    almacen.telefono     = entrada.telefono
    almacen.modified_by  = ctx["user_id"]

    await db.flush()
    await db.refresh(almacen)
    await db.commit()

    return {"success": True, "data": AlmacenRead.model_validate(almacen)}

@router.delete("/{id_almacen}", status_code=200)
async def eliminar_almacen(
    id_almacen: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un almacén. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Almacen).where(Almacen.id_almacen == id_almacen)
    )
    almacen = result.scalar_one_or_none()
    if not almacen:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    await db.execute(delete(Almacen).where(Almacen.id_almacen == id_almacen))
    await db.commit()

    return {"success": True, "message": "Almacén eliminado permanentemente"}

@router.get("/sucursal/{id_sucursal}", response_model=dict)
async def listar_almacenes_por_sucursal(
    id_sucursal: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista los almacenes activos asociados a la sucursal indicada,
    con paginación opcional.

    Ruta completa: GET /almacen/sucursal/{id_sucursal}
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta filtrando por sucursal e id_estado
    stmt = (
        select(Almacen)
        .where(
            Almacen.id_estado   == estado_activo_id,
            Almacen.id_sucursal == id_sucursal
        )
    )

    # 3) Contar total de registros para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Devolver respuesta con el mismo formato que otros endpoints
    return {
        "success": True,
        "total_count": total,
        "data": [AlmacenRead.model_validate(a) for a in data]
    }
