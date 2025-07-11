# venta_detalle.py
# ---------------------------
# Módulo de endpoints REST para gestión de Detalles de Venta.

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from sqlalchemy import Column, Numeric, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.contexto import obtener_contexto

# --------------------------------------
# Modelo ORM (SQLAlchemy)
# --------------------------------------
class VentaDetalle(Base):
    __tablename__ = "venta_detalle"
    
    id_venta_detalle = Column(PG_UUID(as_uuid=True), primary_key=True, 
server_default=text("gen_random_uuid()"))
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, 
server_default=text("current_setting('app.current_tenant'::text)::uuid"))
    id_venta = Column(PG_UUID(as_uuid=True), nullable=False)
    id_producto_var = Column(PG_UUID(as_uuid=True), nullable=False)
    
    cantidad = Column(Numeric(14,2), nullable=False)
    precio_unitario = Column(Numeric(14,4), nullable=False)
    descuento_linea = Column(Numeric(14,2), default=0)
    total_linea = Column(Numeric(14,2), nullable=False)

# ----------------------------------
# Schemas Pydantic
# ----------------------------------
class VentaDetalleBase(BaseModel):
    id_producto_var: UUID
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_linea: Optional[Decimal] = 0
    total_linea: Decimal

class VentaDetalleCreate(VentaDetalleBase):
    id_venta: UUID

class VentaDetalleRead(VentaDetalleBase):
    id_venta_detalle: UUID
    id_empresa: UUID
    id_venta: UUID
    
    model_config = {"from_attributes": True}

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/venta/{id_venta}", response_model=dict)
async def listar_detalle_venta(
    id_venta: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista todos los detalles de una venta específica."""
    stmt = select(VentaDetalle).where(VentaDetalle.id_venta == id_venta)
    result = await db.execute(stmt)
    detalles = result.scalars().all()
    
    return {
        "success": True,
        "total_count": len(detalles),
        "data": [VentaDetalleRead.model_validate(d) for d in detalles]
    }

@router.post("/", response_model=dict, status_code=201)
async def crear_detalle_venta(
    entrada: VentaDetalleCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Agrega una línea de producto a una venta."""
    ctx = await obtener_contexto(db)
    
    nuevo = VentaDetalle(
        id_venta=entrada.id_venta,
        id_producto_var=entrada.id_producto_var,
        cantidad=entrada.cantidad,
        precio_unitario=entrada.precio_unitario,
        descuento_linea=entrada.descuento_linea,
        total_linea=entrada.total_linea
    )
    db.add(nuevo)
    
    await db.flush()
    await db.refresh(nuevo)
    await db.commit()
    
    return {"success": True, "data": VentaDetalleRead.model_validate(nuevo)}
