# producto.py - VERSIÓN CORREGIDA PARA SQLALCHEMY 2.x
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Producto.
# Incluye objetos relacionados completos y filtros avanzados

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel, model_validator                 # Pydantic para schemas de entrada/salida
from typing import Optional                                     # Tipos para anotaciones
from uuid import UUID                                           # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from decimal import Decimal                                     # Para campos numéricos de alta precisión
from sqlalchemy import (
    Column, String, Text, DateTime, Numeric, Boolean, Integer,
    func, select, text, delete, and_, or_, cast
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# ===== IMPORTAR MODELOS Y ESQUEMAS RELACIONADOS =====
from marca import Marca, MarcaRead
from umedida import UMedida, UMedidaRead
from categoria import Categoria, CategoriaRead
from subcategoria import Subcategoria, SubcategoriaRead

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Producto(Base):
    __tablename__ = "producto"
    id_producto    = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa     = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_estado      = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    sku            = Column(String(50))
    codigo_barras  = Column(CITEXT)
    nombre         = Column(String(120), nullable=False)
    descripcion    = Column(Text)
    precio_base    = Column(Numeric(14, 2), nullable=True, server_default=text("0"))
    es_kit         = Column(Boolean, nullable=False, server_default=text("false"))
    vida_util_dias = Column(Integer)
    id_marca       = Column(PG_UUID(as_uuid=True))
    id_umedida     = Column(PG_UUID(as_uuid=True))
    guid           = Column(String(36))
    costo_u        = Column(Numeric(14, 2))    
    id_categoria   = Column(PG_UUID(as_uuid=True))
    id_subcategoria= Column(PG_UUID(as_uuid=True))
    created_by     = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by    = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at     = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at     = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class ProductoBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Producto.
    """
    sku: Optional[str] = None
    codigo_barras: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio_base: Optional[Decimal] = None
    es_kit: Optional[bool] = None
    vida_util_dias: Optional[int] = None
    id_marca: Optional[UUID] = None
    id_umedida: Optional[UUID] = None    
    guid: Optional[str] = None
    costo_u: Optional[Decimal] = None    
    id_categoria: Optional[UUID] = None
    id_subcategoria: Optional[UUID] = None

class ProductoCreate(ProductoBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ProductoUpdate(BaseModel):
    """
    Esquema para actualización con todos los campos opcionales.
    Solo se actualizarán los campos que se proporcionen.
    """
    sku: Optional[str] = None
    codigo_barras: Optional[str] = None
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio_base: Optional[Decimal] = None
    es_kit: Optional[bool] = None
    vida_util_dias: Optional[int] = None
    id_marca: Optional[UUID] = None
    id_umedida: Optional[UUID] = None    
    guid: Optional[str] = None
    costo_u: Optional[Decimal] = None    
    id_categoria: Optional[UUID] = None
    id_subcategoria: Optional[UUID] = None
    
    # Validador personalizado para categoría/subcategoría
    @model_validator(mode='after')
    def validate_categoria_subcategoria(self):
        # Si se proporciona subcategoría sin categoría, está bien
        # Si se proporciona categoría sin subcategoría, está bien
        # Si se proporcionan ambos, se validará en el endpoint
        return self

class ProductoRead(ProductoBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_producto: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# ===== NUEVO ESQUEMA EXPANDIDO =====
class ProductoReadExpanded(ProductoBase):
    """
    Esquema de lectura expandido con objetos relacionados completos.
    """
    id_producto: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    # Objetos relacionados completos
    marca: Optional[MarcaRead] = None
    umedida: Optional[UMedidaRead] = None
    categoria: Optional[CategoriaRead] = None
    subcategoria: Optional[SubcategoriaRead] = None
    
    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_productos(
    # ===== FILTROS BÁSICOS =====
    nombre: Optional[str] = Query(None, description="Filtro por nombre del producto"),
    sku: Optional[str] = Query(None, description="Filtro por SKU del producto"),
    codigo_barras: Optional[str] = Query(None, description="Filtro por código de barras"),
    
    # ===== FILTROS DE PRECIO EXTENDIDOS =====
    precio: Optional[float] = Query(None, description="Precio exacto"),
    precio_min: Optional[float] = Query(None, description="Precio mínimo (>=)"),
    precio_max: Optional[float] = Query(None, description="Precio máximo (<=)"),
    precio_mayor: Optional[float] = Query(None, description="Precio mayor que (>)"),
    precio_menor: Optional[float] = Query(None, description="Precio menor que (<)"),
    precio_texto: Optional[str] = Query(None, description="Búsqueda textual en precio"),
    
    # ===== FILTROS POR NOMBRES DE ENTIDADES RELACIONADAS =====
    marca_nombre: Optional[str] = Query(None, description="Filtro por nombre de marca"),
    categoria_nombre: Optional[str] = Query(None, description="Filtro por nombre de categoría"),
    subcategoria_nombre: Optional[str] = Query(None, description="Filtro por nombre de subcategoría"),
    
    # ===== PARÁMETROS DE CONFIGURACIÓN =====
    expandir: bool = Query(False, description="Incluir objetos relacionados completos"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista productos en estado "activo" con paginación, filtros opcionales extendidos
    y opción de expandir objetos relacionados.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    if expandir:
        # ===== CONSULTA CON JOINS PARA OBJETOS RELACIONADOS =====
        # Crear query base
        query = select(
            Producto,
            Marca,
            UMedida,
            Categoria,
            Subcategoria
        )
        
        # Especificar FROM explícitamente para SQLAlchemy 2.x
        query = query.select_from(
            Producto.__table__
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                UMedida.__table__,
                and_(
                    Producto.id_umedida == UMedida.id_umedida,
                    UMedida.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Categoria.__table__,
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Subcategoria.__table__,
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            )
        )
        
        # Filtro base
        query = query.where(Producto.id_estado == estado_activo_id)
        
        # ===== APLICAR FILTROS BÁSICOS =====
        if nombre:
            query = query.where(Producto.nombre.ilike(f"%{nombre}%"))
        if sku:
            query = query.where(Producto.sku.ilike(f"%{sku}%"))
        if codigo_barras:
            query = query.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))
        
        # ===== APLICAR FILTROS DE PRECIO =====
        if precio is not None:
            query = query.where(Producto.precio_base == precio)
        if precio_min is not None:
            query = query.where(Producto.precio_base >= precio_min)
        if precio_max is not None:
            query = query.where(Producto.precio_base <= precio_max)
        if precio_mayor is not None:
            query = query.where(Producto.precio_base > precio_mayor)
        if precio_menor is not None:
            query = query.where(Producto.precio_base < precio_menor)
        if precio_texto:
            query = query.where(cast(Producto.precio_base, String).ilike(f"%{precio_texto}%"))
        
        # ===== APLICAR FILTROS DE ENTIDADES RELACIONADAS =====
        if marca_nombre:
            query = query.where(Marca.nombre.ilike(f"%{marca_nombre}%"))
        if categoria_nombre:
            query = query.where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
        if subcategoria_nombre:
            query = query.where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))
        
        # ===== CONTAR TOTAL PARA PAGINACIÓN =====
        count_query = select(func.count(Producto.id_producto)).select_from(
            Producto.__table__
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Categoria.__table__,
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Subcategoria.__table__,
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            )
        ).where(Producto.id_estado == estado_activo_id)
        
        # Aplicar los mismos filtros al count
        if nombre:
            count_query = count_query.where(Producto.nombre.ilike(f"%{nombre}%"))
        if sku:
            count_query = count_query.where(Producto.sku.ilike(f"%{sku}%"))
        if codigo_barras:
            count_query = count_query.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))
        if precio is not None:
            count_query = count_query.where(Producto.precio_base == precio)
        if precio_min is not None:
            count_query = count_query.where(Producto.precio_base >= precio_min)
        if precio_max is not None:
            count_query = count_query.where(Producto.precio_base <= precio_max)
        if precio_mayor is not None:
            count_query = count_query.where(Producto.precio_base > precio_mayor)
        if precio_menor is not None:
            count_query = count_query.where(Producto.precio_base < precio_menor)
        if precio_texto:
            count_query = count_query.where(cast(Producto.precio_base, String).ilike(f"%{precio_texto}%"))
        if marca_nombre:
            count_query = count_query.where(Marca.nombre.ilike(f"%{marca_nombre}%"))
        if categoria_nombre:
            count_query = count_query.where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
        if subcategoria_nombre:
            count_query = count_query.where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))
        
        total = await db.scalar(count_query)
        
        # Ejecutar consulta paginada
        result = await db.execute(query.offset(skip).limit(limit))
        
        # ===== CONSTRUIR RESPUESTA EXPANDIDA =====
        data = []
        for row in result:
            producto_obj = row[0]  # Objeto Producto
            marca_obj = row[1]     # Objeto Marca (puede ser None)
            umedida_obj = row[2]   # Objeto UMedida (puede ser None)
            categoria_obj = row[3] # Objeto Categoria (puede ser None)
            subcategoria_obj = row[4] # Objeto Subcategoria (puede ser None)
            
            # Convertir producto base
            producto_dict = ProductoRead.model_validate(producto_obj).model_dump()
            
            # Agregar objetos relacionados si existen
            producto_dict['marca'] = MarcaRead.model_validate(marca_obj).model_dump() if marca_obj else None
            producto_dict['umedida'] = UMedidaRead.model_validate(umedida_obj).model_dump() if umedida_obj else None
            producto_dict['categoria'] = CategoriaRead.model_validate(categoria_obj).model_dump() if categoria_obj else None
            producto_dict['subcategoria'] = SubcategoriaRead.model_validate(subcategoria_obj).model_dump() if subcategoria_obj else None
            
            data.append(producto_dict)
    
    else:
        # ===== CONSULTA SIN JOINS (VERSIÓN SIMPLIFICADA) =====
        query = select(Producto).where(Producto.id_estado == estado_activo_id)
        
        # Aplicar filtros básicos
        if nombre:
            query = query.where(Producto.nombre.ilike(f"%{nombre}%"))
        if sku:
            query = query.where(Producto.sku.ilike(f"%{sku}%"))
        if codigo_barras:
            query = query.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))
        
        # Aplicar filtros de precio
        if precio is not None:
            query = query.where(Producto.precio_base == precio)
        if precio_min is not None:
            query = query.where(Producto.precio_base >= precio_min)
        if precio_max is not None:
            query = query.where(Producto.precio_base <= precio_max)
        if precio_mayor is not None:
            query = query.where(Producto.precio_base > precio_mayor)
        if precio_menor is not None:
            query = query.where(Producto.precio_base < precio_menor)
        if precio_texto:
            query = query.where(cast(Producto.precio_base, String).ilike(f"%{precio_texto}%"))
        
        # Para filtros de entidades relacionadas, agregar joins específicos
        if marca_nombre:
            query = query.join(Marca).where(
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id,
                    Marca.nombre.ilike(f"%{marca_nombre}%")
                )
            )
        
        if categoria_nombre:
            query = query.join(Categoria).where(
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id,
                    Categoria.nombre.ilike(f"%{categoria_nombre}%")
                )
            )
        
        if subcategoria_nombre:
            query = query.join(Subcategoria).where(
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id,
                    Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%")
                )
            )
        
        # Contar total (replicando la misma lógica)
        count_query = select(func.count(Producto.id_producto)).where(Producto.id_estado == estado_activo_id)
        
        if nombre:
            count_query = count_query.where(Producto.nombre.ilike(f"%{nombre}%"))
        if sku:
            count_query = count_query.where(Producto.sku.ilike(f"%{sku}%"))
        if codigo_barras:
            count_query = count_query.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))
        if precio is not None:
            count_query = count_query.where(Producto.precio_base == precio)
        if precio_min is not None:
            count_query = count_query.where(Producto.precio_base >= precio_min)
        if precio_max is not None:
            count_query = count_query.where(Producto.precio_base <= precio_max)
        if precio_mayor is not None:
            count_query = count_query.where(Producto.precio_base > precio_mayor)
        if precio_menor is not None:
            count_query = count_query.where(Producto.precio_base < precio_menor)
        if precio_texto:
            count_query = count_query.where(cast(Producto.precio_base, String).ilike(f"%{precio_texto}%"))
        
        if marca_nombre:
            count_query = count_query.join(Marca).where(
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id,
                    Marca.nombre.ilike(f"%{marca_nombre}%")
                )
            )
        
        if categoria_nombre:
            count_query = count_query.join(Categoria).where(
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id,
                    Categoria.nombre.ilike(f"%{categoria_nombre}%")
                )
            )
        
        if subcategoria_nombre:
            count_query = count_query.join(Subcategoria).where(
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id,
                    Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%")
                )
            )
        
        total = await db.scalar(count_query)
        
        # Ejecutar consulta paginada
        result = await db.execute(query.offset(skip).limit(limit))
        productos = result.scalars().all()
        
        data = [ProductoRead.model_validate(p).model_dump() for p in productos]

    return {
        "success": True,
        "total_count": total,
        "expandido": expandir,
        "filtros_aplicados": {
            "basicos": {
                "nombre": nombre,
                "sku": sku,
                "codigo_barras": codigo_barras
            },
            "precio": {
                "exacto": precio,
                "min": precio_min,
                "max": precio_max,
                "mayor": precio_mayor,
                "menor": precio_menor,
                "texto": precio_texto
            },
            "entidades": {
                "marca_nombre": marca_nombre,
                "categoria_nombre": categoria_nombre,
                "subcategoria_nombre": subcategoria_nombre
            }
        },
        "paginacion": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "pagina_actual": (skip // limit) + 1,
            "total_paginas": ((total - 1) // limit) + 1 if total > 0 else 0
        },
        "data": data
    }

@router.get("/{id_producto}", response_model=dict)
async def obtener_producto(
    id_producto: UUID,
    expandir: bool = Query(False, description="Incluir objetos relacionados completos"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un producto por su ID, con opción de expandir objetos relacionados.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    if expandir:
        # Consulta con joins usando tabla base
        query = select(
            Producto,
            Marca,
            UMedida,
            Categoria,
            Subcategoria
        ).select_from(
            Producto.__table__
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                UMedida.__table__,
                and_(
                    Producto.id_umedida == UMedida.id_umedida,
                    UMedida.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Categoria.__table__,
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Subcategoria.__table__,
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            )
        ).where(
            Producto.id_producto == id_producto,
            Producto.id_estado == estado_activo_id
        )
        
        result = await db.execute(query)
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        # Construir respuesta expandida
        producto_obj = row[0]
        marca_obj = row[1]
        umedida_obj = row[2]
        categoria_obj = row[3]
        subcategoria_obj = row[4]
        
        producto_dict = ProductoRead.model_validate(producto_obj).model_dump()
        
        producto_dict['marca'] = MarcaRead.model_validate(marca_obj).model_dump() if marca_obj else None
        producto_dict['umedida'] = UMedidaRead.model_validate(umedida_obj).model_dump() if umedida_obj else None
        producto_dict['categoria'] = CategoriaRead.model_validate(categoria_obj).model_dump() if categoria_obj else None
        producto_dict['subcategoria'] = SubcategoriaRead.model_validate(subcategoria_obj).model_dump() if subcategoria_obj else None
        
        return {
            "success": True,
            "expandido": True,
            "data": producto_dict
        }
    
    else:
        # Consulta normal
        query = select(Producto).where(
            Producto.id_producto == id_producto,
            Producto.id_estado == estado_activo_id
        )
        result = await db.execute(query)
        producto = result.scalar_one_or_none()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        return {
            "success": True,
            "expandido": False,
            "data": ProductoRead.model_validate(producto).model_dump()
        }

@router.post("/", response_model=dict, status_code=201)
async def crear_producto(
    entrada: ProductoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo producto. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)
    nuevo = Producto(
        sku             = entrada.sku,
        codigo_barras   = entrada.codigo_barras,
        nombre          = entrada.nombre,
        descripcion     = entrada.descripcion,
        precio_base     = entrada.precio_base,
        es_kit          = entrada.es_kit,
        vida_util_dias  = entrada.vida_util_dias,
        id_marca        = entrada.id_marca,
        id_umedida      = entrada.id_umedida,        
        guid            = entrada.guid,
        costo_u         = entrada.costo_u,        
        id_categoria    = entrada.id_categoria,
        id_subcategoria = entrada.id_subcategoria,
        created_by      = ctx["user_id"],
        modified_by     = ctx["user_id"],
        id_empresa      = ctx["tenant_id"]
    )
    db.add(nuevo)
    await db.flush()
    await db.refresh(nuevo)
    await db.commit()
    return {"success": True, "data": ProductoRead.model_validate(nuevo)}

@router.put("/{id_producto}", response_model=dict)
async def actualizar_producto(
    id_producto: UUID,
    entrada: ProductoUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un producto en estado "activo".
    Maneja correctamente las relaciones de categoría/subcategoría.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el producto existente
    query = select(Producto).where(
        Producto.id_producto == id_producto,
        Producto.id_estado == estado_activo_id
    )
    result = await db.execute(query)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Obtener contexto del usuario
    ctx = await obtener_contexto(db)
    
    # ===== VALIDACIONES ESPECIALES PARA CATEGORÍA/SUBCATEGORÍA =====
    
    # Si se proporciona subcategoría, validar que la categoría sea compatible
    if entrada.id_subcategoria is not None:
        subcat_query = select(Subcategoria).where(
            Subcategoria.id_subcategoria == entrada.id_subcategoria,
            Subcategoria.id_estado == estado_activo_id
        )
        subcat_result = await db.execute(subcat_query)
        subcategoria = subcat_result.scalar_one_or_none()
        
        if not subcategoria:
            raise HTTPException(status_code=400, detail="Subcategoría no encontrada")
        
        # Si se proporciona categoría, verificar que coincida con la subcategoría
        if entrada.id_categoria is not None:
            if subcategoria.id_categoria != entrada.id_categoria:
                raise HTTPException(
                    status_code=400, 
                    detail="La subcategoría no pertenece a la categoría especificada"
                )
        else:
            # Si no se proporciona categoría, usar la de la subcategoría
            entrada.id_categoria = subcategoria.id_categoria
    
    # Si se proporciona categoría pero no subcategoría, verificar que sea válido
    elif entrada.id_categoria is not None:
        cat_query = select(Categoria).where(
            Categoria.id_categoria == entrada.id_categoria,
            Categoria.id_estado == estado_activo_id
        )
        cat_result = await db.execute(cat_query)
        categoria = cat_result.scalar_one_or_none()
        
        if not categoria:
            raise HTTPException(status_code=400, detail="Categoría no encontrada")
    
    # ===== ACTUALIZAR SOLO LOS CAMPOS PROPORCIONADOS =====
    
    # Campos básicos
    if entrada.sku is not None:
        producto.sku = entrada.sku
    if entrada.codigo_barras is not None:
        producto.codigo_barras = entrada.codigo_barras
    if entrada.nombre is not None:
        producto.nombre = entrada.nombre
    if entrada.descripcion is not None:
        producto.descripcion = entrada.descripcion
    
    # Campos comerciales
    if entrada.precio_base is not None:
        producto.precio_base = entrada.precio_base
    if entrada.es_kit is not None:
        producto.es_kit = entrada.es_kit
    if entrada.vida_util_dias is not None:
        producto.vida_util_dias = entrada.vida_util_dias
    if entrada.costo_u is not None:
        producto.costo_u = entrada.costo_u
    
    # Relaciones (solo actualizar si se proporcionan)
    if entrada.id_marca is not None:
        producto.id_marca = entrada.id_marca
    if entrada.id_umedida is not None:
        producto.id_umedida = entrada.id_umedida
    
    # ===== MANEJO ESPECIAL DE CATEGORÍA/SUBCATEGORÍA =====
    # Solo actualizar si al menos uno de los dos se proporciona
    if entrada.id_categoria is not None or entrada.id_subcategoria is not None:
        producto.id_categoria = entrada.id_categoria
        producto.id_subcategoria = entrada.id_subcategoria
    
    # Campos adicionales    
    if entrada.guid is not None:
        producto.guid = entrada.guid    
    
    # Campos de auditoría
    producto.modified_by = ctx["user_id"]
    
    try:
        await db.flush()
        await db.refresh(producto)
        await db.commit()
        
        return {
            "success": True, 
            "message": "Producto actualizado correctamente",
            "data": ProductoRead.model_validate(producto).model_dump()
        }
        
    except Exception as e:
        await db.rollback()
        
        # Manejo específico de errores de constraint
        if "cat_subcategoria" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="Error de relación entre categoría y subcategoría. Verifica que ambas sean compatibles."
            )
        elif "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(
                status_code=409, 
                detail="Ya existe un producto con ese SKU o código de barras."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )


@router.delete("/{id_producto}", status_code=200)
async def eliminar_producto(
    id_producto: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un producto. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Producto).where(Producto.id_producto == id_producto)
    )
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    await db.execute(delete(Producto).where(Producto.id_producto == id_producto))
    await db.commit()
    return {"success": True, "message": "Producto eliminado permanentemente"}

# ===== ENDPOINT CORREGIDO - Maneja Productos sin Variantes =====
# Reemplazar en producto.py

@router.get("/buscar_por_codigo/{codigo}", response_model=dict)
async def buscar_producto_por_codigo(
    codigo: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint inteligente que busca un producto por código (SKU, código de barras).
    
    Implementa búsqueda híbrida:
    1. Busca primero como variante específica
    2. Si no encuentra, busca como producto base
    3. Si el producto base no tiene variantes, lo trata como variante única
    4. Retorna información optimizada para punto de venta
    """
    
    if not codigo or not codigo.strip():
        raise HTTPException(status_code=400, detail="El código no puede estar vacío")
    
    codigo = codigo.strip()
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # =================
    # PASO 1: Buscar como variante específica
    # =================
    variante_query = text("""
        SELECT 
            pv.id_producto_variante,
            pv.id_producto,
            pv.sku_variante,
            pv.codigo_barras_var,
            pv.precio,
            pv.peso_gr,
            pv.vida_util_dias,
            p.nombre as producto_nombre,
            p.descripcion as producto_descripcion,
            p.precio_base,
            p.es_kit,
            ct.nombre as talla_nombre,
            cc.nombre as color_nombre,
            ctam.nombre as tamano_nombre
        FROM producto_variante pv
        INNER JOIN producto p ON pv.id_producto = p.id_producto 
            AND p.id_estado = :estado_activo_id
        LEFT JOIN cat_talla ct ON pv.id_talla = ct.id_talla
        LEFT JOIN cat_color cc ON pv.id_color = cc.id_color  
        LEFT JOIN cat_tamano ctam ON pv.id_tamano = ctam.id_tamano
        WHERE pv.id_estado = :estado_activo_id
        AND (
            LOWER(pv.sku_variante) LIKE LOWER(:codigo_like) 
            OR LOWER(pv.codigo_barras_var) LIKE LOWER(:codigo_like)
        )
        LIMIT 1
    """)
    
    result = await db.execute(variante_query, {
        "estado_activo_id": estado_activo_id,
        "codigo_like": f"%{codigo}%"
    })
    variante_row = result.first()
    
    if variante_row:
        # ENCONTRADO COMO VARIANTE ESPECÍFICA
        precio_final = float(variante_row.precio) if variante_row.precio else float(variante_row.precio_base) if variante_row.precio_base else 0.0
        
        # Construir descripción de atributos
        atributos = []
        if variante_row.talla_nombre:
            atributos.append(f"Talla: {variante_row.talla_nombre}")
        if variante_row.color_nombre:
            atributos.append(f"Color: {variante_row.color_nombre}")
        if variante_row.tamano_nombre:
            atributos.append(f"Tamaño: {variante_row.tamano_nombre}")
        
        variante_info = {
            "id_producto_variante": str(variante_row.id_producto_variante),
            "id_producto": str(variante_row.id_producto),
            "sku_variante": variante_row.sku_variante,
            "codigo_barras_var": variante_row.codigo_barras_var,
            "precio": precio_final,
            "peso_gr": float(variante_row.peso_gr) if variante_row.peso_gr else 0.0,
            "vida_util_dias": variante_row.vida_util_dias,
            "producto_nombre": variante_row.producto_nombre,
            "producto_descripcion": variante_row.producto_descripcion,
            "es_kit": variante_row.es_kit,
            "descripcion_variante": " | ".join(atributos) if atributos else "Estándar",
            "atributos": {
                "talla": variante_row.talla_nombre,
                "color": variante_row.color_nombre, 
                "tamano": variante_row.tamano_nombre
            }
        }
        
        return {
            "success": True,
            "tipo": "variante_especifica",
            "accion_sugerida": "agregar_directo",
            "mensaje": f"Variante específica encontrada: {variante_row.sku_variante}",
            "variante": variante_info,
            "producto": None,
            "variantes": []
        }
    
    # =================
    # PASO 2: Buscar como producto base
    # =================
    producto_query = text("""
        SELECT 
            id_producto,
            sku,
            codigo_barras,
            nombre,
            descripcion,
            precio_base,
            es_kit,
            vida_util_dias
        FROM producto 
        WHERE id_estado = :estado_activo_id
        AND (
            LOWER(sku) LIKE LOWER(:codigo_like) 
            OR LOWER(codigo_barras) LIKE LOWER(:codigo_like)
            OR LOWER(nombre) LIKE LOWER(:codigo_like)
        )
        LIMIT 1
    """)
    
    result = await db.execute(producto_query, {
        "estado_activo_id": estado_activo_id,
        "codigo_like": f"%{codigo}%"
    })
    producto_row = result.first()
    
    if producto_row:
        # ENCONTRADO COMO PRODUCTO BASE - Buscar sus variantes
        variantes_query = text("""
            SELECT 
                pv.id_producto_variante,
                pv.sku_variante,
                pv.codigo_barras_var,
                pv.precio,
                pv.peso_gr,
                ct.nombre as talla_nombre,
                cc.nombre as color_nombre,
                ctam.nombre as tamano_nombre
            FROM producto_variante pv
            LEFT JOIN cat_talla ct ON pv.id_talla = ct.id_talla
            LEFT JOIN cat_color cc ON pv.id_color = cc.id_color
            LEFT JOIN cat_tamano ctam ON pv.id_tamano = ctam.id_tamano
            WHERE pv.id_producto = :id_producto
            AND pv.id_estado = :estado_activo_id
            ORDER BY pv.sku_variante
        """)
        
        result = await db.execute(variantes_query, {
            "id_producto": producto_row.id_producto,
            "estado_activo_id": estado_activo_id
        })
        variantes_rows = result.fetchall()
        
        # Construir información del producto
        producto_info = {
            "id_producto": str(producto_row.id_producto),
            "sku": producto_row.sku,
            "codigo_barras": producto_row.codigo_barras,
            "nombre": producto_row.nombre,
            "descripcion": producto_row.descripcion,
            "precio_base": float(producto_row.precio_base) if producto_row.precio_base else 0.0,
            "es_kit": producto_row.es_kit,
            "vida_util_dias": producto_row.vida_util_dias,
            "total_variantes": len(variantes_rows)
        }
        
        # ===== NUEVO: Manejar productos sin variantes =====
        if len(variantes_rows) == 0:
            # PRODUCTO SIN VARIANTES - Crear variante virtual del producto base
            variante_virtual = {
                "id_producto_variante": f"virtual_{producto_row.id_producto}",  # ID virtual
                "id_producto": str(producto_row.id_producto),
                "sku_variante": producto_row.sku or f"{producto_row.nombre}_BASE",
                "codigo_barras_var": producto_row.codigo_barras,
                "precio": float(producto_row.precio_base) if producto_row.precio_base else 0.0,
                "peso_gr": 0.0,
                "vida_util_dias": producto_row.vida_util_dias,
                "producto_nombre": producto_row.nombre,
                "producto_descripcion": producto_row.descripcion,
                "es_kit": producto_row.es_kit,
                "descripcion_variante": "Producto Base",
                "atributos": {
                    "talla": None,
                    "color": None,
                    "tamano": None
                }
            }
            
            return {
                "success": True,
                "tipo": "producto_sin_variantes",
                "accion_sugerida": "agregar_directo",
                "mensaje": f"Producto base encontrado: {producto_row.nombre}",
                "variante": variante_virtual,
                "producto": producto_info,
                "variantes": []
            }
        
        # ===== PRODUCTO CON VARIANTES (lógica original) =====
        # Construir lista de variantes
        variantes_info = []
        for var_row in variantes_rows:
            precio_final = float(var_row.precio) if var_row.precio else float(producto_row.precio_base) if producto_row.precio_base else 0.0
            
            # Construir descripción de atributos
            atributos = []
            if var_row.talla_nombre:
                atributos.append(f"Talla: {var_row.talla_nombre}")
            if var_row.color_nombre:
                atributos.append(f"Color: {var_row.color_nombre}")
            if var_row.tamano_nombre:
                atributos.append(f"Tamaño: {var_row.tamano_nombre}")
            
            descripcion_variante = " | ".join(atributos) if atributos else "Estándar"
            
            variantes_info.append({
                "id_producto_variante": str(var_row.id_producto_variante),
                "sku_variante": var_row.sku_variante,
                "codigo_barras_var": var_row.codigo_barras_var,
                "precio": precio_final,
                "peso_gr": float(var_row.peso_gr) if var_row.peso_gr else 0.0,
                "descripcion_variante": descripcion_variante,
                "atributos": {
                    "talla": var_row.talla_nombre,
                    "color": var_row.color_nombre,
                    "tamano": var_row.tamano_nombre
                }
            })
        
        # Determinar acción sugerida
        if len(variantes_rows) == 1:
            accion = "agregar_directo"
            mensaje = f"Producto con una variante encontrado: {producto_row.nombre}"
        else:
            accion = "mostrar_selector"
            mensaje = f"Producto encontrado con {len(variantes_rows)} variantes disponibles"
        
        return {
            "success": True,
            "tipo": "producto_base",
            "accion_sugerida": accion,
            "mensaje": mensaje,
            "variante": variantes_info[0] if len(variantes_rows) == 1 else None,
            "producto": producto_info,
            "variantes": variantes_info
        }
    
    # =================
    # NO ENCONTRADO
    # =================
    return {
        "success": False,
        "tipo": "no_encontrado",
        "accion_sugerida": "mostrar_error",
        "mensaje": f"No se encontró ningún producto con el código: {codigo}",
        "variante": None,
        "producto": None,
        "variantes": []
    }