# pago.py
# ---------------------------
# Módulo de endpoints REST para gestión de Pagos de Ventas.

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, DateTime, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto

# --------------------------------------
# Modelo ORM (SQLAlchemy)
# --------------------------------------
class Pago(Base):
    __tablename__ = "pago"
    
    id_pago = Column(PG_UUID(as_uuid=True), primary_key=True, 
server_default=text("gen_random_uuid()"))
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, 
server_default=text("current_setting('app.current_tenant'::text)::uuid"))
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False, 
server_default=text("f_default_estatus_activo()"))
    id_venta = Column(PG_UUID(as_uuid=True), nullable=False)
    id_forma_pago = Column(PG_UUID(as_uuid=True), nullable=False)
    
    monto = Column(Numeric(14,2), nullable=False)
    referencia = Column(String(100))
    observaciones = Column(String)
    
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ----------------------------------
# Schemas Pydantic
# ----------------------------------
class PagoBase(BaseModel):
    id_forma_pago: UUID
    monto: Decimal
    referencia: Optional[str] = None
    observaciones: Optional[str] = None

class PagoCreate(PagoBase):
    id_venta: UUID

class PagoRead(PagoBase):
    id_pago: UUID
    id_empresa: UUID
    id_estado: UUID
    id_venta: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/venta/{id_venta}", response_model=dict)
async def listar_pagos_venta(
    id_venta: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista todos los pagos de una venta específica."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Pago).where(
        Pago.id_venta == id_venta,
        Pago.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    pagos = result.scalars().all()
    
    total_pagado = sum(p.monto for p in pagos)
    
    return {
        "success": True,
        "total_count": len(pagos),
        "total_pagado": total_pagado,
        "data": [PagoRead.model_validate(p) for p in pagos]
    }

@router.post("/", response_model=dict, status_code=201)
async def crear_pago(
    entrada: PagoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Registra un pago para una venta."""
    ctx = await obtener_contexto(db)
    
    nuevo = Pago(
        id_venta=entrada.id_venta,
        id_forma_pago=entrada.id_forma_pago,
        monto=entrada.monto,
        referencia=entrada.referencia,
        observaciones=entrada.observaciones,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"]
    )
    db.add(nuevo)
    
    await db.flush()
    await db.refresh(nuevo)
    await db.commit()
    
    return {"success": True, "data": PagoRead.model_validate(nuevo)}
