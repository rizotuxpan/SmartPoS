# terminal.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Terminal.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional                                      # Tipos para anotaciones
from uuid import UUID                                            # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, DateTime, func, select, text, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID       # Tipo UUID específico de PostgreSQL
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
class Terminal(Base):
    __tablename__ = "terminal"

    id_terminal = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_sucursal = Column(
        PG_UUID(as_uuid=True),
        nullable=False
    )
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    codigo = Column(String(30), nullable=False)
    nombre = Column(String(120), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
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

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class TerminalBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Terminal.
    """
    id_sucursal: UUID
    codigo: str
    nombre: str

class TerminalCreate(TerminalBase):
    """Esquema para creación; hereda id_sucursal, código y nombre."""
    pass

class TerminalUpdate(TerminalBase):
    """Esquema para actualización; hereda id_sucursal, código y nombre."""
    pass

class TerminalRead(TerminalBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_terminal: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

class TerminalIdentificacion(BaseModel):
    """
    Esquema simplificado que retorna únicamente id_terminal y nombre.
    Usado para identificación básica de terminales.
    """
    id_terminal: UUID
    nombre: str

    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_terminales(
    id_sucursal: Optional[UUID] = Query(None),  # Filtro por sucursal
    codigo: Optional[str]    = Query(None),     # Filtro por código (ilike)
    nombre: Optional[str]    = Query(None),     # Filtro por nombre (ilike)
    skip: int                = 0,              # Paginación: offset
    limit: int               = 100,            # Paginación: máximo de registros
    db: AsyncSession         = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista terminales en estado "activo" con paginación y filtros opcionales.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtros
    stmt = select(Terminal).where(Terminal.id_estado == estado_activo_id)
    if id_sucursal:
        stmt = stmt.where(Terminal.id_sucursal == id_sucursal)
    if codigo:
        stmt = stmt.where(Terminal.codigo.ilike(f"%{codigo}%"))
    if nombre:
        stmt = stmt.where(Terminal.nombre.ilike(f"%{nombre}%"))

    # 3) Contar total para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Serializar y devolver
    return {
        "success": True,
        "total_count": total,
        "data": [TerminalRead.model_validate(t) for t in data]
    }

@router.get("/search", response_model=TerminalIdentificacion)  # ← MOVER AQUÍ (ANTES de /{id_terminal})
async def buscar_terminal_por_sucursal_y_codigo(
    id_sucursal: UUID = Query(..., description="ID de la sucursal"),
    codigo: str = Query(..., description="Código de la terminal"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Busca una terminal específica por sucursal y código.
    Retorna únicamente id_terminal y nombre de la terminal encontrada.
    Solo considera terminales en estado "activo".
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)  # ← CORREGIDO: "act" no "ACT"
    
    # 2) Construir consulta con filtros exactos
    stmt = select(Terminal).where(
        Terminal.id_sucursal == id_sucursal,
        Terminal.codigo == codigo,
        Terminal.id_estado == estado_activo_id
    )
    
    # 3) Ejecutar consulta
    result = await db.execute(stmt)
    terminal = result.scalar_one_or_none()
    
    # 4) Si no existe, devolver 404
    if not terminal:
        raise HTTPException(
            status_code=404, 
            detail=f"Terminal no encontrada'"
        )
    
    # 5) Retornar solo id_terminal y nombre
    return TerminalIdentificacion.model_validate(terminal)

@router.get("/{id_terminal}", response_model=TerminalRead)  # ← ESTE VA DESPUÉS de /search
async def obtener_terminal(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una terminal por su ID, sólo si está en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Terminal).where(
        Terminal.id_terminal == id_terminal,
        Terminal.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    terminal = result.scalar_one_or_none()

    # 3) Si no existe o no está activa, devolver 404
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")

    # 4) Retornar serializado
    return TerminalRead.model_validate(terminal)

@router.post("/", response_model=dict, status_code=201)
async def crear_terminal(
    entrada: TerminalCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva terminal. Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)

    # 2) Construir instancia ORM
    nueva = Terminal(
        id_sucursal  = entrada.id_sucursal,
        codigo       = entrada.codigo,
        nombre       = entrada.nombre,
        created_by   = ctx["user_id"],
        modified_by  = ctx["user_id"],
        id_empresa   = ctx["tenant_id"]
    )
    db.add(nueva)

    # 3) Insert + Refresh
    await db.flush()
    await db.refresh(nueva)
    await db.commit()

    # 4) Devolver datos completos
    return {"success": True, "data": TerminalRead.model_validate(nueva)}

@router.put("/{id_terminal}", response_model=dict)
async def actualizar_terminal(
    id_terminal: UUID,
    entrada: TerminalUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de una terminal en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga sólo si existe y está activa
    stmt = select(Terminal).where(
        Terminal.id_terminal == id_terminal,
        Terminal.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    terminal = result.scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")

    # 3) Aplicar cambios y auditoría
    ctx = await obtener_contexto(db)
    terminal.id_sucursal = entrada.id_sucursal
    terminal.codigo      = entrada.codigo
    terminal.nombre      = entrada.nombre
    terminal.modified_by = ctx["user_id"]

    # 4) Flush + Refresh
    await db.flush()
    await db.refresh(terminal)
    await db.commit()

    return {"success": True, "data": TerminalRead.model_validate(terminal)}

@router.delete("/{id_terminal}", status_code=200)
async def eliminar_terminal(
    id_terminal: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una terminal. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Terminal).where(Terminal.id_terminal == id_terminal))
    terminal = result.scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=404, detail="Terminal no encontrada")

    # 2) Ejecutar DELETE
    await db.execute(delete(Terminal).where(Terminal.id_terminal == id_terminal))
    await db.commit()

    # 3) Responder al cliente
    return {"success": True, "message": "Terminal eliminada permanentemente"}