# cliente.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Cliente.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query  # FastAPI para rutas y dependencias
from pydantic import BaseModel                                # Pydantic para schemas de entrada/salida
from typing import Optional                                    # Tipos para anotaciones
from uuid import UUID                                          # UUID para identificadores únicos
from datetime import datetime                                 # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos específicos de PostgreSQL
from sqlalchemy.ext.asyncio import AsyncSession               # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Cliente(Base):
    __tablename__ = "cliente"  # Nombre de la tabla en la BD

    id_cliente = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    nombre = Column(String(120), nullable=False)
    apellido = Column(String(120))
    razon_social = Column(String(255))
    rfc = Column(CITEXT)
    email = Column(CITEXT)
    telefono = Column(String(30))
    domicilio = Column(Text)
    colonia = Column(String(100))
    cp = Column(String(20))
    municipio = Column(String(100))
    entidad = Column(String(100))
    guid = Column(String(36))
    clave = Column(String(50))
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
class ClienteBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Cliente.
    """
    nombre: str
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    domicilio: Optional[str] = None
    colonia: Optional[str] = None
    cp: Optional[str] = None
    municipio: Optional[str] = None
    entidad: Optional[str] = None
    guid: Optional[str] = None
    clave: Optional[str] = None

class ClienteCreate(ClienteBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ClienteUpdate(ClienteBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class ClienteRead(ClienteBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_cliente: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_clientes(
    nombre: Optional[str] = Query(None),         # Filtro por nombre (ilike)
    skip: int = 0,                               # Paginación: offset
    limit: int = 100,                            # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)     # Sesión RLS inyectada
):
    """
    Lista clientes en estado "activo" con paginación y filtro opcional.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtro de estado y nombre
    stmt = select(Cliente).where(Cliente.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Cliente.nombre.ilike(f"%{nombre}%"))

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
        "data": [ClienteRead.model_validate(c) for c in data]
    }

@router.get("/{id_cliente}", response_model=ClienteRead)
async def obtener_cliente(
    id_cliente: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un cliente por su ID, sólo si está en estado "activo".
    """
    # 1) Identificador del estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Cliente).where(
        Cliente.id_cliente == id_cliente,
        Cliente.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    cliente = result.scalar_one_or_none()

    # 3) Si no existe o no es activo, devolver 404
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # 4) Retornar objeto serializado
    return ClienteRead.model_validate(cliente)

@router.post("/", response_model=dict, status_code=201)
async def crear_cliente(
    entrada: ClienteCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo cliente. Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)

    # 2) Construir instancia ORM sin id_estado (se aplica server_default)
    nuevo = Cliente(
        nombre       = entrada.nombre,
        apellido     = entrada.apellido,
        razon_social = entrada.razon_social,
        rfc          = entrada.rfc,
        email        = entrada.email,
        telefono     = entrada.telefono,
        domicilio    = entrada.domicilio,
        colonia      = entrada.colonia,
        cp           = entrada.cp,
        municipio    = entrada.municipio,
        entidad      = entrada.entidad,
        guid         = entrada.guid,
        clave        = entrada.clave,
        created_by   = ctx["user_id"],
        modified_by  = ctx["user_id"],
        id_empresa   = ctx["tenant_id"]
    )
    db.add(nuevo)

    # 3) Ejecutar INSERT y refrescar antes de commit para respetar RLS
    await db.flush()
    await db.refresh(nuevo)

    # 4) Confirmar transacción
    await db.commit()

    # 5) Devolver datos completos
    return {"success": True, "data": ClienteRead.model_validate(nuevo)}

@router.put("/{id_cliente}", response_model=dict)
async def actualizar_cliente(
    id_cliente: UUID,
    entrada: ClienteUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un cliente en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga únicamente si el cliente existe y está activo
    stmt = select(Cliente).where(
        Cliente.id_cliente == id_cliente,
        Cliente.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # 3) Aplicar cambios y auditoría
    ctx = await obtener_contexto(db)
    cliente.nombre       = entrada.nombre
    cliente.apellido     = entrada.apellido
    cliente.razon_social = entrada.razon_social
    cliente.rfc          = entrada.rfc
    cliente.email        = entrada.email
    cliente.telefono     = entrada.telefono
    cliente.domicilio    = entrada.domicilio
    cliente.colonia      = entrada.colonia
    cliente.cp           = entrada.cp
    cliente.municipio    = entrada.municipio
    cliente.entidad      = entrada.entidad
    cliente.guid         = entrada.guid
    cliente.clave        = entrada.clave
    cliente.modified_by  = ctx["user_id"]

    # 4) Flush + Refresh para respetar RLS
    await db.flush()
    await db.refresh(cliente)

    # 5) Confirmar cambios
    await db.commit()

    return {"success": True, "data": ClienteRead.model_validate(cliente)}

@router.delete("/{id_cliente}", status_code=200)
async def eliminar_cliente(
    id_cliente: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un cliente. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Cliente).where(Cliente.id_cliente == id_cliente))
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # 2) Ejecutar DELETE
    await db.execute(delete(Cliente).where(Cliente.id_cliente == id_cliente))

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Cliente eliminado permanentemente"}
