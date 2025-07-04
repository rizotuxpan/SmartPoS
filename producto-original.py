# producto.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Producto.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional                                      # Tipos para anotaciones
from uuid import UUID                                            # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from decimal import Decimal                                      # Para campos numéricos de alta precisión
from sqlalchemy import (
    Column, String, Text, DateTime, Numeric, Boolean, Integer,
    func, select, text, delete
)
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
class Producto(Base):
    __tablename__ = "producto"

    id_producto    = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa     = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_estado      = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    sku            = Column(String(50))
    codigo_barras  = Column(CITEXT)
    nombre         = Column(String(120), nullable=False)
    descripcion    = Column(Text)
    precio_base    = Column(Numeric(14, 2), nullable=True, server_default=text("0"))
    es_kit         = Column(Boolean, nullable=False, server_default=text("false"))
    vida_util_dias = Column(Integer)
    id_marca       = Column(PG_UUID(as_uuid=True))
    id_umedida     = Column(PG_UUID(as_uuid=True))
    articulo       = Column(String(20))
    guid           = Column(String(36))
    costo_u        = Column(Numeric(14, 2))
    linea          = Column(String(100))
    sublinea       = Column(String(100))
    id_categoria   = Column(PG_UUID(as_uuid=True))
    id_subcategoria= Column(PG_UUID(as_uuid=True))
    created_by     = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by    = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at     = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at     = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class ProductoBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Producto.
    """
    sku: Optional[str] = None
    codigo_barras: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio_base: Optional[Decimal] = None
    es_kit: Optional[bool] = None
    vida_util_dias: Optional[int] = None
    id_marca: Optional[UUID] = None
    id_umedida: Optional[UUID] = None
    articulo: Optional[str] = None
    guid: Optional[str] = None
    costo_u: Optional[Decimal] = None
    linea: Optional[str] = None
    sublinea: Optional[str] = None
    id_categoria: Optional[UUID] = None
    id_subcategoria: Optional[UUID] = None

class ProductoCreate(ProductoBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ProductoUpdate(ProductoBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class ProductoRead(ProductoBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_producto: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_productos(
    nombre: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    codigo_barras: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista productos en estado "activo" con paginación y filtros opcionales.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Producto).where(Producto.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Producto.nombre.ilike(f"%{nombre}%"))
    if sku:
        stmt = stmt.where(Producto.sku.ilike(f"%{sku}%"))
    if codigo_barras:
        stmt = stmt.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [ProductoRead.model_validate(p) for p in data]
    }

@router.get("/{id_producto}", response_model=ProductoRead)
async def obtener_producto(
    id_producto: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un producto por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Producto).where(
        Producto.id_producto == id_producto,
        Producto.id_estado    == estado_activo_id
    )
    result = await db.execute(stmt)
    producto = result.scalar_one_or_none()

    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    return ProductoRead.model_validate(producto)

@router.post("/", response_model=dict, status_code=201)
async def crear_producto(
    entrada: ProductoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo producto. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)

    nuevo = Producto(
        sku             = entrada.sku,
        codigo_barras   = entrada.codigo_barras,
        nombre          = entrada.nombre,
        descripcion     = entrada.descripcion,
        precio_base     = entrada.precio_base,
        es_kit          = entrada.es_kit,
        vida_util_dias  = entrada.vida_util_dias,
        id_marca        = entrada.id_marca,
        id_umedida      = entrada.id_umedida,
        articulo        = entrada.articulo,
        guid            = entrada.guid,
        costo_u         = entrada.costo_u,
        linea           = entrada.linea,
        sublinea        = entrada.sublinea,
        id_categoria    = entrada.id_categoria,
        id_subcategoria = entrada.id_subcategoria,
        created_by      = ctx["user_id"],
        modified_by     = ctx["user_id"],
        id_empresa      = ctx["tenant_id"]
    )
    db.add(nuevo)

    await db.flush()
    await db.refresh(nuevo)
    await db.commit()

    return {"success": True, "data": ProductoRead.model_validate(nuevo)}

@router.put("/{id_producto}", response_model=dict)
async def actualizar_producto(
    id_producto: UUID,
    entrada: ProductoUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un producto en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Producto).where(
        Producto.id_producto == id_producto,
        Producto.id_estado    == estado_activo_id
    )
    result = await db.execute(stmt)
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    ctx = await obtener_contexto(db)
    producto.sku             = entrada.sku
    producto.codigo_barras   = entrada.codigo_barras
    producto.nombre          = entrada.nombre
    producto.descripcion     = entrada.descripcion
    producto.precio_base     = entrada.precio_base
    producto.es_kit          = entrada.es_kit
    producto.vida_util_dias  = entrada.vida_util_dias
    producto.id_marca        = entrada.id_marca
    producto.id_umedida      = entrada.id_umedida
    producto.articulo        = entrada.articulo
    producto.guid            = entrada.guid
    producto.costo_u         = entrada.costo_u
    producto.linea           = entrada.linea
    producto.sublinea        = entrada.sublinea
    producto.id_categoria    = entrada.id_categoria
    producto.id_subcategoria = entrada.id_subcategoria
    producto.modified_by     = ctx["user_id"]

    await db.flush()
    await db.refresh(producto)
    await db.commit()

    return {"success": True, "data": ProductoRead.model_validate(producto)}

@router.delete("/{id_producto}", status_code=200)
async def eliminar_producto(
    id_producto: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un producto. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Producto).where(Producto.id_producto == id_producto)
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    await db.execute(delete(Producto).where(Producto.id_producto == id_producto))
    await db.commit()

    return {"success": True, "message": "Producto eliminado permanentemente"}
