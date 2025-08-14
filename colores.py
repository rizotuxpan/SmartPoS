# colores.py
# ---------------------------
# Módulo de endpoints REST para gestión del catálogo de Colores.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
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
class CatColor(Base):
    """Modelo ORM para catálogo de colores"""
    __tablename__ = "cat_color"
    
    id_color = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    codigo = Column(String(10), nullable=False)
    nombre = Column(String(50), nullable=False)
    hex_codigo = Column(String(7))
    descripcion = Column(Text)
    orden_visualizacion = Column(Integer, server_default="1")
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

# ---------------------------
# Schemas de validación con Pydantic
# ---------------------------
class ColorBase(BaseModel):
    """Esquema base con campos comunes para crear/actualizar Color."""
    codigo: str
    nombre: str
    hex_codigo: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Código hexadecimal del color (ej: #FF0000)")
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = 1

class ColorCreate(ColorBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ColorUpdate(BaseModel):
    """Esquema para actualización con todos los campos opcionales."""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    hex_codigo: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$', description="Código hexadecimal del color (ej: #FF0000)")
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = None

class ColorRead(ColorBase):
    """Esquema de lectura (salida) con atributos del modelo ORM."""
    id_color: UUID
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
async def listar_colores_combo(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint optimizado para llenar ComboBox de colores.
    Retorna solo ID y descripción simplificada.
    """
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta
    query = select(
        CatColor.id_color,
        CatColor.codigo,
        CatColor.nombre,
        CatColor.hex_codigo
    ).where(
        CatColor.id_estado == estado_activo_id
    ).order_by(
        CatColor.orden_visualizacion,
        CatColor.nombre
    )
    
    # Ejecutar consulta
    result = await db.execute(query)
    colores = []
    
    for row in result:
        # Construir texto descriptivo
        texto = f"{row.codigo} - {row.nombre}"
        if row.hex_codigo:
            texto += f" ({row.hex_codigo})"
            
        colores.append({
            "id": str(row.id_color),
            "texto": texto
        })
    
    return colores

@router.get("/", response_model=dict)
async def listar_colores(
    nombre: Optional[str] = Query(None, description="Filtro por nombre"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
    db: AsyncSession = Depends(get_async_db)
):
    """Listar colores con paginación y filtros."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta base
    query = select(CatColor).where(CatColor.id_estado == estado_activo_id)
    
    # Aplicar filtros
    if nombre:
        query = query.where(CatColor.nombre.ilike(f"%{nombre}%"))
    
    # Contar total de registros
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_count = await db.scalar(count_query)
    
    # Aplicar paginación y ordenamiento
    query = query.order_by(
        CatColor.orden_visualizacion,
        CatColor.nombre
    ).offset(skip).limit(limit)
    
    # Ejecutar consulta
    result = await db.execute(query)
    colores = result.scalars().all()
    
    return {
        "success": True,
        "data": [ColorRead.model_validate(color) for color in colores],
        "total_count": total_count,
        "skip": skip,
        "limit": limit
    }

@router.get("/{id_color}", response_model=ColorRead)
async def obtener_color(
    id_color: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Obtener un color específico por ID."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el color
    query = select(CatColor).where(
        CatColor.id_color == id_color,
        CatColor.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    color = result.scalar_one_or_none()
    
    if not color:
        raise HTTPException(
            status_code=404,
            detail=f"Color con ID {id_color} no encontrado"
        )
    
    return ColorRead.model_validate(color)

@router.post("/", response_model=dict, status_code=201)
async def crear_color(
    color_data: ColorCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crear un nuevo color."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Crear nuevo color
    nuevo_color = CatColor(
        id_color=uuid4(),
        id_empresa=contexto.tenant_id,
        codigo=color_data.codigo,
        nombre=color_data.nombre,
        hex_codigo=color_data.hex_codigo,
        descripcion=color_data.descripcion,
        orden_visualizacion=color_data.orden_visualizacion,
        id_estado=estado_activo_id,
        created_by=contexto.user_id,
        modified_by=contexto.user_id
    )
    
    # Guardar en la base de datos
    db.add(nuevo_color)
    await db.commit()
    await db.refresh(nuevo_color)
    
    return {
        "success": True,
        "message": "Color creado exitosamente",
        "data": ColorRead.model_validate(nuevo_color)
    }

@router.put("/{id_color}", response_model=dict)
async def actualizar_color(
    id_color: UUID,
    color_data: ColorUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """Actualizar un color existente."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el color
    query = select(CatColor).where(
        CatColor.id_color == id_color,
        CatColor.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    color = result.scalar_one_or_none()
    
    if not color:
        raise HTTPException(
            status_code=404,
            detail=f"Color con ID {id_color} no encontrado"
        )
    
    # Actualizar campos proporcionados
    update_data = color_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(color, field, value)
    
    # Actualizar auditoría
    color.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    await db.refresh(color)
    
    return {
        "success": True,
        "message": "Color actualizado exitosamente",
        "data": ColorRead.model_validate(color)
    }

@router.delete("/{id_color}", response_model=dict)
async def eliminar_color(
    id_color: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Eliminar (borrado lógico) un color."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUIDs de estados
    estado_activo_id = await get_estado_id_por_clave("act", db)
    estado_borrado_id = await get_estado_id_por_clave("del", db)
    
    # Buscar el color
    query = select(CatColor).where(
        CatColor.id_color == id_color,
        CatColor.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    color = result.scalar_one_or_none()
    
    if not color:
        raise HTTPException(
            status_code=404,
            detail=f"Color con ID {id_color} no encontrado"
        )
    
    # Realizar borrado lógico
    color.id_estado = estado_borrado_id
    color.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    
    return {
        "success": True,
        "message": "Color eliminado exitosamente"
    }