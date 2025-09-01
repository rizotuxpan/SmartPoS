# proveedor.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Proveedor.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query # FastAPI para rutas y dependencias
from pydantic import BaseModel, Field, field_validator   # Pydantic para schemas de entrada/salida
from typing import Optional, List                            # Tipos para anotaciones
from uuid import UUID, uuid4                                 # UUID para identificadores únicos
from datetime import datetime                                # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, insert, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID   # Tipo UUID específico de PostgreSQL
from sqlalchemy.ext.asyncio import AsyncSession              # Sesión asíncrona de SQLAlchemy
from sqlalchemy.exc import IntegrityError                    # Para manejar errores de integridad

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Proveedor(Base):
    __tablename__ = "proveedor"  # Nombre de la tabla en la BD

    # Identificador principal generado por la función gen_random_uuid() en la BD
    id_proveedor = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    # Relación multiempresa: tenant actual (RLS)
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    # Razón social del proveedor (obligatorio, único por empresa)
    razon_social = Column(String(200), nullable=False)
    # RFC del proveedor (único global, opcional)
    rfc = Column(String(13), unique=True)
    # Información de contacto
    nombre_contacto = Column(String(100))
    telefono = Column(String(20))
    celular = Column(String(20))
    email = Column(String(100))
    # Información de dirección
    direccion = Column(String(300))
    ciudad = Column(String(100))
    estado = Column(String(100))
    codigo_postal = Column(String(10))
    pais = Column(String(50), server_default=text("'MEXICO'::character varying"))
    # Observaciones generales
    observaciones = Column(Text)
    # Auditoría: quién creó y modificó el proveedor (UUIDs)
    created_by = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.usuario'::text)::uuid")
    )
    modified_by = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.usuario'::text)::uuid")
    )
    # Estado del proveedor (activo/inactivo) con default en BD
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
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

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class ProveedorBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Proveedor.
    """
    razon_social: str = Field(..., max_length=200, description="Razón social del proveedor")
    rfc: Optional[str] = Field(None, max_length=13, description="RFC del proveedor")
    nombre_contacto: Optional[str] = Field(None, max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)
    celular: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    direccion: Optional[str] = Field(None, max_length=300)
    ciudad: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=5, description="Código postal de 5 dígitos")
    pais: Optional[str] = Field("MEXICO", max_length=50)
    observaciones: Optional[str] = None

class ProveedorCreate(ProveedorBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ProveedorUpdate(BaseModel):
    """Esquema para actualización con campos opcionales."""
    razon_social: Optional[str] = Field(None, max_length=200)
    rfc: Optional[str] = Field(None, max_length=13)
    nombre_contacto: Optional[str] = Field(None, max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)
    celular: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = None
    direccion: Optional[str] = Field(None, max_length=300)
    ciudad: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = Field(None, max_length=100)
    codigo_postal: Optional[str] = Field(None, max_length=5)
    pais: Optional[str] = Field(None, max_length=50)
    observaciones: Optional[str] = None

class ProveedorRead(ProveedorBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_proveedor: UUID
    id_empresa: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    modified_by: UUID
    id_estado: UUID

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_proveedores(
    razon_social: Optional[str] = Query(None, description="Filtro por razón social"),
    rfc: Optional[str] = Query(None, description="Filtro por RFC"),
    ciudad: Optional[str] = Query(None, description="Filtro por ciudad"),
    estado: Optional[str] = Query(None, description="Filtro por estado"),
    skip: int = Query(0, ge=0, description="Registros a saltar para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)  # Sesión RLS inyectada
):
    """
    Lista proveedores en estado "activo" con paginación y filtros opcionales.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta base con filtro de estado
    stmt = select(Proveedor).where(Proveedor.id_estado == estado_activo_id)

    # 3) Aplicar filtros opcionales
    if razon_social:
        stmt = stmt.where(Proveedor.razon_social.ilike(f"%{razon_social}%"))
    if rfc:
        stmt = stmt.where(Proveedor.rfc.ilike(f"%{rfc.upper()}%"))
    if ciudad:
        stmt = stmt.where(Proveedor.ciudad.ilike(f"%{ciudad}%"))
    if estado:
        stmt = stmt.where(Proveedor.estado.ilike(f"%{estado}%"))

    # 4) Ordenar por razón social
    stmt = stmt.order_by(Proveedor.razon_social)

    # 5) Contar total de registros para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 6) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 7) Serializar y devolver
    return {
        "success": True,
        "total_count": total,
        "data": [ProveedorRead.model_validate(p) for p in data]
    }

@router.get("/combo", response_model=dict)
async def listar_proveedores_combo(db: AsyncSession = Depends(get_async_db)):
    """Endpoint optimizado para llenar ComboBox de proveedores"""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    query = select(Proveedor.id_proveedor, Proveedor.razon_social).where(
        Proveedor.id_estado == estado_activo_id
    ).order_by(Proveedor.razon_social)
    
    result = await db.execute(query)
    proveedores = [{"id": str(row[0]), "razon_social": row[1]} for row in result]
    
    return {"success": True, "data": proveedores}

@router.get("/buscar/rfc/{rfc}", response_model=dict)
async def buscar_por_rfc(
    rfc: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Busca un proveedor por RFC específico.
    """
    # Validar que el RFC no esté vacío
    if not rfc or not rfc.strip():
        raise HTTPException(status_code=400, detail="RFC no puede estar vacío")
    
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Proveedor).where(
        Proveedor.rfc.ilike(rfc.upper().strip()),
        Proveedor.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    proveedor = result.scalar_one_or_none()

    if not proveedor:
        return {"success": False, "data": None, "message": "Proveedor no encontrado con ese RFC"}

    return {"success": True, "data": ProveedorRead.model_validate(proveedor)}

@router.get("/{id_proveedor}", response_model=ProveedorRead)
async def obtener_proveedor(
    id_proveedor: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un proveedor por su ID, sólo si está en estado "activo".
    """
    # 1) Identificador del estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Proveedor).where(
        Proveedor.id_proveedor == id_proveedor,
        Proveedor.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    proveedor = result.scalar_one_or_none()

    # 3) Si no existe o no es activo, devolver 404
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # 4) Retornar objeto serializado
    return ProveedorRead.model_validate(proveedor)

@router.post("/", response_model=dict, status_code=201)
async def crear_proveedor(
    entrada: ProveedorCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo proveedor. Aplica RLS y defaults de servidor.
    """
    try:
        # 1) Recuperar tenant y usuario del contexto RLS
        ctx = await obtener_contexto(db)

        # 2) Construir instancia ORM sin campos con server_default
        nuevo = Proveedor(
            razon_social=entrada.razon_social,
            rfc=entrada.rfc,
            nombre_contacto=entrada.nombre_contacto,
            telefono=entrada.telefono,
            celular=entrada.celular,
            email=entrada.email,
            direccion=entrada.direccion,
            ciudad=entrada.ciudad,
            estado=entrada.estado,
            codigo_postal=entrada.codigo_postal,
            pais=entrada.pais or "México",
            observaciones=entrada.observaciones,
            created_by=ctx["user_id"],
            modified_by=ctx["user_id"],
            id_empresa=ctx["tenant_id"]
        )
        db.add(nuevo)

        # 3) Ejecutar INSERT y refrescar antes de commit para respetar RLS
        await db.flush()        # Realiza INSERT RETURNING …
        await db.refresh(nuevo) # Ejecuta SELECT dentro de la misma tx

        # 4) Finalizar tx
        await db.commit()

        # 5) Devolver datos completos
        return {"success": True, "data": ProveedorRead.model_validate(nuevo)}

    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig).lower()
        
        if "rfc_key" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"El RFC '{entrada.rfc}' ya está registrado con otro proveedor"
            )
        elif "uq_proveedor_empresa_ci" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"Ya existe un proveedor con la razón social '{entrada.razon_social}' en esta empresa"
            )
        else:
            raise HTTPException(status_code=400, detail="Error de integridad de datos")

@router.put("/{id_proveedor}", response_model=dict)
async def actualizar_proveedor(
    id_proveedor: UUID,
    entrada: ProveedorUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza los campos de un proveedor en estado "activo".
    """
    try:
        # 1) UUID de estado activo
        estado_activo_id = await get_estado_id_por_clave("act", db)

        # 2) Carga únicamente si el proveedor existe y está activo
        stmt = select(Proveedor).where(
            Proveedor.id_proveedor == id_proveedor,
            Proveedor.id_estado == estado_activo_id
        )
        result = await db.execute(stmt)
        proveedor = result.scalar_one_or_none()
        if not proveedor:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")

        # 3) Aplicar cambios solo a campos que no son None
        ctx = await obtener_contexto(db)
        
        if entrada.razon_social is not None:
            proveedor.razon_social = entrada.razon_social
        if entrada.rfc is not None:
            proveedor.rfc = entrada.rfc
        if entrada.nombre_contacto is not None:
            proveedor.nombre_contacto = entrada.nombre_contacto
        if entrada.telefono is not None:
            proveedor.telefono = entrada.telefono
        if entrada.celular is not None:
            proveedor.celular = entrada.celular
        if entrada.email is not None:
            proveedor.email = entrada.email
        if entrada.direccion is not None:
            proveedor.direccion = entrada.direccion
        if entrada.ciudad is not None:
            proveedor.ciudad = entrada.ciudad
        if entrada.estado is not None:
            proveedor.estado = entrada.estado
        if entrada.codigo_postal is not None:
            proveedor.codigo_postal = entrada.codigo_postal
        if entrada.pais is not None:
            proveedor.pais = entrada.pais
        if entrada.observaciones is not None:
            proveedor.observaciones = entrada.observaciones

        # Auditoría
        proveedor.modified_by = ctx["user_id"]

        # 4) Flush + Refresh para respetar RLS
        await db.flush()
        await db.refresh(proveedor)

        # 5) Confirmar cambios
        await db.commit()

        return {"success": True, "data": ProveedorRead.model_validate(proveedor)}

    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig).lower()
        
        if "rfc_key" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"El RFC '{entrada.rfc}' ya está registrado con otro proveedor"
            )
        elif "uq_proveedor_empresa_ci" in error_msg:
            raise HTTPException(
                status_code=400, 
                detail=f"Ya existe un proveedor con la razón social '{entrada.razon_social}' en esta empresa"
            )
        else:
            raise HTTPException(status_code=400, detail="Error de integridad de datos")

@router.delete("/{id_proveedor}", status_code=200)
async def eliminar_proveedor(id_proveedor: UUID, db: AsyncSession = Depends(get_async_db)):
    """
    Elimina físicamente un proveedor. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Proveedor).where(Proveedor.id_proveedor == id_proveedor))
    proveedor = result.scalar_one_or_none()
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # 2) Ejecutar DELETE
    await db.execute(delete(Proveedor).where(Proveedor.id_proveedor == id_proveedor))

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Proveedor eliminado permanentemente"}