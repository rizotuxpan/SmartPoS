# inventario.py
# ---------------------------
# Módulo de endpoints REST para gestión del Inventario.
# Control de stock por almacén y producto_variante.

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Numeric, DateTime, func, select, text, and_
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto

# --------------------------------------
# Modelo ORM (SQLAlchemy)
# --------------------------------------
class Inventario(Base):
    __tablename__ = "inventario"
    
    id_almacen = Column(PG_UUID(as_uuid=True), primary_key=True)
    id_producto_variante = Column(PG_UUID(as_uuid=True), primary_key=True)
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    stock_actual = Column(Numeric(16,4), nullable=False, default=0)
    stock_minimo = Column(Numeric(16,4), default=0)
    stock_maximo = Column(Numeric(16,4), default=0)
    costo_promedio = Column(Numeric(14,4), default=0)
    ultimo_costo = Column(Numeric(14,4), default=0)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ----------------------------------
# Schemas Pydantic
# ----------------------------------
class InventarioBase(BaseModel):
    stock_actual: Decimal
    stock_minimo: Optional[Decimal] = None
    stock_maximo: Optional[Decimal] = None
    costo_promedio: Optional[Decimal] = None
    ultimo_costo: Optional[Decimal] = None

class InventarioCreate(InventarioBase):
    id_almacen: UUID
    id_producto_variante: UUID

class InventarioUpdate(InventarioBase):
    pass

class InventarioRead(InventarioBase):
    id_almacen: UUID
    id_producto_variante: UUID
    id_empresa: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_inventario(
    id_almacen: Optional[UUID] = Query(None),
    id_producto_variante: Optional[UUID] = Query(None),
    stock_bajo: bool = Query(False, description="Solo productos con stock bajo"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista inventario con filtros opcionales."""
    stmt = select(Inventario)
    
    if id_almacen:
        stmt = stmt.where(Inventario.id_almacen == id_almacen)
    if id_producto_variante:
        stmt = stmt.where(Inventario.id_producto_variante == id_producto_variante)
    if stock_bajo:
        stmt = stmt.where(Inventario.stock_actual <= Inventario.stock_minimo)
    
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)
    
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()
    
    return {
        "success": True,
        "total_count": total,
        "data": [InventarioRead.model_validate(i) for i in data]
    }

@router.get("/{id_almacen}/{id_producto_variante}", response_model=InventarioRead)
async def obtener_inventario(
    id_almacen: UUID,
    id_producto_variante: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Obtiene stock específico de un producto en un almacén."""
    stmt = select(Inventario).where(
        Inventario.id_almacen == id_almacen,
        Inventario.id_producto_variante == id_producto_variante
    )
    result = await db.execute(stmt)
    inventario = result.scalar_one_or_none()
    
    if not inventario:
        raise HTTPException(status_code=404, detail="Inventario no encontrado")
    
    return InventarioRead.model_validate(inventario)

@router.post("/", response_model=dict, status_code=201)
async def crear_inventario(
    entrada: InventarioCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crea registro de inventario inicial."""
    ctx = await obtener_contexto(db)
    
    nuevo = Inventario(
        id_almacen=entrada.id_almacen,
        id_producto_variante=entrada.id_producto_variante,
        stock_actual=entrada.stock_actual,
        stock_minimo=entrada.stock_minimo or 0,
        stock_maximo=entrada.stock_maximo or 0,
        costo_promedio=entrada.costo_promedio or 0,
        ultimo_costo=entrada.ultimo_costo or 0,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"]
    )
    db.add(nuevo)
    
    await db.flush()
    await db.refresh(nuevo)
    await db.commit()
    
    return {"success": True, "data": InventarioRead.model_validate(nuevo)}
