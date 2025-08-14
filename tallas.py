# tallas.py
# ---------------------------
# Módulo de endpoints REST para gestión del catálogo de Tallas.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Importa base de modelos y función de sesión configurada con RLS
from db import get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto

# ---------------------------
# Importar modelo ORM desde producto_variante.py
# ---------------------------
from producto_variante import CatTalla

# ---------------------------
# Schemas de validación con Pydantic
# ---------------------------
class TallaBase(BaseModel):
    """Esquema base con campos comunes para crear/actualizar Talla."""
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = 1

class TallaCreate(TallaBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class TallaUpdate(BaseModel):
    """Esquema para actualización con todos los campos opcionales."""
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = None

class TallaRead(TallaBase):
    """Esquema de lectura (salida) con atributos del modelo ORM."""
    id_talla: UUID
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
async def listar_tallas_combo(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint optimizado para llenar ComboBox de tallas.
    Retorna solo ID y descripción simplificada.
    """
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta
    query = select(
        CatTalla.id_talla,
        CatTalla.codigo,
        CatTalla.nombre
    ).where(
        CatTalla.id_estado == estado_activo_id
    ).order_by(
        CatTalla.orden_visualizacion,
        CatTalla.nombre
    )
    
    # Ejecutar consulta
    result = await db.execute(query)
    tallas = []
    
    for row in result:
        # Construir texto descriptivo
        texto = f"{row.codigo} - {row.nombre}"
            
        tallas.append({
            "id": str(row.id_talla),
            "texto": texto
        })
    
    return tallas

@router.get("/", response_model=dict)
async def listar_tallas(
    nombre: Optional[str] = Query(None, description="Filtro por nombre"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
    db: AsyncSession = Depends(get_async_db)
):
    """Listar tallas con paginación y filtros."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta base
    query = select(CatTalla).where(CatTalla.id_estado == estado_activo_id)
    
    # Aplicar filtros
    if nombre:
        query = query.where(CatTalla.nombre.ilike(f"%{nombre}%"))
    
    # Contar total de registros
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_count = await db.scalar(count_query)
    
    # Aplicar paginación y ordenamiento
    query = query.order_by(
        CatTalla.orden_visualizacion,
        CatTalla.nombre
    ).offset(skip).limit(limit)
    
    # Ejecutar consulta
    result = await db.execute(query)
    tallas = result.scalars().all()
    
    return {
        "success": True,
        "data": [TallaRead.model_validate(talla) for talla in tallas],
        "total_count": total_count,
        "skip": skip,
        "limit": limit
    }

@router.get("/{id_talla}", response_model=TallaRead)
async def obtener_talla(
    id_talla: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Obtener una talla específica por ID."""
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar la talla
    query = select(CatTalla).where(
        CatTalla.id_talla == id_talla,
        CatTalla.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    talla = result.scalar_one_or_none()
    
    if not talla:
        raise HTTPException(
            status_code=404,
            detail=f"Talla con ID {id_talla} no encontrada"
        )
    
    return TallaRead.model_validate(talla)

@router.post("/", response_model=dict, status_code=201)
async def crear_talla(
    talla_data: TallaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """Crear una nueva talla."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Crear nueva talla
    nueva_talla = CatTalla(
        id_talla=uuid4(),
        id_empresa=contexto.tenant_id,
        codigo=talla_data.codigo,
        nombre=talla_data.nombre,
        descripcion=talla_data.descripcion,
        orden_visualizacion=talla_data.orden_visualizacion,
        id_estado=estado_activo_id,
        created_by=contexto.user_id,
        modified_by=contexto.user_id
    )
    
    # Guardar en la base de datos
    db.add(nueva_talla)
    await db.commit()
    await db.refresh(nueva_talla)
    
    return {
        "success": True,
        "message": "Talla creada exitosamente",
        "data": TallaRead.model_validate(nueva_talla)
    }

@router.put("/{id_talla}", response_model=dict)
async def actualizar_talla(
    id_talla: UUID,
    talla_data: TallaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """Actualizar una talla existente."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar la talla
    query = select(CatTalla).where(
        CatTalla.id_talla == id_talla,
        CatTalla.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    talla = result.scalar_one_or_none()
    
    if not talla:
        raise HTTPException(
            status_code=404,
            detail=f"Talla con ID {id_talla} no encontrada"
        )
    
    # Actualizar campos proporcionados
    update_data = talla_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(talla, field, value)
    
    # Actualizar auditoría
    talla.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    await db.refresh(talla)
    
    return {
        "success": True,
        "message": "Talla actualizada exitosamente",
        "data": TallaRead.model_validate(talla)
    }

@router.delete("/{id_talla}", response_model=dict)
async def eliminar_talla(
    id_talla: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """Eliminar (borrado lógico) una talla."""
    # Obtener contexto de RLS
    contexto = await obtener_contexto(db)
    
    # Obtener UUIDs de estados
    estado_activo_id = await get_estado_id_por_clave("act", db)
    estado_borrado_id = await get_estado_id_por_clave("del", db)
    
    # Buscar la talla
    query = select(CatTalla).where(
        CatTalla.id_talla == id_talla,
        CatTalla.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    talla = result.scalar_one_or_none()
    
    if not talla:
        raise HTTPException(
            status_code=404,
            detail=f"Talla con ID {id_talla} no encontrada"
        )
    
    # Realizar borrado lógico
    talla.id_estado = estado_borrado_id
    talla.modified_by = contexto.user_id
    
    # Guardar cambios
    await db.commit()
    
    return {
        "success": True,
        "message": "Talla eliminada exitosamente"
    }