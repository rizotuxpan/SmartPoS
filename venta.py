# venta.py
# ---------------------------
# Módulo de endpoints REST para gestión de Ventas.

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, Numeric, Date, DateTime, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto

# --------------------------------------
# Modelo ORM (SQLAlchemy) - SIN CAMBIOS
# --------------------------------------
class Venta(Base):
    __tablename__ = "venta"
    
    id_venta = Column(PG_UUID(as_uuid=True), primary_key=True, 
server_default=text("gen_random_uuid()"))
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, 
server_default=text("current_setting('app.current_tenant'::text)::uuid"))
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False, 
server_default=text("f_default_estatus_activo()"))
    id_cliente = Column(PG_UUID(as_uuid=True), nullable=False)
    id_terminal = Column(PG_UUID(as_uuid=True), nullable=False)
    id_sucursal = Column(PG_UUID(as_uuid=True), nullable=False)
    id_usuario = Column(PG_UUID(as_uuid=True), nullable=False)  # Vendedor
    
    numero_folio = Column(String(50), nullable=False)
    fecha_venta = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    subtotal = Column(Numeric(14,2), nullable=False, default=0)
    descuento = Column(Numeric(14,2), default=0)
    impuesto = Column(Numeric(14,2), default=0)
    total = Column(Numeric(14,2), nullable=False, default=0)
    
    tipo_venta = Column(String(20), nullable=False, default='CONTADO')  # CONTADO, CREDITO
    estado_venta = Column(String(20), nullable=False, default='COMPLETADA')  # COMPLETADA, PENDIENTE, ANULADA
    
    observaciones = Column(String)
    
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ----------------------------------
# Schemas Pydantic - CORREGIDOS
# ----------------------------------
class VentaBase(BaseModel):
    id_cliente: UUID
    id_terminal: UUID
    id_sucursal: UUID
    id_usuario: UUID
    numero_folio: str
    fecha_venta: Optional[datetime] = None  # ✅ AGREGADO - CAMPO FALTANTE
    subtotal: Decimal
    descuento: Optional[Decimal] = 0
    impuesto: Optional[Decimal] = 0
    total: Decimal
    tipo_venta: Optional[str] = "CONTADO"
    estado_venta: Optional[str] = "COMPLETADA"
    observaciones: Optional[str] = None
    created_by: UUID  # ✅ AGREGADO - CAMPO FALTANTE
    modified_by: UUID  # ✅ AGREGADO - CAMPO FALTANTE

class VentaCreate(VentaBase):
    pass

class VentaUpdate(BaseModel):
    numero_folio: Optional[str] = None
    fecha_venta: Optional[datetime] = None
    subtotal: Optional[Decimal] = None
    descuento: Optional[Decimal] = None
    impuesto: Optional[Decimal] = None
    total: Optional[Decimal] = None
    tipo_venta: Optional[str] = None
    estado_venta: Optional[str] = None
    observaciones: Optional[str] = None
    modified_by: Optional[UUID] = None

class VentaRead(VentaBase):
    id_venta: UUID
    id_empresa: UUID
    id_estado: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_ventas(
    id_cliente: Optional[UUID] = Query(None),
    id_terminal: Optional[UUID] = Query(None),
    id_sucursal: Optional[UUID] = Query(None),
    numero_folio: Optional[str] = Query(None),
    estado_venta: Optional[str] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista ventas con filtros opcionales."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Venta).where(Venta.id_estado == estado_activo_id)
    
    if id_cliente:
        stmt = stmt.where(Venta.id_cliente == id_cliente)
    if id_terminal:
        stmt = stmt.where(Venta.id_terminal == id_terminal)
    if id_sucursal:
        stmt = stmt.where(Venta.id_sucursal == id_sucursal)
    if numero_folio:
        stmt = stmt.where(Venta.numero_folio.ilike(f"%{numero_folio}%"))
    if estado_venta:
        stmt = stmt.where(Venta.estado_venta == estado_venta)
    if fecha_desde:
        stmt = stmt.where(Venta.fecha_venta >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(Venta.fecha_venta <= fecha_hasta)
    
    stmt = stmt.order_by(Venta.fecha_venta.desc())
    
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)
    
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()
    
    return {
        "success": True,
        "total_count": total,
        "data": [VentaRead.model_validate(v) for v in data]
    }

@router.get("/{id_venta}", response_model=VentaRead)
async def obtener_venta(
    id_venta: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Obtiene una venta por ID."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Venta).where(
        Venta.id_venta == id_venta,
        Venta.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    venta = result.scalar_one_or_none()
    
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    return VentaRead.model_validate(venta)

@router.post("/", response_model=dict, status_code=201)
async def crear_venta(
    entrada: VentaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crea una nueva venta."""
    ctx = await obtener_contexto(db)
    
    nueva = Venta(
        id_cliente=entrada.id_cliente,
        id_terminal=entrada.id_terminal,
        id_sucursal=entrada.id_sucursal,
        id_usuario=entrada.id_usuario,
        numero_folio=entrada.numero_folio,
        fecha_venta=entrada.fecha_venta or datetime.now(),  # ✅ AGREGADO - PROCESAR FECHA_VENTA
        subtotal=entrada.subtotal,
        descuento=entrada.descuento,
        impuesto=entrada.impuesto,
        total=entrada.total,
        tipo_venta=entrada.tipo_venta,
        estado_venta=entrada.estado_venta,
        observaciones=entrada.observaciones,
        created_by=entrada.created_by,  # ✅ CAMBIADO - USAR DEL JSON EN LUGAR DE CTX
        modified_by=entrada.modified_by  # ✅ CAMBIADO - USAR DEL JSON EN LUGAR DE CTX
    )
    db.add(nueva)
    
    await db.flush()
    await db.refresh(nueva)
    await db.commit()
    
    return {"success": True, "data": VentaRead.model_validate(nueva)}

@router.put("/{id_venta}", response_model=dict)
async def actualizar_venta(
    id_venta: UUID,
    entrada: VentaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """Actualiza una venta existente."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Venta).where(
        Venta.id_venta == id_venta,
        Venta.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    venta = result.scalar_one_or_none()
    
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    
    # Actualizar campos proporcionados
    update_data = entrada.dict(exclude_unset=True)
    update_data['updated_at'] = datetime.now()
    
    for field, value in update_data.items():
        setattr(venta, field, value)
    
    try:
        await db.commit()
        await db.refresh(venta)
        
        return {
            "success": True,
            "data": VentaRead.model_validate(venta)
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar venta: {str(e)}")

# ===== ENDPOINT ADICIONAL PARA DEBUGGING =====
@router.post("/debug", response_model=dict)
async def debug_venta(
    entrada: dict,
    db: AsyncSession = Depends(get_async_db)
):
    """Endpoint para debugging - muestra qué datos se reciben."""
    return {
        "success": True,
        "received_data": entrada,
        "fields_count": len(entrada),
        "fields": list(entrada.keys())
    }