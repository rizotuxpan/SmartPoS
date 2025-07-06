# subcategoria.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Subcategoría.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional, List                               # Tipos para anotaciones
from uuid import UUID, uuid4                                    # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID      # Tipo UUID específico de PostgreSQL
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# -------------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# -------------------------------------------
class Subcategoria(Base):
    __tablename__ = "cat_subcategoria"  # Nombre de la tabla en la BD

    id_subcategoria = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_categoria = Column(
        PG_UUID(as_uuid=True),
        nullable=False
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
    nombre = Column(String(80), nullable=False)
    descripcion = Column(Text)
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
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class SubcategoriaBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Subcategoría.
    """
    id_categoria: UUID                   # Referencia a categoría padre
    nombre: str                          # Nombre obligatorio
    descripcion: Optional[str] = None    # Descripción opcional

class SubcategoriaCreate(SubcategoriaBase):
    """Esquema para creación; hereda id_categoria, nombre y descripción."""
    pass

class SubcategoriaUpdate(SubcategoriaBase):
    """Esquema para actualización; hereda id_categoria, nombre y descripción."""
    pass

class SubcategoriaRead(SubcategoriaBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_subcategoria: UUID
    id_empresa: UUID
    id_estado: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    modified_by: UUID

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_subcategorias(
    nombre: Optional[str] = Query(None),      # Filtro por nombre (ilike)
    skip: int = 0,                            # Paginación: offset
    limit: int = 100,                         # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista subcategorías en estado "activo" con paginación y filtro opcional.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Subcategoria).where(Subcategoria.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Subcategoria.nombre.ilike(f"%{nombre}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [SubcategoriaRead.model_validate(s) for s in data]
    }

@router.get("/{id_subcategoria}", response_model=SubcategoriaRead)
async def obtener_subcategoria(
    id_subcategoria: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una subcategoría por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Subcategoria).where(
        Subcategoria.id_subcategoria == id_subcategoria,
        Subcategoria.id_estado       == estado_activo_id
    )
    result = await db.execute(stmt)
    subcat = result.scalar_one_or_none()

    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")

    return SubcategoriaRead.model_validate(subcat)

@router.post("/", response_model=dict, status_code=201)
async def crear_subcategoria(
    entrada: SubcategoriaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva subcategoría. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)

    nueva = Subcategoria(
        id_categoria = entrada.id_categoria,
        nombre       = entrada.nombre,
        descripcion  = entrada.descripcion,
        created_by   = ctx["user_id"],
        modified_by  = ctx["user_id"],
        id_empresa   = ctx["tenant_id"]
    )
    db.add(nueva)

    await db.flush()
    await db.refresh(nueva)
    await db.commit()

    return {"success": True, "data": SubcategoriaRead.model_validate(nueva)}

@router.get("/combo", response_model=dict)
async def listar_subcategorias_combo(
    id_categoria: Optional[UUID] = Query(None, description="Filtrar por categoría"),
    db: AsyncSession = Depends(get_async_db)
):
    """Endpoint optimizado para llenar ComboBox de subcategorías con filtro opcional por categoría"""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    query = select(
        Subcategoria.id_subcategoria, 
        Subcategoria.nombre,
        Subcategoria.id_categoria
    ).where(Subcategoria.id_estado == estado_activo_id)
    
    if id_categoria:
        query = query.where(Subcategoria.id_categoria == id_categoria)
    
    query = query.order_by(Subcategoria.nombre)
    
    result = await db.execute(query)
    subcategorias = [
        {
            "id": str(row[0]), 
            "nombre": row[1],
            "id_categoria": str(row[2])
        } for row in result
    ]
    
    return {"success": True, "data": subcategorias}

@router.put("/{id_subcategoria}", response_model=dict)
async def actualizar_subcategoria(
    id_subcategoria: UUID,
    entrada: SubcategoriaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza campos de una subcategoría en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Subcategoria).where(
        Subcategoria.id_subcategoria == id_subcategoria,
        Subcategoria.id_estado       == estado_activo_id
    )
    result = await db.execute(stmt)
    subcat = result.scalar_one_or_none()
    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")

    ctx = await obtener_contexto(db)
    subcat.id_categoria = entrada.id_categoria
    subcat.nombre       = entrada.nombre
    subcat.descripcion  = entrada.descripcion
    subcat.modified_by  = ctx["user_id"]

    await db.flush()
    await db.refresh(subcat)
    await db.commit()

    return {"success": True, "data": SubcategoriaRead.model_validate(subcat)}

@router.delete("/{id_subcategoria}", status_code=200)
async def eliminar_subcategoria(
    id_subcategoria: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una subcategoría. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Subcategoria).where(Subcategoria.id_subcategoria == id_subcategoria)
    )
    subcat = result.scalar_one_or_none()
    if not subcat:
        raise HTTPException(status_code=404, detail="Subcategoría no encontrada")

    await db.execute(delete(Subcategoria).where(Subcategoria.id_subcategoria == id_subcategoria))
    await db.commit()

    return {"success": True, "message": "Subcategoría eliminada permanentemente"}


@router.get("/categoria/{id_categoria}", response_model=dict)
async def listar_subcategorias_por_categoria(
    id_categoria: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista todas las subcategorías activas que pertenecen a una categoría dada,
    con paginación opcional.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta filtrando por categoría e id_estado
    stmt = (
        select(Subcategoria)
        .where(
            Subcategoria.id_estado    == estado_activo_id,
            Subcategoria.id_categoria == id_categoria
        )
    )

    # 3) Contar total de registros para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Devolver respuesta
    return {
        "success": True,
        "total_count": total,
        "data": [SubcategoriaRead.model_validate(s) for s in data]
    }
