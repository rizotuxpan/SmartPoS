# forma_pago.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Forma_Pago.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query # FastAPI para rutas y dependencias
from pydantic import BaseModel                               # Pydantic para schemas de entrada/salida
from typing import Optional, List                            # Tipos para anotaciones
from uuid import UUID, uuid4                                 # UUID para identificadores únicos
from datetime import datetime                                # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, insert, delete
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
class Forma_Pago(Base):
    __tablename__ = "cat_forma_pago"  # Nombre de la tabla en la BD

    # Identificador principal generado por la función gen_random_uuid() en la BD
    id_forma_pago = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    # Nombre descriptivo de la forma de pago (no nulo)
    nombre = Column(String(10), nullable=False)
    # Descripción obligatoria
    descripcion = Column(String(50), nullable=False)
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
    # Auditoría: quién creó y modificó la forma de pago (UUIDs)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    # Relación multiempresa: tenant actual (RLS)
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    # Estado de la forma de pago (activo/inactivo) con default en BD
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class Forma_PagoBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Forma de Pago.
    """
    nombre: str         # Nombre obligatorio
    descripcion: str    # Descripción obligatorio

class Forma_PagoCreate(Forma_PagoBase):
    """Esquema para creación; hereda nombre y descripción."""
    pass

class Forma_PagoUpdate(Forma_PagoBase):
    """Esquema para actualización; hereda nombre y descripción."""
    pass

class Forma_PagoRead(Forma_PagoBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_forma_pago: UUID
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
async def listar_forma_pago(
    nombre: Optional[str] = Query(None),      # Filtro por nombre (ilike)
    skip: int = 0,                            # Paginación: offset
    limit: int = 100,                         # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista formas de pago en estado "activo" con paginación y filtro opcional.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtro de estado y nombre
    stmt = select(Forma_Pago).where(Forma_Pago.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Forma_Pago.nombre.ilike(f"%{nombre}%"))

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
        "data": [Forma_PagoRead.model_validate(m) for m in data]
    }

@router.get("/{id_forma_pago}", response_model=Forma_PagoRead)
async def obtener_forma_pago(
    id_forma_pago: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una forma de pago por su ID, sólo si está en estado "activo".
    """
    # 1) Identificador del estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Forma_Pago).where(
        Forma_Pago.id_forma_pago  == id_forma_pago,
        Forma_Pago.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    forma_pago = result.scalar_one_or_none()

    # 3) Si no existe o no es activo, devolver 404
    if not forma_pago:
        raise HTTPException(status_code=404, detail="Forma de Pago no encontrada")

    # 4) Retornar objeto serializado
    return Forma_PagoRead.model_validate(forma_pago)

@router.post("/", response_model=dict, status_code=201)
async def crear_forma_pago(
    entrada: Forma_PagoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva forma de pago. Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)

    # 2) Construir instancia ORM sin id_estado (se aplica server_default)
    nueva = Forma_Pago(
        nombre=entrada.nombre,
        descripcion=entrada.descripcion,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"],
        id_empresa=ctx["tenant_id"]
    )
    db.add(nueva)

    # 3) Ejecutar INSERT y refrescar antes de commit para respetar RLS
    await db.flush()        # Realiza INSERT RETURNING …
    await db.refresh(nueva) # Ejecuta SELECT dentro de la misma tx

    # 4) Finalizar tx
    await db.commit()

    # 5) Devolver datos completos
    return {"success": True, "data": Forma_PagoRead.model_validate(nueva)}

@router.put("/{id_forma_pago}", response_model=dict)
async def actualizar_forma_pago(
    id_forma_pago: UUID,
    entrada: Forma_PagoUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza nombre y descripción de una forma de pago en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga únicamente si la forma de pago existe y está activa
    stmt = select(Forma_Pago).where(
        Forma_Pago.id_forma_pago  == id_forma_pago,
        Forma_Pago.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    forma_pago = result.scalar_one_or_none()
    if not forma_pago:
        raise HTTPException(status_code=404, detail="Forma de Pago no encontrada")

    # 3) Aplicar cambios y auditoría
    ctx = await obtener_contexto(db)
    forma_pago.nombre      = entrada.nombre
    forma_pago.descripcion = entrada.descripcion
    forma_pago.modified_by = ctx["user_id"]

    # 4) Flush + Refresh para respetar RLS
    await db.flush()
    await db.refresh(forma_pago)

    # 5) Confirmar cambios
    await db.commit()

    return {"success": True, "data": Forma_PagoRead.model_validate(forma_pago)}

@router.delete("/{id_forma_pago}", status_code=200)
async def eliminar_forma_pago(id_forma_pago: UUID, db: AsyncSession = Depends(get_async_db)):
    """
    Elimina físicamente una forma de pago. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Forma_Pago).where(Forma_Pago.id_forma_pago == id_forma_pago))
    forma_pago = result.scalar_one_or_none()
    if not forma_pago:
        raise HTTPException(status_code=404, detail="Forma de Pago no encontrada")

    # 2) Ejecutar DELETE
    await db.execute(delete(Forma_Pago).where(Forma_Pago.id_forma_pago == id_forma_pago))

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Forma de Pago eliminada permanentemente"}