# auditoria.py
# -----------------------------------------------
# Sistema completo de Auditoría y Trazabilidad
# Endpoints para reportes de auditoría empresarial
# -----------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

# Importaciones del proyecto
from db import get_async_db
from utils.contexto import obtener_contexto

# =====================================================
# SCHEMAS PYDANTIC PARA AUDITORÍA
# =====================================================

class AuditoriaGeneralRead(BaseModel):
    tabla: str
    registro_id: UUID
    descripcion_registro: str
    usuario_creacion: Optional[str]
    fecha_creacion: datetime
    usuario_modificacion: Optional[str]
    fecha_modificacion: datetime
    detalle_accion: str
    
    model_config = {"from_attributes": True}

class AuditoriaPorUsuarioRead(BaseModel):
    id_usuario: UUID
    nombre_usuario: str
    login_usuario: str
    total_creaciones: int
    total_modificaciones: int
    ultima_actividad: Optional[datetime]
    primera_actividad: Optional[datetime]
    tablas_modificadas: Optional[str]
    
    model_config = {"from_attributes": True}

class AuditoriaVentaModificadaRead(BaseModel):
    id_venta: UUID
    numero_folio: str
    fecha_venta: datetime
    total: Decimal
    estado_venta: str
    cliente: Optional[str]
    terminal: str
    usuario_creacion: Optional[str]
    fecha_creacion: datetime
    usuario_modificacion: Optional[str]
    fecha_modificacion: datetime
    minutos_transcurridos: Optional[float]
    tipo_modificacion: str
    
    model_config = {"from_attributes": True}

class AuditoriaProductoRead(BaseModel):
    id_producto: UUID
    sku: str
    nombre: str
    precio_base: Decimal
    marca: Optional[str]
    usuario_creacion: Optional[str]
    fecha_creacion: datetime
    usuario_modificacion: Optional[str]
    fecha_modificacion: datetime
    tipo_modificacion: str
    horas_transcurridas: Optional[float]
    
    model_config = {"from_attributes": True}

class AuditoriaSesionCajaRead(BaseModel):
    id_sesion: UUID
    codigo_terminal: str
    nombre_terminal: str
    sucursal: str
    usuario_apertura: Optional[str]
    usuario_cierre: Optional[str]
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime]
    fondo_inicial: Decimal
    efectivo_sistema: Optional[Decimal]
    efectivo_contado: Optional[Decimal]
    diferencia_efectivo: Optional[Decimal]
    estado_sesion: str
    observaciones_cierre: Optional[str]
    horas_sesion: Optional[float]
    alerta: str
    
    model_config = {"from_attributes": True}

class AlertaAuditoriaRead(BaseModel):
    tipo_alerta: str
    prioridad: str
    descripcion: str
    fecha_alerta: datetime
    usuario_responsable: Optional[str]
    terminal: str
    
    model_config = {"from_attributes": True}

class EstadisticasAuditoriaRead(BaseModel):
    total_registros_auditados: int
    usuarios_activos: int
    modificaciones_ultima_semana: int
    alertas_pendientes: int
    tablas_con_actividad: int
    
    model_config = {"from_attributes": True}

# =====================================================
# ROUTER Y ENDPOINTS
# =====================================================

router = APIRouter()

@router.get("/general", response_model=dict)
async def obtener_auditoria_general(
    tabla: Optional[str] = Query(None, description="Filtrar por tabla específica"),
    usuario: Optional[str] = Query(None, description="Filtrar por usuario"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene el log general de auditoría del sistema.
    Incluye todas las operaciones CREATE/UPDATE de todas las tablas.
    """
    
    # Construir query base
    query = """
        SELECT * FROM vista_auditoria_general 
        WHERE id_empresa = :empresa_id
    """
    params = {"empresa_id": (await obtener_contexto(db))["tenant_id"]}
    
    # Aplicar filtros
    if tabla:
        query += " AND tabla = :tabla"
        params["tabla"] = tabla
    
    if usuario:
        query += " AND (usuario_creacion ILIKE :usuario OR usuario_modificacion ILIKE :usuario)"
        params["usuario"] = f"%{usuario}%"
    
    if fecha_desde:
        query += " AND fecha_modificacion >= :fecha_desde"
        params["fecha_desde"] = fecha_desde
    
    if fecha_hasta:
        query += " AND fecha_modificacion <= :fecha_hasta"
        params["fecha_hasta"] = fecha_hasta
    
    # Query para total
    count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()
    
    # Query principal con paginación
    query += " ORDER BY fecha_modificacion DESC LIMIT :limit OFFSET :skip"
    params.update({"limit": limit, "skip": skip})
    
    result = await db.execute(text(query), params)
    data = [dict(row._mapping) for row in result]
    
    return {
        "success": True,
        "total_count": total,
        "data": data
    }

@router.get("/por-usuario", response_model=dict)
async def obtener_auditoria_por_usuario(
    usuario_id: Optional[UUID] = Query(None, description="ID específico de usuario"),
    activos_solamente: bool = Query(True, description="Solo usuarios con actividad reciente"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Estadísticas de actividad por usuario.
    Muestra productividad y patrones de uso.
    """
    
    query = """
        SELECT * FROM vista_auditoria_por_usuario 
        WHERE 1=1
    """
    params = {}
    
    if usuario_id:
        query += " AND id_usuario = :usuario_id"
        params["usuario_id"] = str(usuario_id)
    
    if activos_solamente:
        query += " AND ultima_actividad >= CURRENT_DATE - INTERVAL '30 days'"
    
    # Total count
    count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()
    
    # Query principal
    query += " ORDER BY ultima_actividad DESC NULLS LAST LIMIT :limit OFFSET :skip"
    params.update({"limit": limit, "skip": skip})
    
    result = await db.execute(text(query), params)
    data = [dict(row._mapping) for row in result]
    
    return {
        "success": True,
        "total_count": total,
        "data": data
    }

@router.get("/ventas-modificadas", response_model=dict)
async def obtener_ventas_modificadas(
    tipo_modificacion: Optional[str] = Query(None, description="Tipo de modificación"),
    usuario: Optional[str] = Query(None, description="Usuario que modificó"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Auditoría específica de ventas que han sido modificadas.
    Detecta posibles manipulaciones o errores.
    """
    
    query = """
        SELECT * FROM vista_auditoria_ventas_modificadas 
        WHERE 1=1
    """
    params = {}
    
    if tipo_modificacion:
        query += " AND tipo_modificacion = :tipo_modificacion"
        params["tipo_modificacion"] = tipo_modificacion
    
    if usuario:
        query += " AND usuario_modificacion ILIKE :usuario"
        params["usuario"] = f"%{usuario}%"
    
    if fecha_desde:
        query += " AND fecha_modificacion >= :fecha_desde"
        params["fecha_desde"] = fecha_desde
    
    if fecha_hasta:
        query += " AND fecha_modificacion <= :fecha_hasta"
        params["fecha_hasta"] = fecha_hasta
    
    # Total count
    count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()
    
    # Query principal
    query += " ORDER BY fecha_modificacion DESC LIMIT :limit OFFSET :skip"
    params.update({"limit": limit, "skip": skip})
    
    result = await db.execute(text(query), params)
    data = [dict(row._mapping) for row in result]
    
    return {
        "success": True,
        "total_count": total,
        "data": data
    }

@router.get("/sesiones-caja", response_model=dict)
async def obtener_auditoria_sesiones_caja(
    terminal_id: Optional[UUID] = Query(None, description="ID del terminal"),
    estado: Optional[str] = Query(None, description="Estado de la sesión"),
    con_alertas: bool = Query(False, description="Solo sesiones con alertas"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Auditoría completa de sesiones de caja.
    Incluye alertas automáticas por irregularidades.
    """
    
    query = """
        SELECT * FROM vista_auditoria_sesiones_caja 
        WHERE 1=1
    """
    params = {}
    
    if terminal_id:
        query += " AND id_terminal = :terminal_id"
        params["terminal_id"] = str(terminal_id)
    
    if estado:
        query += " AND estado_sesion = :estado"
        params["estado"] = estado
    
    if con_alertas:
        query += " AND alerta != 'NORMAL'"
    
    if fecha_desde:
        query += " AND fecha_apertura >= :fecha_desde"
        params["fecha_desde"] = fecha_desde
    
    if fecha_hasta:
        query += " AND fecha_apertura <= :fecha_hasta"
        params["fecha_hasta"] = fecha_hasta
    
    # Total count
    count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()
    
    # Query principal
    query += " ORDER BY fecha_apertura DESC LIMIT :limit OFFSET :skip"
    params.update({"limit": limit, "skip": skip})
    
    result = await db.execute(text(query), params)
    data = [dict(row._mapping) for row in result]
    
    return {
        "success": True,
        "total_count": total,
        "data": data
    }

@router.get("/alertas", response_model=dict)
async def obtener_alertas_auditoria(
    prioridad: Optional[Literal["CRÍTICA", "ALTA", "MEDIA"]] = Query(None, description="Nivel de prioridad"),
    tipo: Optional[str] = Query(None, description="Tipo de alerta"),
    dias_atras: int = Query(7, ge=1, le=365, description="Días hacia atrás para buscar"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Alertas automáticas del sistema de auditoría.
    Detecta situaciones que requieren atención inmediata.
    """
    
    query = """
        SELECT * FROM vista_alertas_auditoria 
        WHERE fecha_alerta >= CURRENT_DATE - INTERVAL :dias_atras
    """
    params = {"dias_atras": f"{dias_atras} days"}
    
    if prioridad:
        query += " AND prioridad = :prioridad"
        params["prioridad"] = prioridad
    
    if tipo:
        query += " AND tipo_alerta = :tipo"
        params["tipo"] = tipo
    
    # Total count
    count_query = f"SELECT COUNT(*) FROM ({query}) as subquery"
    total_result = await db.execute(text(count_query), params)
    total = total_result.scalar()
    
    # Query principal
    query += " ORDER BY prioridad DESC, fecha_alerta DESC LIMIT :limit OFFSET :skip"
    params.update({"limit": limit, "skip": skip})
    
    result = await db.execute(text(query), params)
    data = [dict(row._mapping) for row in result]
    
    # Agrupar por prioridad para resumen
    resumen = {}
    for row in data:
        prioridad_item = row["prioridad"]
        if prioridad_item not in resumen:
            resumen[prioridad_item] = 0
        resumen[prioridad_item] += 1
    
    return {
        "success": True,
        "total_count": total,
        "resumen_por_prioridad": resumen,
        "data": data
    }

@router.get("/estadisticas", response_model=EstadisticasAuditoriaRead)
async def obtener_estadisticas_auditoria(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Estadísticas generales del sistema de auditoría.
    Dashboard ejecutivo de trazabilidad.
    """
    
    ctx = await obtener_contexto(db)
    
    # Total de registros auditados
    total_query = """
        SELECT COUNT(*) FROM vista_auditoria_general 
        WHERE id_empresa = :empresa_id
    """
    total_result = await db.execute(text(total_query), {"empresa_id": ctx["tenant_id"]})
    total_registros = total_result.scalar()
    
    # Usuarios activos (con actividad en últimos 30 días)
    usuarios_query = """
        SELECT COUNT(*) FROM vista_auditoria_por_usuario 
        WHERE ultima_actividad >= CURRENT_DATE - INTERVAL '30 days'
    """
    usuarios_result = await db.execute(text(usuarios_query))
    usuarios_activos = usuarios_result.scalar()
    
    # Modificaciones en última semana
    modificaciones_query = """
        SELECT COUNT(*) FROM vista_auditoria_general 
        WHERE fecha_modificacion >= CURRENT_DATE - INTERVAL '7 days'
        AND id_empresa = :empresa_id
    """
    mod_result = await db.execute(text(modificaciones_query), {"empresa_id": ctx["tenant_id"]})
    modificaciones_semana = mod_result.scalar()
    
    # Alertas pendientes
    alertas_query = """
        SELECT COUNT(*) FROM vista_alertas_auditoria 
        WHERE fecha_alerta >= CURRENT_DATE - INTERVAL '7 days'
    """
    alertas_result = await db.execute(text(alertas_query))
    alertas_pendientes = alertas_result.scalar()
    
    # Tablas con actividad
    tablas_query = """
        SELECT COUNT(DISTINCT tabla) FROM vista_auditoria_general 
        WHERE id_empresa = :empresa_id
    """
    tablas_result = await db.execute(text(tablas_query), {"empresa_id": ctx["tenant_id"]})
    tablas_actividad = tablas_result.scalar()
    
    return EstadisticasAuditoriaRead(
        total_registros_auditados=total_registros,
        usuarios_activos=usuarios_activos,
        modificaciones_ultima_semana=modificaciones_semana,
        alertas_pendientes=alertas_pendientes,
        tablas_con_actividad=tablas_actividad
    )

@router.get("/timeline/{registro_id}", response_model=dict)
async def obtener_timeline_registro(
    registro_id: UUID,
    tabla: str = Query(..., description="Nombre de la tabla"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Timeline completo de un registro específico.
    Muestra historial detallado de cambios.
    """
    
    query = """
        SELECT * FROM vista_auditoria_general 
        WHERE registro_id = :registro_id AND tabla = :tabla
        ORDER BY fecha_modificacion ASC
    """
    
    result = await db.execute(text(query), {
        "registro_id": str(registro_id),
        "tabla": tabla
    })
    data = [dict(row._mapping) for row in result]
    
    if not data:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró historial para {tabla} con ID {registro_id}"
        )
    
    return {
        "success": True,
        "registro_id": registro_id,
        "tabla": tabla,
        "total_eventos": len(data),
        "timeline": data
    }