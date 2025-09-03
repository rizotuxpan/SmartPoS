# compra.py
# ---------------------------
# Módulo de endpoints REST para gestión de Compras.
# Integra con el sistema existente de proveedores e inventarios.

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Column, String, Date, Numeric, Text, DateTime, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto

# --------------------------------------
# Modelos ORM (SQLAlchemy)
# --------------------------------------
class Compra(Base):
    __tablename__ = "compra"
    
    id_compra = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("current_setting('app.current_tenant'::text)::uuid"))
    id_proveedor = Column(PG_UUID(as_uuid=True), nullable=False)
    id_almacen = Column(PG_UUID(as_uuid=True), nullable=False)
    numero_compra = Column(String(50), nullable=False)
    fecha_compra = Column(Date, nullable=False, server_default=func.current_date())
    fecha_entrega = Column(Date)
    subtotal = Column(Numeric(14,2), nullable=False, server_default="0")
    impuestos = Column(Numeric(14,2), nullable=False, server_default="0")
    total = Column(Numeric(14,2), nullable=False, server_default="0")
    observaciones = Column(Text)
    estado_compra = Column(String(20), nullable=False, server_default="PENDIENTE")
    id_estado = id_estado = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("f_default_estatus_activo()"))
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class CompraDetalle(Base):
    __tablename__ = "compra_detalle"
    
    id_compra_detalle = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_compra = Column(PG_UUID(as_uuid=True), nullable=False)
    id_producto_variante = Column(PG_UUID(as_uuid=True), nullable=False)
    cantidad_pedida = Column(Numeric(16,4), nullable=False)
    cantidad_recibida = Column(Numeric(16,4), server_default="0")
    costo_unitario = Column(Numeric(14,4), nullable=False)
    subtotal = Column(Numeric(14,2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"
    
    id_movimiento = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    id_almacen = Column(PG_UUID(as_uuid=True), nullable=False)
    id_producto_variante = Column(PG_UUID(as_uuid=True), nullable=False)
    tipo_movimiento = Column(String(20), nullable=False)
    referencia_tipo = Column(String(20))
    referencia_id = Column(PG_UUID(as_uuid=True))
    cantidad = Column(Numeric(16,4), nullable=False)
    costo_unitario = Column(Numeric(14,4))
    stock_anterior = Column(Numeric(16,4), nullable=False)
    stock_nuevo = Column(Numeric(16,4), nullable=False)
    observaciones = Column(Text)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ----------------------------------
# Schemas Pydantic
# ----------------------------------
class CompraDetalleBase(BaseModel):
    id_producto_variante: UUID
    cantidad_pedida: Decimal
    costo_unitario: Decimal
    subtotal: Decimal

class CompraDetalleCreate(CompraDetalleBase):
    pass

class CompraDetalleUpdate(BaseModel):
    cantidad_recibida: Decimal

class CompraDetalleRead(CompraDetalleBase):
    id_compra_detalle: UUID
    id_compra: UUID
    cantidad_recibida: Decimal
    created_at: datetime
    model_config = {"from_attributes": True}

class CompraBase(BaseModel):
    id_proveedor: UUID
    id_almacen: UUID
    numero_compra: str = Field(..., max_length=50)
    fecha_compra: date
    fecha_entrega: Optional[date] = None
    observaciones: Optional[str] = None

class CompraCreate(CompraBase):
    detalles: List[CompraDetalleCreate] = []

class CompraUpdate(BaseModel):
    estado_compra: Optional[str] = Field(None, pattern="^(PENDIENTE|RECIBIDA|CANCELADA)$")
    fecha_entrega: Optional[date] = None
    observaciones: Optional[str] = None

class CompraRead(CompraBase):
    id_compra: UUID
    id_empresa: UUID
    subtotal: Decimal
    impuestos: Decimal
    total: Decimal
    estado_compra: str
    created_by: UUID
    created_at: datetime
    detalles: Optional[List[CompraDetalleRead]] = None
    model_config = {"from_attributes": True}

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_compras(
    id_proveedor: Optional[UUID] = Query(None),
    id_almacen: Optional[UUID] = Query(None),
    estado_compra: Optional[str] = Query(None, pattern="^(PENDIENTE|RECIBIDA|CANCELADA)$"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista compras con filtros opcionales."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Compra).where(Compra.id_estado == estado_activo_id)
    
    if id_proveedor:
        stmt = stmt.where(Compra.id_proveedor == id_proveedor)
    if id_almacen:
        stmt = stmt.where(Compra.id_almacen == id_almacen)
    if estado_compra:
        stmt = stmt.where(Compra.estado_compra == estado_compra)
    if fecha_desde:
        stmt = stmt.where(Compra.fecha_compra >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(Compra.fecha_compra <= fecha_hasta)
    
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)
    
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()
    
    return {
        "success": True,
        "total_count": total,
        "data": [CompraRead.model_validate(c) for c in data]
    }

@router.get("/{id_compra}", response_model=dict)
async def obtener_compra(
    id_compra: UUID,
    incluir_detalles: bool = Query(True),
    db: AsyncSession = Depends(get_async_db)
):
    """Obtiene una compra por ID, opcionalmente con detalles."""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Compra).where(
        Compra.id_compra == id_compra,
        Compra.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    compra = result.scalar_one_or_none()
    
    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    compra_read = CompraRead.model_validate(compra)
    
    if incluir_detalles:
        # Cargar detalles
        stmt_detalles = select(CompraDetalle).where(
            CompraDetalle.id_compra == id_compra
        )
        result_detalles = await db.execute(stmt_detalles)
        detalles = result_detalles.scalars().all()
        compra_read.detalles = [CompraDetalleRead.model_validate(d) for d in detalles]
    
    return {
        "success": True,
        "total_count": 1,
        "data": [compra_read]
    }

@router.post("/", response_model=dict, status_code=201)
async def crear_compra(
    entrada: CompraCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crea una nueva compra con sus detalles."""
    ctx = await obtener_contexto(db)
    
    # Calcular totales
    subtotal = sum(d.subtotal for d in entrada.detalles)
    impuestos = subtotal * Decimal("0.16")  # IVA 16% México
    total = subtotal + impuestos
    
    # Crear compra
    estado_activo_id = await get_estado_id_por_clave("act", db)
    nueva_compra = Compra(
        id_proveedor=entrada.id_proveedor,
        id_almacen=entrada.id_almacen,
        numero_compra=entrada.numero_compra,
        fecha_compra=entrada.fecha_compra,
        fecha_entrega=entrada.fecha_entrega,
        subtotal=subtotal,
        impuestos=impuestos,
        total=total,
        observaciones=entrada.observaciones,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"],
        id_empresa=ctx["tenant_id"],
        id_estado=estado_activo_id
    )
    db.add(nueva_compra)
    await db.flush()
    
    # Crear detalles
    for detalle in entrada.detalles:
        nuevo_detalle = CompraDetalle(
            id_compra=nueva_compra.id_compra,
            id_producto_variante=detalle.id_producto_variante,
            cantidad_pedida=detalle.cantidad_pedida,
            costo_unitario=detalle.costo_unitario,
            subtotal=detalle.subtotal
        )
        db.add(nuevo_detalle)
    
    await db.commit()
    await db.refresh(nueva_compra)
    
    return {"success": True, "data": CompraRead.model_validate(nueva_compra)}

@router.put("/{id_compra}/recibir", response_model=dict)
async def recibir_compra(
    id_compra: UUID,
    recepciones: List[dict],  # [{"id_producto_variante": UUID, "cantidad_recibida": Decimal}]
    db: AsyncSession = Depends(get_async_db)
):
    """
    Marca productos como recibidos y actualiza el inventario.
    recepciones: [{"id_producto_variante": "uuid", "cantidad_recibida": 10.5}]
    """
    # Importar modelo de inventario existente
    try:
        from inventario import Inventario
    except ImportError:
        # Si no funciona, crear la clase aquí mismo
        class Inventario(Base):
            __tablename__ = "inventario"
            id_almacen = Column(PG_UUID(as_uuid=True), primary_key=True)
            id_producto_variante = Column(PG_UUID(as_uuid=True), primary_key=True)
            id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
            stock_actual = Column(Numeric(16,4), nullable=False, default=0)
            stock_minimo = Column(Numeric(16,4), default=0)
            stock_maximo = Column(Numeric(16,4), default=0)
            costo_promedio = Column(Numeric(14,4), default=0)
            ultimo_costo = Column(Numeric(14,4), default=0)
            created_by = Column(PG_UUID(as_uuid=True), nullable=False)
            modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
            created_at = Column(DateTime(timezone=True), server_default=func.now())
            updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    estado_activo_id = await get_estado_id_por_clave("act", db)
    ctx = await obtener_contexto(db)
    
    # Verificar que la compra existe
    stmt = select(Compra).where(
        Compra.id_compra == id_compra,
        Compra.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    compra = result.scalar_one_or_none()
    
    if not compra:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    
    if compra.estado_compra == "RECIBIDA":
        raise HTTPException(status_code=400, detail="Esta compra ya fue recibida")
    
    # Procesar cada recepción
    for recepcion in recepciones:
        id_producto_variante = UUID(recepcion["id_producto_variante"])
        cantidad_recibida = Decimal(str(recepcion["cantidad_recibida"]))
        
        # Actualizar detalle de compra
        stmt_detalle = select(CompraDetalle).where(
            CompraDetalle.id_compra == id_compra,
            CompraDetalle.id_producto_variante == id_producto_variante
        )
        result_detalle = await db.execute(stmt_detalle)
        detalle = result_detalle.scalar_one_or_none()
        
        if detalle and cantidad_recibida > 0:
            detalle.cantidad_recibida = cantidad_recibida
            
            # Obtener o crear registro de inventario
            stmt_inv = select(Inventario).where(
                Inventario.id_almacen == compra.id_almacen,
                Inventario.id_producto_variante == id_producto_variante
            )
            result_inv = await db.execute(stmt_inv)
            inventario = result_inv.scalar_one_or_none()
            
            stock_anterior = Decimal("0")
            if inventario is None:
                # Crear nuevo registro de inventario
                inventario = Inventario(
                    id_almacen=compra.id_almacen,
                    id_producto_variante=id_producto_variante,
                    stock_actual=cantidad_recibida,
                    ultimo_costo=detalle.costo_unitario,
                    costo_promedio=detalle.costo_unitario,
                    created_by=ctx["user_id"],
                    modified_by=ctx["user_id"]
                )
                db.add(inventario)
            else:
                # Actualizar inventario existente
                stock_anterior = inventario.stock_actual
                nuevo_stock = stock_anterior + cantidad_recibida
                
                # Calcular nuevo costo promedio ponderado
                if nuevo_stock > 0:
                    valor_anterior = stock_anterior * inventario.costo_promedio
                    valor_nuevo = cantidad_recibida * detalle.costo_unitario
                    inventario.costo_promedio = (valor_anterior + valor_nuevo) / nuevo_stock
                
                inventario.stock_actual = nuevo_stock
                inventario.ultimo_costo = detalle.costo_unitario
                inventario.modified_by = ctx["user_id"]
            
            # Crear movimiento de inventario
            movimiento = MovimientoInventario(
                id_empresa=ctx["tenant_id"],
                id_almacen=compra.id_almacen,
                id_producto_variante=id_producto_variante,
                tipo_movimiento="ENTRADA",
                referencia_tipo="COMPRA",
                referencia_id=id_compra,
                cantidad=cantidad_recibida,
                costo_unitario=detalle.costo_unitario,
                stock_anterior=stock_anterior,
                stock_nuevo=inventario.stock_actual,
                observaciones=f"Recepción de compra {compra.numero_compra}",
                created_by=ctx["user_id"]
            )
            db.add(movimiento)
    
    # Marcar compra como recibida
    compra.estado_compra = "RECIBIDA"
    compra.modified_by = ctx["user_id"]
    
    await db.commit()
    
    return {"success": True, "message": "Compra recibida y inventario actualizado"}

@router.get("/movimientos/{id_almacen}", response_model=dict)
async def obtener_movimientos_inventario(
    id_almacen: UUID,
    id_producto_variante: Optional[UUID] = Query(None),
    tipo_movimiento: Optional[str] = Query(None),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """Lista movimientos de inventario con filtros."""
    stmt = select(MovimientoInventario).where(
        MovimientoInventario.id_almacen == id_almacen
    )
    
    if id_producto_variante:
        stmt = stmt.where(MovimientoInventario.id_producto_variante == id_producto_variante)
    if tipo_movimiento:
        stmt = stmt.where(MovimientoInventario.tipo_movimiento == tipo_movimiento)
    if fecha_desde:
        stmt = stmt.where(func.date(MovimientoInventario.created_at) >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(func.date(MovimientoInventario.created_at) <= fecha_hasta)
    
    # Contar total de registros para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)
    
    # Aplicar paginación y ordenamiento
    stmt = stmt.order_by(MovimientoInventario.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    movimientos = result.scalars().all()
    
    data = [
        {
            "id_movimiento": str(m.id_movimiento),
            "tipo_movimiento": m.tipo_movimiento,
            "referencia_tipo": m.referencia_tipo,
            "cantidad": float(m.cantidad),
            "costo_unitario": float(m.costo_unitario) if m.costo_unitario else None,
            "stock_anterior": float(m.stock_anterior),
            "stock_nuevo": float(m.stock_nuevo),
            "observaciones": m.observaciones,
            "created_at": m.created_at.isoformat()
        }
        for m in movimientos
    ]
    
    return {
        "success": True,
        "total_count": total,
        "data": data
    }