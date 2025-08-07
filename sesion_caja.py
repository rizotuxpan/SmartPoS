# sesion_caja.py
# -----------------------------------------------
# Endpoints API para Sistema de Cortes de Caja X, Z
# VERSIÓN CORREGIDA - Compatible con Pascal y Funciones Refactorizadas
# -----------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, Text, DateTime, Numeric, Boolean, Integer, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

# Importaciones del proyecto
from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto

# =====================================================
# MODELOS ORM (SQLAlchemy) - SIN CAMBIOS
# =====================================================

class SesionCaja(Base):
    __tablename__ = "sesion_caja"

    id_sesion = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("current_setting('app.current_tenant')::uuid"))
    id_terminal = Column(PG_UUID(as_uuid=True), nullable=False)
    id_usuario_apertura = Column(PG_UUID(as_uuid=True), nullable=False)
    id_usuario_cierre = Column(PG_UUID(as_uuid=True), nullable=True)
    
    fecha_apertura = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    
    fondo_inicial = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    efectivo_sistema = Column(Numeric(14, 2), nullable=True)
    efectivo_contado = Column(Numeric(14, 2), nullable=True)
    diferencia_efectivo = Column(Numeric(14, 2), nullable=True)
    
    estado_sesion = Column(String(20), nullable=False, server_default=text("'ABIERTA'"))
    observaciones_cierre = Column(Text, nullable=True)
    
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class CorteCaja(Base):
    __tablename__ = "corte_caja"

    id_corte = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("current_setting('app.current_tenant')::uuid"))
    id_sesion = Column(PG_UUID(as_uuid=True), nullable=False)
    id_terminal = Column(PG_UUID(as_uuid=True), nullable=False)
    id_usuario = Column(PG_UUID(as_uuid=True), nullable=False)
    
    tipo_corte = Column(String(1), nullable=False)  # 'X' o 'Z'
    numero_corte_x = Column(Integer, nullable=False, server_default=text("0"))
    fecha_corte = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    total_ventas = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    cantidad_ventas = Column(Integer, nullable=False, server_default=text("0"))
    total_efectivo = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    total_tarjeta = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    total_transferencia = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    total_otros_pagos = Column(Numeric(14, 2), nullable=False, server_default=text("0.00"))
    
    # Solo para Corte Z
    fondo_inicial = Column(Numeric(14, 2), nullable=True)
    efectivo_esperado = Column(Numeric(14, 2), nullable=True)
    efectivo_contado = Column(Numeric(14, 2), nullable=True)
    diferencia_efectivo = Column(Numeric(14, 2), nullable=True)
    
    observaciones = Column(Text, nullable=True)
    impreso = Column(Boolean, server_default=text("false"))
    
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class MovimientoEfectivo(Base):
    __tablename__ = "movimiento_efectivo"

    id_movimiento = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("current_setting('app.current_tenant')::uuid"))
    id_sesion = Column(PG_UUID(as_uuid=True), nullable=False)
    id_terminal = Column(PG_UUID(as_uuid=True), nullable=False)
    id_usuario = Column(PG_UUID(as_uuid=True), nullable=False)
    
    tipo_movimiento = Column(String(20), nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    id_venta = Column(PG_UUID(as_uuid=True), nullable=True)
    id_pago = Column(PG_UUID(as_uuid=True), nullable=True)
    
    concepto = Column(String(200), nullable=False)
    referencia = Column(String(100), nullable=True)
    fecha_movimiento = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# =====================================================
# SCHEMAS PYDANTIC - SIN CAMBIOS (YA TIENEN LOS NOMBRES CORRECTOS)
# =====================================================

class AbrirCajaRequest(BaseModel):
    id_terminal: UUID
    fondo_inicial: Decimal = Field(ge=0, description="Fondo inicial debe ser mayor o igual a 0")

class CerrarCajaRequest(BaseModel):
    id_terminal: UUID
    efectivo_contado: Decimal = Field(ge=0, description="Efectivo contado debe ser mayor o igual a 0")
    observaciones: Optional[str] = None

class CorteXRequest(BaseModel):
    id_terminal: UUID

class SesionCajaRead(BaseModel):
    id_sesion: UUID
    id_terminal: UUID
    id_usuario_apertura: UUID
    id_usuario_cierre: Optional[UUID]
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime]
    fondo_inicial: Decimal
    efectivo_sistema: Optional[Decimal]
    efectivo_contado: Optional[Decimal]
    diferencia_efectivo: Optional[Decimal]
    estado_sesion: str
    observaciones_cierre: Optional[str]
    
    model_config = {"from_attributes": True}

class CorteCajaRead(BaseModel):
    id_corte: UUID
    id_sesion: UUID
    id_terminal: UUID
    id_usuario: UUID
    tipo_corte: str
    numero_corte_x: int
    fecha_corte: datetime
    total_ventas: Decimal
    cantidad_ventas: int
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_otros_pagos: Decimal
    fondo_inicial: Optional[Decimal]
    efectivo_esperado: Optional[Decimal]
    efectivo_contado: Optional[Decimal]
    diferencia_efectivo: Optional[Decimal]
    observaciones: Optional[str]
    impreso: bool
    
    model_config = {"from_attributes": True}

class EstadoTerminalRead(BaseModel):
    id_terminal: UUID
    codigo_terminal: str
    nombre_terminal: str
    sucursal_nombre: str
    estado_actual: str
    id_sesion: Optional[UUID]
    fecha_apertura: Optional[datetime]
    fondo_inicial: Optional[Decimal]
    usuario_apertura: Optional[str]
    ventas_sesion_actual: Decimal
    cantidad_ventas_sesion: int
    efectivo_sesion_actual: Decimal
    ultimo_tipo_corte: Optional[str]
    fecha_ultimo_corte: Optional[datetime]
    ultimo_numero_x: Optional[int]
    horas_sesion_abierta: Optional[float]
    
    model_config = {"from_attributes": True}

class DatosCorteXRead(BaseModel):
    id_terminal: UUID
    codigo_terminal: str
    nombre_terminal: str  # ✅ YA CORRECTO para Pascal
    id_sesion: UUID
    fecha_apertura: datetime
    fondo_inicial: Decimal
    usuario_apertura: str
    cantidad_ventas: int
    total_ventas: Decimal
    subtotal_ventas: Decimal
    impuestos_ventas: Decimal
    descuentos_ventas: Decimal
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_otros: Decimal
    efectivo_esperado: Decimal
    fecha_corte: datetime
    proximo_numero_x: int
    inicio_periodo: datetime
    fin_periodo: datetime
    
    model_config = {"from_attributes": True}

class MovimientoEfectivoRead(BaseModel):
    id_movimiento: UUID
    id_sesion: UUID
    id_terminal: UUID
    id_usuario: UUID
    tipo_movimiento: str
    monto: Decimal
    id_venta: Optional[UUID]
    id_pago: Optional[UUID]
    concepto: str
    referencia: Optional[str]
    fecha_movimiento: datetime
    
    model_config = {"from_attributes": True}

# =====================================================
# ROUTER Y ENDPOINTS - ACTUALIZADOS PARA PASCAL
# =====================================================

router = APIRouter()

@router.post("/abrir-caja", response_model=dict, status_code=201)
async def abrir_caja(
    entrada: AbrirCajaRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Abrir sesión de caja con fondo inicial.
    Solo se permite una sesión abierta por terminal.
    """
    ctx = await obtener_contexto(db)
    
    # Verificar que no haya sesión abierta
    stmt = select(SesionCaja).where(
        SesionCaja.id_terminal == entrada.id_terminal,
        SesionCaja.estado_sesion == 'ABIERTA'
    )
    sesion_existente = await db.scalar(stmt)
    
    if sesion_existente:
        raise HTTPException(
            status_code=400, 
            detail="Ya existe una sesión abierta para esta terminal"
        )
    
    try:
        # Llamar función de base de datos
        result = await db.execute(
            text("SELECT fn_abrir_caja(:id_terminal, :id_usuario, :fondo_inicial)"),
            {
                "id_terminal": str(entrada.id_terminal),
                "id_usuario": str(ctx["user_id"]),
                "fondo_inicial": float(entrada.fondo_inicial)
            }
        )
        id_sesion = result.scalar()
        await db.commit()
        
        return {
            "success": True,
            "message": "Caja abierta exitosamente",
            "id_sesion": id_sesion,
            "fondo_inicial": entrada.fondo_inicial
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al abrir caja: {str(e)}")

# En sesion_caja.py
@router.post("/cerrar-caja", response_model=dict)
async def cerrar_caja(
    entrada: CerrarCajaRequest,
    db: AsyncSession = Depends(get_async_db)
):
    ctx = await obtener_contexto(db)
    
    # ✅ CONFIGURAR CONTEXTO RLS EXPLÍCITAMENTE
    await db.execute(text(f"SET app.current_tenant = '{ctx['tenant_id']}'"))
    
    # Verificar que hay sesión abierta
    stmt = select(SesionCaja).where(
        SesionCaja.id_terminal == entrada.id_terminal,
        SesionCaja.estado_sesion == 'ABIERTA'
    )
    sesion = await db.scalar(stmt)
    
    if not sesion:
        raise HTTPException(
            status_code=400, 
            detail="No hay sesión abierta para esta terminal"
        )
    
    try:
        # ✅ MEJORADO: Mejor manejo de transacciones
        result = await db.execute(
            text("SELECT fn_cerrar_caja(:id_terminal, :id_usuario, :efectivo_contado, :observaciones)"),
            {
                "id_terminal": str(entrada.id_terminal),
                "id_usuario": str(ctx["user_id"]),
                "efectivo_contado": float(entrada.efectivo_contado),
                "observaciones": entrada.observaciones
            }
        )
        
        id_corte = result.scalar()
        await db.commit()
        
        return {
            "success": True,
            "message": "Caja cerrada exitosamente (Corte Z)",
            "id_corte": id_corte,
            "efectivo_contado": entrada.efectivo_contado
        }
        
    except Exception as e:
        await db.rollback()  # ✅ IMPORTANTE: Rollback explícito
        raise HTTPException(status_code=500, detail=f"Error al cerrar caja: {str(e)}")

@router.post("/generar-corte-x", response_model=dict)
async def generar_corte_x(
    entrada: CorteXRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generar Corte X (parcial) sin cerrar la sesión.
    ✅ ACTUALIZADO para usar función compatible con Pascal
    """
    ctx = await obtener_contexto(db)
    
    # Verificar que hay sesión abierta
    stmt = select(SesionCaja).where(
        SesionCaja.id_terminal == entrada.id_terminal,
        SesionCaja.estado_sesion == 'ABIERTA'
    )
    sesion = await db.scalar(stmt)
    
    if not sesion:
        raise HTTPException(
            status_code=400, 
            detail="No hay sesión abierta para esta terminal"
        )
    
    try:
        # ✅ CORREGIDO: Usar función wrapper Pascal o función consolidada con persistencia
        try:
            # Intentar usar función wrapper específica para Pascal
            result = await db.execute(
                text("SELECT fn_generar_corte_x_pascal(:id_terminal, :id_usuario)"),
                {
                    "id_terminal": str(entrada.id_terminal),
                    "id_usuario": str(ctx["user_id"])
                }
            )
        except Exception:
            # Si no existe el wrapper, usar función consolidada con persistencia activada
            result = await db.execute(
                text("SELECT fn_generar_corte_x(:id_terminal, :id_usuario, :persistir)"),
                {
                    "id_terminal": str(entrada.id_terminal),
                    "id_usuario": str(ctx["user_id"]),
                    "persistir": True
                }
            )
        
        id_corte = result.scalar()
        await db.commit()
        
        return {
            "success": True,
            "message": "Corte X generado exitosamente",
            "id_corte": id_corte,
            "tipo_corte": "X"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al generar corte X: {str(e)}")

@router.get("/estado-terminal/{id_terminal}", response_model=EstadoTerminalRead)
async def obtener_estado_terminal(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener estado actual de una terminal (abierta/cerrada, sesión activa, etc.)
    ✅ ACTUALIZADO para usar vista base optimizada
    """
    stmt = text("""
        SELECT 
            id_terminal,
            codigo_terminal,
            terminal_nombre AS nombre_terminal,
            sucursal_nombre,
            estado_actual,
            id_sesion,
            fecha_apertura,
            fondo_inicial,
            usuario_apertura,
            total_ventas AS ventas_sesion_actual,
            cantidad_ventas AS cantidad_ventas_sesion,
            total_efectivo AS efectivo_sesion_actual,
            'X' AS ultimo_tipo_corte,
            CURRENT_DATE AS fecha_ultimo_corte,
            CASE WHEN proximo_numero_x > 1 THEN proximo_numero_x - 1 ELSE 0 END AS ultimo_numero_x,
            horas_sesion_abierta
        FROM vista_base_cortes 
        WHERE id_terminal = :id_terminal
    """)
    
    result = await db.execute(stmt, {"id_terminal": str(id_terminal)})
    estado = result.mappings().fetchone()
    
    if not estado:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
    
    return EstadoTerminalRead.model_validate(dict(estado))

@router.get("/datos-corte-x/{id_terminal}", response_model=DatosCorteXRead)
async def obtener_datos_corte_x(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener datos actuales para generar Corte X.
    ✅ ACTUALIZADO para usar vista compatible con Pascal
    """
    stmt = text("""
        SELECT * FROM vista_corte_x_pascal 
        WHERE id_terminal = :id_terminal
    """)
    
    result = await db.execute(stmt, {"id_terminal": str(id_terminal)})
    datos = result.mappings().fetchone()
    
    if not datos:
        # Fallback a vista original si la vista Pascal no existe
        stmt = text("""
            SELECT 
                id_terminal,
                codigo_terminal,
                terminal_nombre AS nombre_terminal,
                id_sesion,
                fecha_apertura,
                fondo_inicial,
                usuario_apertura,
                cantidad_ventas,
                total_ventas,
                subtotal_ventas,
                impuestos_ventas,
                descuentos_ventas,
                total_efectivo,
                total_tarjeta,
                total_transferencia,
                total_otros,
                efectivo_esperado,
                fecha_corte,
                proximo_numero_x,
                inicio_periodo,
                fin_periodo
            FROM vista_corte_x 
            WHERE id_terminal = :id_terminal
        """)
        
        result = await db.execute(stmt, {"id_terminal": str(id_terminal)})
        datos = result.mappings().fetchone()
    
    if not datos:
        raise HTTPException(
            status_code=400, 
            detail="No hay sesión abierta para esta terminal o no se encontraron datos"
        )
    
    return DatosCorteXRead.model_validate(dict(datos))

# =====================================================
# ENDPOINTS SIN CAMBIOS (MANTENER ORIGINALES)
# =====================================================

@router.get("/historial-cortes/{id_terminal}", response_model=List[CorteCajaRead])
async def obtener_historial_cortes(
    id_terminal: UUID,
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (YYYY-MM-DD)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (YYYY-MM-DD)"),
    tipo_corte: Optional[str] = Query(None, regex="^[XZ]$", description="Tipo de corte: X o Z"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener historial de cortes de una terminal con filtros opcionales.
    """
    stmt = select(CorteCaja).where(CorteCaja.id_terminal == id_terminal)
    
    if fecha_desde:
        stmt = stmt.where(func.date(CorteCaja.fecha_corte) >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(func.date(CorteCaja.fecha_corte) <= fecha_hasta)
    if tipo_corte:
        stmt = stmt.where(CorteCaja.tipo_corte == tipo_corte)
    
    stmt = stmt.order_by(CorteCaja.fecha_corte.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    cortes = result.scalars().all()
    
    return [CorteCajaRead.model_validate(corte) for corte in cortes]

@router.get("/movimientos-efectivo/{id_sesion}", response_model=List[MovimientoEfectivoRead])
async def obtener_movimientos_efectivo(
    id_sesion: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener todos los movimientos de efectivo de una sesión específica.
    """
    stmt = select(MovimientoEfectivo).where(
        MovimientoEfectivo.id_sesion == id_sesion
    ).order_by(MovimientoEfectivo.fecha_movimiento.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    movimientos = result.scalars().all()
    
    return [MovimientoEfectivoRead.model_validate(mov) for mov in movimientos]

@router.get("/sesiones-terminal/{id_terminal}", response_model=List[SesionCajaRead])
async def obtener_sesiones_terminal(
    id_terminal: UUID,
    estado: Optional[str] = Query(None, regex="^(ABIERTA|CERRADA|EN_PROCESO_CIERRE)$"),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener historial de sesiones de una terminal.
    """
    stmt = select(SesionCaja).where(SesionCaja.id_terminal == id_terminal)
    
    if estado:
        stmt = stmt.where(SesionCaja.estado_sesion == estado)
    if fecha_desde:
        stmt = stmt.where(func.date(SesionCaja.fecha_apertura) >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(func.date(SesionCaja.fecha_apertura) <= fecha_hasta)
    
    stmt = stmt.order_by(SesionCaja.fecha_apertura.desc()).offset(skip).limit(limit)
    
    result = await db.execute(stmt)
    sesiones = result.scalars().all()
    
    return [SesionCajaRead.model_validate(sesion) for sesion in sesiones]

@router.get("/corte-detalle/{id_corte}", response_model=CorteCajaRead)
async def obtener_detalle_corte(
    id_corte: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener detalles completos de un corte específico.
    """
    stmt = select(CorteCaja).where(CorteCaja.id_corte == id_corte)
    result = await db.execute(stmt)
    corte = result.scalar_one_or_none()
    
    if not corte:
        raise HTTPException(status_code=404, detail="Corte no encontrado")
    
    return CorteCajaRead.model_validate(corte)

@router.put("/marcar-impreso/{id_corte}", response_model=dict)
async def marcar_corte_impreso(
    id_corte: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Marcar un corte como impreso.
    """
    stmt = select(CorteCaja).where(CorteCaja.id_corte == id_corte)
    result = await db.execute(stmt)
    corte = result.scalar_one_or_none()
    
    if not corte:
        raise HTTPException(status_code=404, detail="Corte no encontrado")
    
    corte.impreso = True
    await db.commit()
    
    return {
        "success": True,
        "message": "Corte marcado como impreso"
    }

@router.get("/resumen-caja-hoy/{id_terminal}", response_model=dict)
async def obtener_resumen_caja_hoy(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener resumen rápido de la caja del día actual.
    ✅ ACTUALIZADO para usar vista base optimizada
    """
    stmt = text("""
        SELECT * FROM vista_base_cortes 
        WHERE id_terminal = :id_terminal
    """)
    
    result = await db.execute(stmt, {"id_terminal": str(id_terminal)})
    resumen = result.mappings().fetchone()
    
    if not resumen:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")
    
    return {
        "success": True,
        "data": dict(resumen)
    }

# =====================================================
# AGREGAR A sesion_caja.py - MODELO PARA CORTE Z
# =====================================================

class DatosCorteZRead(BaseModel):
    # Datos básicos de terminal
    id_terminal: UUID
    codigo_terminal: str
    nombre_terminal: str
    
    # Datos de sesión
    id_sesion: UUID
    fecha_apertura: datetime
    fecha_cierre: datetime
    
    # Usuarios
    usuario_apertura: str
    usuario_cierre: str
    
    # Datos financieros de ventas (SOLO COMPLETADAS)
    cantidad_ventas: int
    total_ventas: Decimal
    subtotal_ventas: Decimal
    impuestos_ventas: Decimal
    descuentos_ventas: Decimal
    
    # Formas de pago (separadas correctamente)
    total_efectivo: Decimal
    total_tarjeta: Decimal
    total_transferencia: Decimal
    total_monedero: Decimal        # Código 05 - separado
    total_apartado: Decimal        # Código 98 - solo anticipos
    
    # Datos específicos de Corte Z (Cierre)
    fondo_inicial: Decimal
    efectivo_sistema: Decimal      # Calculado por sistema
    efectivo_contado: Decimal      # Contado físicamente
    diferencia_efectivo: Decimal   # Sistema - Contado
    observaciones_cierre: Optional[str]
    
    # Datos de período
    inicio_periodo: datetime
    fin_periodo: datetime
    duracion_sesion_horas: Decimal
    
    model_config = {"from_attributes": True}

# =====================================================
# AGREGAR A sesion_caja.py - ENDPOINT DATOS CORTE Z
# =====================================================

@router.get("/datos-corte-z/{id_terminal}", response_model=DatosCorteZRead)
async def obtener_datos_corte_z(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtener datos del último Corte Z (sesión cerrada) de una terminal.
    """
    stmt = text("""
        SELECT 
            sc.id_terminal,
            t.codigo AS codigo_terminal,
            t.nombre AS nombre_terminal,
            sc.id_sesion,
            sc.fecha_apertura,
            sc.fecha_cierre,
            ua.nombre AS usuario_apertura,
            uc.nombre AS usuario_cierre,
            
            -- Datos de ventas del día (desde totales calculados)
            COALESCE(tv.cantidad_ventas, 0) AS cantidad_ventas,
            COALESCE(tv.total_ventas, 0.00) AS total_ventas,
            COALESCE(tv.subtotal_ventas, 0.00) AS subtotal_ventas,
            COALESCE(tv.impuestos_ventas, 0.00) AS impuestos_ventas,
            COALESCE(tv.descuentos_ventas, 0.00) AS descuentos_ventas,
            
            -- Formas de pago (separadas correctamente)
            COALESCE(tfp.total_efectivo, 0.00) AS total_efectivo,
            COALESCE(tfp.total_tarjeta, 0.00) AS total_tarjeta,
            COALESCE(tfp.total_transferencia, 0.00) AS total_transferencia,
            COALESCE(tfp.total_monedero, 0.00) AS total_monedero,
            COALESCE(tfp.total_apartado, 0.00) AS total_apartado,
            
            -- Datos específicos de Corte Z
            sc.fondo_inicial,
            sc.efectivo_sistema,
            sc.efectivo_contado,
            sc.diferencia_efectivo,
            sc.observaciones_cierre,
            
            -- Período de la sesión
            sc.fecha_apertura AS inicio_periodo,
            sc.fecha_cierre AS fin_periodo,
            EXTRACT(epoch FROM sc.fecha_cierre - sc.fecha_apertura) / 3600.0 AS duracion_sesion_horas

        FROM sesion_caja sc
        INNER JOIN terminal t ON sc.id_terminal = t.id_terminal
        INNER JOIN usuario ua ON sc.id_usuario_apertura = ua.id_usuario
        LEFT JOIN usuario uc ON sc.id_usuario_cierre = uc.id_usuario
        
        -- Obtener totales de ventas del día de cierre (SOLO COMPLETADAS)
        LEFT JOIN (
            SELECT 
                v.id_terminal,
                COUNT(v.id_venta) AS cantidad_ventas,
                SUM(v.total) AS total_ventas,
                SUM(v.subtotal) AS subtotal_ventas,
                SUM(v.impuesto) AS impuestos_ventas,
                SUM(v.descuento) AS descuentos_ventas
            FROM venta v
            WHERE v.estado_venta = 'COMPLETADA'  -- Solo ventas completadas
            AND DATE(v.fecha_venta) = (
                SELECT DATE(sc2.fecha_cierre) 
                FROM sesion_caja sc2 
                WHERE sc2.id_terminal = :id_terminal 
                AND sc2.estado_sesion = 'CERRADA'
                ORDER BY sc2.fecha_cierre DESC 
                LIMIT 1
            )
            GROUP BY v.id_terminal
        ) tv ON sc.id_terminal = tv.id_terminal
        
        -- Obtener totales por forma de pago del día de cierre (SEPARADOS CORRECTAMENTE)
        LEFT JOIN (
            SELECT 
                v.id_terminal,
                -- Efectivo (código 01)
                SUM(CASE WHEN cfp.nombre = '01' THEN p.monto ELSE 0 END) AS total_efectivo,
                -- Tarjetas (códigos 04, 28)
                SUM(CASE WHEN cfp.nombre IN ('04', '28') THEN p.monto ELSE 0 END) AS total_tarjeta,
                -- Transferencias (código 03)
                SUM(CASE WHEN cfp.nombre = '03' THEN p.monto ELSE 0 END) AS total_transferencia,
                -- Monedero electrónico (código 05) - SEPARADO
                SUM(CASE WHEN cfp.nombre = '05' THEN p.monto ELSE 0 END) AS total_monedero,
                -- Apartados (código 98) - SOLO ANTICIPOS - SEPARADO
                SUM(CASE WHEN cfp.nombre = '98' THEN p.monto ELSE 0 END) AS total_apartado
            FROM venta v
            INNER JOIN pago p ON v.id_venta = p.id_venta
            INNER JOIN cat_forma_pago cfp ON p.id_forma_pago = cfp.id_forma_pago
            WHERE DATE(v.fecha_venta) = (
                SELECT DATE(sc3.fecha_cierre) 
                FROM sesion_caja sc3 
                WHERE sc3.id_terminal = :id_terminal 
                AND sc3.estado_sesion = 'CERRADA'
                ORDER BY sc3.fecha_cierre DESC 
                LIMIT 1
            )
            -- INCLUIR TODOS LOS PAGOS (completadas y apartados)
            GROUP BY v.id_terminal
        ) tfp ON sc.id_terminal = tfp.id_terminal

        WHERE sc.id_terminal = :id_terminal
        AND sc.estado_sesion = 'CERRADA'
        ORDER BY sc.fecha_cierre DESC
        LIMIT 1
    """)
    
    result = await db.execute(stmt, {"id_terminal": str(id_terminal)})
    datos = result.mappings().fetchone()
    
    if not datos:
        raise HTTPException(
            status_code=400, 
            detail="No se encontró ningún Corte Z (sesión cerrada) para esta terminal"
        )
    
    return DatosCorteZRead.model_validate(dict(datos))