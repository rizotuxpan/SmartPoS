# tamanos.py
# ---------------------------
# Módulo de endpoints REST para gestión del catálogo de Tamaños.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, func, select, text, insert, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto

# ---------------------------
# Modelo ORM SQLAlchemy (importado desde producto_variante.py)
# ---------------------------
class CatTamano(Base):
    """Modelo ORM para catálogo de tamaños"""
    __tablename__ = "cat_tamano"
    
    id_tamano = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    codigo = Column(String(10), nullable=False)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(Text)
    unidad_medida = Column(String(10))
    orden_visualizacion = Column(Integer, server_default="1")
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

# ---------------------------
# Schemas de validación con Pydantic
# ---------------------------
class TamanoBase(BaseModel):
    """Esquema base con campos comunes para crear/actualizar Tamaño."""
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    unidad_medida: Optional[str] = None
    orden_visualizacion: Optional[int] = 1

class TamanoCreate(TamanoBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class TamanoUpdate(BaseModel):
    """Esquema para actualización con todos los campos opcionales."""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    unidad_medida: Optional[str] = None
    orden_visualizacion: Optional[int] = None

class TamanoRead(TamanoBase):
    """Esquema de lectura (salida) con atributos del modelo ORM."""
    id_tamano: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/combo/", response_model=List[dict])
async def listar_tamanos_combo(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint optimizado para llenar ComboBox de tamaños.
    Retorna solo ID y descripción simplificada.
    """
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta
    query = select(
        CatTamano.id_tamano,
        CatTamano.codigo,
        CatTamano.nombre,
        CatTamano.unidad_medida
    ).where(
        CatTamano.id_estado == estado_activo_id
    ).order_by(
        CatTamano.orden_visualizacion,
        CatTamano.nombre
    )
    
    # Ejecutar consulta
    result = await db.execute(query)
    tamanos = []
    
    for row in result:
        # Construir texto descriptivo
        texto = f"{row.codigo} - {row.nombre}"
        if row.unidad_medida:
            texto += f" ({row.unidad_medida})"
            
        tamanos.append({
            "id": str(row.id_tamano),
            "texto": texto
        })
    
    return tamanos

@router.get("/", response_model=dict)
async def listar_tamanos(
    nombre: Optional[str] = Query(None, description="Filtro por nombre"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
    db: AsyncSession = Depends(get_async_db)
):
    """Listar tamaños con paginación y filtros."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta base
    query = select(CatTamano).where(CatTamano.id_estado == estado_activo_id)
    
    # Aplicar filtros
    if nombre:
        query = query.where(CatTamano.nombre.ilike(f"%{nombre}%"))
    
    # Contar total de registros
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_count = await db.scalar(count_query)
    
    # Aplicar paginación y ordenamiento
    query = query.order_by(
        CatTamano.orden_visualizacion,
        CatTamano.nombre
    ).offset(skip).limit(limit)
    
    # Ejecutar consulta
    result = await db.execute(query)
    tamanos = result.scalars().all()
    
    return {
        "success": True,
        "data": [TamanoRead.model_validate(tamano) for tamano in tamanos],
        "total_count": total_count,
        "skip": skip,
        "limit": limit
    }

@router.get("/{id_tamano}", response_model=TamanoRead)
async def obtener_tamano(
    id_tamano: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Obtener un tamaño específico por ID."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el tamaño
    query = select(CatTamano).where(
        CatTamano.id_tamano == id_tamano,
        CatTamano.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    tamano = result.scalar_one_or_none()
    
    if not tamano:
        raise HTTPException(
            status_code=404,
            detail=f"Tamaño con ID {id_tamano} no encontrado"
        )
    
    return TamanoRead.model_validate(tamano)

@router.post("/", response_model=dict, status_code=201)
async def crear_tamano(
    tamano_data: TamanoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crear un nuevo tamaño."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Crear nuevo tamaño
    nuevo_tamano = CatTamano(
        id_tamano=uuid4(),
        id_empresa=contexto.tenant_id,
        codigo=tamano_data.codigo,
        nombre=tamano_data.nombre,
        descripcion=tamano_data.descripcion,
        unidad_medida=tamano_data.unidad_medida,
        orden_visualizacion=tamano_data.orden_visualizacion,
        id_estado=estado_activo_id,
        created_by=contexto.user_id,
        modified_by=contexto.user_id
    )
    
    # Guardar en la base de datos
    db.add(nuevo_tamano)
    await db.commit()
    await db.refresh(nuevo_tamano)
    
    return {
        "success": True,
        "message": "Tamaño creado exitosamente",
        "data": TamanoRead.model_validate(nuevo_tamano)
    }

@router.put("/{id_tamano}", response_model=dict)
async def actualizar_tamano(
    id_tamano: UUID,
    tamano_data: TamanoUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """Actualizar un tamaño existente."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el tamaño
    query = select(CatTamano).where(
        CatTamano.id_tamano == id_tamano,
        CatTamano.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    tamano = result.scalar_one_or_none()
    
    if not tamano:
        raise HTTPException(
            status_code=404,
            detail=f"Tamaño con ID {id_tamano} no encontrado"
        )
    
    # Actualizar campos proporcionados
    update_data = tamano_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tamano, field, value)
    
    # Actualizar auditoría
    tamano.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    await db.refresh(tamano)
    
    return {
        "success": True,
        "message": "Tamaño actualizado exitosamente",
        "data": TamanoRead.model_validate(tamano)
    }

@router.delete("/{id_tamano}", response_model=dict)
async def eliminar_tamano(
    id_tamano: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Eliminar (borrado lógico) un tamaño."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUIDs de estados
    estado_activo_id = await get_estado_id_por_clave("act", db)
    estado_borrado_id = await get_estado_id_por_clave("del", db)
    
    # Buscar el tamaño
    query = select(CatTamano).where(
        CatTamano.id_tamano == id_tamano,
        CatTamano.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    tamano = result.scalar_one_or_none()
    
    if not tamano:
        raise HTTPException(
            status_code=404,
            detail=f"Tamaño con ID {id_tamano} no encontrado"
        )
    
    # Realizar borrado lógico
    tamano.id_estado = estado_borrado_id
    tamano.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    
    return {
        "success": True,
        "message": "Tamaño eliminado exitosamente"
    }