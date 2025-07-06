# marca.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Marca.
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
class Marca(Base):
    __tablename__ = "cat_marca"  # Nombre de la tabla en la BD

    # Identificador principal generado por la función gen_random_uuid() en la BD
    id_marca = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    # Nombre descriptivo de la marca (no nulo)
    nombre = Column(String(80), nullable=False)
    # Descripción opcional
    descripcion = Column(Text)
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
    # Auditoría: quién creó y modificó la marca (UUIDs)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    # Relación multiempresa: tenant actual (RLS)
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    # Estado de la marca (activo/inactivo) con default en BD
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class MarcaBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Marca.
    """
    nombre: str                           # Nombre obligatorio
    descripcion: Optional[str] = None    # Descripción opcional

class MarcaCreate(MarcaBase):
    """Esquema para creación; hereda nombre y descripción."""
    pass

class MarcaUpdate(MarcaBase):
    """Esquema para actualización; hereda nombre y descripción."""
    pass

class MarcaRead(MarcaBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_marca: UUID
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
async def listar_marcas(
    nombre: Optional[str] = Query(None),      # Filtro por nombre (ilike)
    skip: int = 0,                            # Paginación: offset
    limit: int = 100,                         # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista marcas en estado "activo" con paginación y filtro opcional.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtro de estado y nombre
    stmt = select(Marca).where(Marca.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Marca.nombre.ilike(f"%{nombre}%"))

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
        "data": [MarcaRead.model_validate(m) for m in data]
    }

@router.get("/{id_marca}", response_model=MarcaRead)
async def obtener_marca(
    id_marca: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una marca por su ID, sólo si está en estado "activo".
    """
    # 1) Identificador del estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Marca).where(
        Marca.id_marca  == id_marca,
        Marca.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    marca = result.scalar_one_or_none()

    # 3) Si no existe o no es activo, devolver 404
    if not marca:
        raise HTTPException(status_code=404, detail="Marca no encontrada")

    # 4) Retornar objeto serializado
    return MarcaRead.model_validate(marca)

@router.post("/", response_model=dict, status_code=201)
async def crear_marca(
    entrada: MarcaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva marca. Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)

    # 2) Construir instancia ORM sin id_estado (se aplica server_default)
    nueva = Marca(
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
    return {"success": True, "data": MarcaRead.model_validate(nueva)}

@router.put("/{id_marca}", response_model=dict)
async def actualizar_marca(
    id_marca: UUID,
    entrada: MarcaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza nombre y descripción de una marca en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga únicamente si la marca existe y está activa
    stmt = select(Marca).where(
        Marca.id_marca  == id_marca,
        Marca.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    marca = result.scalar_one_or_none()
    if not marca:
        raise HTTPException(status_code=404, detail="Marca no encontrada")

    # 3) Aplicar cambios y auditoría
    ctx = await obtener_contexto(db)
    marca.nombre      = entrada.nombre
    marca.descripcion = entrada.descripcion
    marca.modified_by = ctx["user_id"]

    # 4) Flush + Refresh para respetar RLS
    await db.flush()
    await db.refresh(marca)

    # 5) Confirmar cambios
    await db.commit()

    return {"success": True, "data": MarcaRead.model_validate(marca)}

@router.delete("/{id_marca}", status_code=200)
async def eliminar_marca(id_marca: UUID, db: AsyncSession = Depends(get_async_db)):
    """
    Elimina físicamente una marca. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Marca).where(Marca.id_marca == id_marca))
    marca = result.scalar_one_or_none()
    if not marca:
        raise HTTPException(status_code=404, detail="Marca no encontrada")

    # 2) Ejecutar DELETE
    await db.execute(delete(Marca).where(Marca.id_marca == id_marca))

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Marca eliminada permanentemente"}

# ===============================================
# AGREGAR AL FINAL DE marca.py
# ===============================================
@router.get("/combo", response_model=dict)
async def listar_marcas_combo(db: AsyncSession = Depends(get_async_db)):
    """Endpoint optimizado para llenar ComboBox de marcas"""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    query = select(Marca.id_marca, Marca.nombre).where(
        Marca.id_estado == estado_activo_id
    ).order_by(Marca.nombre)
    
    result = await db.execute(query)
    marcas = [{"id": str(row[0]), "nombre": row[1]} for row in result]
    
    return {"success": True, "data": marcas}