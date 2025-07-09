# regimenfiscal.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Régimen Fiscal.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query # FastAPI para rutas y dependencias
from pydantic import BaseModel                               # Pydantic para schemas de entrada/salida
from typing import Optional, List                            # Tipos para anotaciones
from uuid import UUID                                        # UUID para identificadores únicos
from datetime import datetime                                # Fecha y hora
from sqlalchemy import Column, String, DateTime, func, select, text, insert, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID   # Tipo UUID específico de PostgreSQL
from sqlalchemy.ext.asyncio import AsyncSession              # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class RegimenFiscal(Base):
    __tablename__ = "regimenfiscal"  # Nombre de la tabla en la BD

    # Identificador principal de 3 caracteres (clave del SAT)
    id_regimenfiscal = Column(
        String(3),
        primary_key=True
    )
    # Nombre descriptivo del régimen fiscal (no nulo)
    nombre = Column(String(120), nullable=False)
    # Timestamps gestionados por PostgreSQL
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
    # Auditoría: quién creó y modificó el régimen fiscal (UUIDs)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    # Relación multiempresa: tenant actual (RLS)
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("(current_setting('app.current_tenant'::text))::uuid")
    )
    # Estado del régimen fiscal (activo/inactivo) con default en BD
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class RegimenFiscalBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Régimen Fiscal.
    """
    nombre: str                          # Nombre obligatorio

class RegimenFiscalCreate(RegimenFiscalBase):
    """Esquema para creación; incluye ID y nombre."""
    id_regimenfiscal: str               # ID de 3 caracteres obligatorio

class RegimenFiscalUpdate(RegimenFiscalBase):
    """Esquema para actualización; solo nombre."""
    pass

class RegimenFiscalRead(RegimenFiscalBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_regimenfiscal: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    modified_by: UUID
    id_empresa: UUID
    id_estado: UUID

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_regimenes_fiscales(
    nombre: Optional[str] = Query(None),      # Filtro por nombre (ilike)
    skip: int = 0,                            # Paginación: offset
    limit: int = 100,                         # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista regímenes fiscales en estado "activo" con paginación y filtro opcional.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtro de estado y nombre
    stmt = select(RegimenFiscal).where(RegimenFiscal.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(RegimenFiscal.nombre.ilike(f"%{nombre}%"))

    # 3) Contar total de registros para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Serializar y devolver
    return {
        "success": True,
        "total_count": total,
        "data": [RegimenFiscalRead.model_validate(rf) for rf in data]
    }

@router.get("/combo", response_model=dict)
async def listar_regimenes_fiscales_combo(db: AsyncSession = Depends(get_async_db)):
    """Endpoint optimizado para llenar ComboBox de regímenes fiscales"""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    query = select(RegimenFiscal.id_regimenfiscal, RegimenFiscal.nombre).where(
        RegimenFiscal.id_estado == estado_activo_id
    ).order_by(RegimenFiscal.nombre)
    
    result = await db.execute(query)
    regimenes = [{"id": row[0], "nombre": row[1]} for row in result]
    
    return {"success": True, "data": regimenes}

@router.get("/{id_regimenfiscal}", response_model=RegimenFiscalRead)
async def obtener_regimen_fiscal(
    id_regimenfiscal: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un régimen fiscal por su ID, sólo si está en estado "activo".
    """
    # 1) Identificador del estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(RegimenFiscal).where(
        RegimenFiscal.id_regimenfiscal == id_regimenfiscal,
        RegimenFiscal.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    regimen_fiscal = result.scalar_one_or_none()

    # 3) Si no existe o no es activo, devolver 404
    if not regimen_fiscal:
        raise HTTPException(status_code=404, detail="Régimen fiscal no encontrado")

    # 4) Retornar objeto serializado
    return RegimenFiscalRead.model_validate(regimen_fiscal)

@router.post("/", response_model=dict, status_code=201)
async def crear_regimen_fiscal(
    entrada: RegimenFiscalCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo régimen fiscal. Aplica RLS y defaults de servidor.
    """
    # 1) Verificar que no exista un régimen fiscal con el mismo ID
    stmt = select(RegimenFiscal).where(RegimenFiscal.id_regimenfiscal == entrada.id_regimenfiscal)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Ya existe un régimen fiscal con este ID")

    # 2) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)

    # 3) Construir instancia ORM sin id_estado (se aplica server_default)
    nuevo = RegimenFiscal(
        id_regimenfiscal=entrada.id_regimenfiscal,
        nombre=entrada.nombre,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"],
        id_empresa=ctx["tenant_id"]
    )
    db.add(nuevo)

    # 4) Ejecutar INSERT y refrescar antes de commit para respetar RLS
    await db.flush()        # Realiza INSERT RETURNING …
    await db.refresh(nuevo) # Ejecuta SELECT dentro de la misma tx

    # 5) Finalizar tx
    await db.commit()

    # 6) Devolver datos completos
    return {"success": True, "data": RegimenFiscalRead.model_validate(nuevo)}

@router.put("/{id_regimenfiscal}", response_model=dict)
async def actualizar_regimen_fiscal(
    id_regimenfiscal: str,
    entrada: RegimenFiscalUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza nombre de un régimen fiscal en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga únicamente si el régimen fiscal existe y está activo
    stmt = select(RegimenFiscal).where(
        RegimenFiscal.id_regimenfiscal == id_regimenfiscal,
        RegimenFiscal.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    regimen_fiscal = result.scalar_one_or_none()
    if not regimen_fiscal:
        raise HTTPException(status_code=404, detail="Régimen fiscal no encontrado")

    # 3) Aplicar cambios y auditoría
    ctx = await obtener_contexto(db)
    regimen_fiscal.nombre = entrada.nombre
    regimen_fiscal.modified_by = ctx["user_id"]

    # 4) Flush + Refresh para respetar RLS
    await db.flush()
    await db.refresh(regimen_fiscal)

    # 5) Confirmar cambios
    await db.commit()

    return {"success": True, "data": RegimenFiscalRead.model_validate(regimen_fiscal)}

@router.delete("/{id_regimenfiscal}", status_code=200)
async def eliminar_regimen_fiscal(id_regimenfiscal: str, db: AsyncSession = Depends(get_async_db)):
    """
    Elimina físicamente un régimen fiscal. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(RegimenFiscal).where(RegimenFiscal.id_regimenfiscal == id_regimenfiscal))
    regimen_fiscal = result.scalar_one_or_none()
    if not regimen_fiscal:
        raise HTTPException(status_code=404, detail="Régimen fiscal no encontrado")

    # 2) Ejecutar DELETE
    await db.execute(delete(RegimenFiscal).where(RegimenFiscal.id_regimenfiscal == id_regimenfiscal))

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Régimen fiscal eliminado permanentemente"}