# producto_variante.py
# ---------------------------
# Módulo de endpoints REST para gestión de Variantes de Productos
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, model_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from sqlalchemy import Column, String, Numeric, Integer, Boolean, Text, ForeignKey, DateTime, func, select, delete, and_, or_, cast
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, relationship

from db import Base, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto

# Importar modelos necesarios para joins
from producto import Producto, ProductoRead
from categoria import Categoria, CategoriaRead
from subcategoria import Subcategoria, SubcategoriaRead
from marca import Marca, MarcaRead

# ---------------------------
# Modelos ORM SQLAlchemy para catálogos
# ---------------------------
class CatTalla(Base):
    """Modelo ORM para catálogo de tallas"""
    __tablename__ = "cat_talla"
    
    id_talla = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    codigo = Column(String(10), nullable=False)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(Text)
    orden_visualizacion = Column(Integer, server_default="1")
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

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
# Modelo ORM SQLAlchemy
# ---------------------------
class ProductoVariante(Base):
    """
    Modelo ORM para la tabla producto_variante.
    Representa variantes de productos con atributos como talla, color, tamaño.
    """
    __tablename__ = "producto_variante"

    # Campos principales
    id_producto_variante = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    id_empresa     = Column(PG_UUID(as_uuid=True), nullable=False)
    id_producto    = Column(PG_UUID(as_uuid=True), ForeignKey('producto.id_producto'), nullable=False)
    id_talla       = Column(PG_UUID(as_uuid=True), nullable=True)
    id_color       = Column(PG_UUID(as_uuid=True), nullable=True)
    id_tamano      = Column(PG_UUID(as_uuid=True), nullable=True)
    sku_variante   = Column(String(50), nullable=False)
    codigo_barras_var = Column(CITEXT, nullable=True)
    precio         = Column(Numeric(14, 2), nullable=True, server_default="0")
    peso_gr        = Column(Numeric(10, 2), nullable=True, server_default="0")
    vida_util_dias = Column(Integer, nullable=True)
    id_estado      = Column(PG_UUID(as_uuid=True), nullable=False)
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

    # Relaciones con otras tablas (opcional, requiere importar modelos)
    # producto = relationship("Producto", back_populates="variantes")

# ----------------------------------
# Schemas de validación con Pydantic para catálogos
# ----------------------------------
class TallaRead(BaseModel):
    """Schema de lectura para tallas"""
    id_talla: UUID
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = None
    model_config = {"from_attributes": True}

class ColorRead(BaseModel):
    """Schema de lectura para colores"""
    id_color: UUID
    codigo: str
    nombre: str
    hex_codigo: Optional[str] = None
    descripcion: Optional[str] = None
    orden_visualizacion: Optional[int] = None
    model_config = {"from_attributes": True}

class TamanoRead(BaseModel):
    """Schema de lectura para tamaños"""
    id_tamano: UUID
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    unidad_medida: Optional[str] = None
    orden_visualizacion: Optional[int] = None
    model_config = {"from_attributes": True}

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class ProductoVarianteBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar ProductoVariante.
    """
    id_producto: UUID
    id_talla: Optional[UUID] = None
    id_color: Optional[UUID] = None
    id_tamano: Optional[UUID] = None
    sku_variante: str
    codigo_barras_var: Optional[str] = None
    precio: Optional[Decimal] = None
    peso_gr: Optional[Decimal] = None
    vida_util_dias: Optional[int] = None

class ProductoVarianteCreate(ProductoVarianteBase):
    """Esquema para creación; hereda todos los campos base."""
    
    @model_validator(mode='after')
    def validate_precio_positivo(self):
        if self.precio is not None and self.precio < 0:
            raise ValueError('El precio debe ser mayor o igual a 0')
        return self
    
    @model_validator(mode='after')
    def validate_vida_util(self):
        if self.vida_util_dias is not None and self.vida_util_dias <= 0:
            raise ValueError('La vida útil debe ser mayor a 0 días')
        return self

class ProductoVarianteUpdate(BaseModel):
    """
    Esquema para actualización con todos los campos opcionales.
    Solo se actualizarán los campos que se proporcionen.
    """
    id_talla: Optional[UUID] = None
    id_color: Optional[UUID] = None
    id_tamano: Optional[UUID] = None
    sku_variante: Optional[str] = None
    codigo_barras_var: Optional[str] = None
    precio: Optional[Decimal] = None
    peso_gr: Optional[Decimal] = None
    vida_util_dias: Optional[int] = None
    
    @model_validator(mode='after')
    def validate_precio_positivo(self):
        if self.precio is not None and self.precio < 0:
            raise ValueError('El precio debe ser mayor o igual a 0')
        return self
    
    @model_validator(mode='after')
    def validate_vida_util(self):
        if self.vida_util_dias is not None and self.vida_util_dias <= 0:
            raise ValueError('La vida útil debe ser mayor a 0 días')
        return self

class ProductoVarianteRead(ProductoVarianteBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_producto_variante: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

# ===== ESQUEMA EXPANDIDO =====
class ProductoVarianteReadExpanded(ProductoVarianteBase):
    """
    Esquema de lectura expandido con objetos relacionados completos.
    """
    id_producto_variante: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    # Objetos relacionados completos
    producto: Optional[ProductoRead] = None
    talla: Optional[TallaRead] = None
    color: Optional[ColorRead] = None
    tamano: Optional[TamanoRead] = None
    
    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/combo", response_model=dict)
async def listar_variantes_combo(
    id_producto: Optional[UUID] = Query(None, description="Filtro por ID del producto"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint optimizado para llenar ComboBox de variantes.
    Retorna solo ID y descripción simplificada.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Construir consulta base
    query = select(
        ProductoVariante.id_producto_variante,
        ProductoVariante.sku_variante,
        ProductoVariante.precio,
        Producto.nombre.label('producto_nombre')
    ).select_from(
        ProductoVariante.__table__
        .join(
            Producto.__table__,
            and_(
                ProductoVariante.id_producto == Producto.id_producto,
                Producto.id_estado == estado_activo_id
            )
        )
    ).where(ProductoVariante.id_estado == estado_activo_id)
    
    # Aplicar filtro por producto si se proporciona
    if id_producto:
        query = query.where(ProductoVariante.id_producto == id_producto)
    
    # Ordenar por SKU
    query = query.order_by(ProductoVariante.sku_variante)
    
    # Ejecutar consulta
    result = await db.execute(query)
    variantes = []
    
    for row in result:
        variantes.append({
            "id": str(row.id_producto_variante),
            "texto": f"{row.sku_variante} - {row.producto_nombre}" + (f" (${row.precio})" if row.precio else ""),
            "sku_variante": row.sku_variante,
            "precio": float(row.precio) if row.precio else None,
            "producto_nombre": row.producto_nombre
        })
    
    return {
        "success": True,
        "total_count": len(variantes),
        "data": variantes
    }

@router.get("/", response_model=dict)
async def listar_variantes(
    # ===== FILTROS BÁSICOS =====
    id_producto: Optional[UUID] = Query(None, description="Filtro por ID del producto"),
    sku_variante: Optional[str] = Query(None, description="Filtro por SKU de la variante"),
    codigo_barras_var: Optional[str] = Query(None, description="Filtro por código de barras de la variante"),
    
    # ===== FILTROS DE PRECIO =====
    precio: Optional[float] = Query(None, description="Precio exacto"),
    precio_min: Optional[float] = Query(None, description="Precio mínimo (>=)"),
    precio_max: Optional[float] = Query(None, description="Precio máximo (<=)"),
    
    # ===== FILTROS POR ATRIBUTOS =====
    id_talla: Optional[UUID] = Query(None, description="Filtro por ID de talla"),
    id_color: Optional[UUID] = Query(None, description="Filtro por ID de color"),
    id_tamano: Optional[UUID] = Query(None, description="Filtro por ID de tamaño"),
    
    # ===== NUEVOS FILTROS POR NOMBRES =====
    producto_nombre: Optional[str] = Query(None, description="Filtro por nombre del producto"),
    marca_nombre: Optional[str] = Query(None, description="Filtro por nombre de la marca"),
    categoria_nombre: Optional[str] = Query(None, description="Filtro por nombre de la categoría"),
    subcategoria_nombre: Optional[str] = Query(None, description="Filtro por nombre de la subcategoría"),
    
    # ===== PARÁMETROS DE CONFIGURACIÓN =====
    expandir: bool = Query(False, description="Incluir objetos relacionados completos"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista variantes de productos en estado "activo" con paginación, filtros opcionales
    y opción de expandir objetos relacionados.
    INCLUYE SIEMPRE los nombres de categoría, subcategoría y marca para StringGrid.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # ===== CONSULTA ÚNICA CON TODOS LOS JOINS NECESARIOS =====
    # Siempre incluimos joins para obtener los nombres, independientemente del valor de 'expandir'
    if expandir:
        # ===== CONSULTA CON JOINS PARA OBJETOS RELACIONADOS COMPLETOS =====
        query = select(
            ProductoVariante,
            Producto,
            CatTalla,
            CatColor,
            CatTamano,
            Categoria,
            Subcategoria,
            Marca
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTalla.__table__,
                and_(
                    ProductoVariante.id_talla == CatTalla.id_talla,
                    CatTalla.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatColor.__table__,
                and_(
                    ProductoVariante.id_color == CatColor.id_color,
                    CatColor.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTamano.__table__,
                and_(
                    ProductoVariante.id_tamano == CatTamano.id_tamano,
                    CatTamano.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(ProductoVariante.id_estado == estado_activo_id)

    else:
        # ===== CONSULTA OPTIMIZADA PARA STRINGGRID (SIN OBJETOS COMPLETOS) =====
        query = select(
            ProductoVariante,
            Producto.nombre.label('producto_nombre'),
            Categoria.nombre.label('categoria_nombre'),
            Subcategoria.nombre.label('subcategoria_nombre'),
            Marca.nombre.label('marca_nombre')
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(ProductoVariante.id_estado == estado_activo_id)

    # ===== APLICAR FILTROS =====
    if id_producto:
        query = query.where(ProductoVariante.id_producto == id_producto)
    if sku_variante:
        query = query.where(ProductoVariante.sku_variante.ilike(f"%{sku_variante}%"))
    if codigo_barras_var:
        query = query.where(ProductoVariante.codigo_barras_var.ilike(f"%{codigo_barras_var}%"))
    if precio is not None:
        query = query.where(ProductoVariante.precio == precio)
    if precio_min is not None:
        query = query.where(ProductoVariante.precio >= precio_min)
    if precio_max is not None:
        query = query.where(ProductoVariante.precio <= precio_max)
    if id_talla:
        query = query.where(ProductoVariante.id_talla == id_talla)
    if id_color:
        query = query.where(ProductoVariante.id_color == id_color)
    if id_tamano:
        query = query.where(ProductoVariante.id_tamano == id_tamano)
    
    # ===== NUEVOS FILTROS POR NOMBRES =====
    if producto_nombre:
        query = query.where(Producto.nombre.ilike(f"%{producto_nombre}%"))
    if marca_nombre:
        query = query.where(Marca.nombre.ilike(f"%{marca_nombre}%"))
    if categoria_nombre:
        query = query.where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
    if subcategoria_nombre:
        query = query.where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))

    # ===== CONTAR TOTAL =====
    count_query = select(func.count(ProductoVariante.id_producto_variante)).select_from(
        ProductoVariante.__table__
        .outerjoin(
            Producto.__table__,
            and_(
                ProductoVariante.id_producto == Producto.id_producto,
                Producto.id_estado == estado_activo_id
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
        .outerjoin(
            Marca.__table__,
            and_(
                Producto.id_marca == Marca.id_marca,
                Marca.id_estado == estado_activo_id
            )
        )
    ).where(ProductoVariante.id_estado == estado_activo_id)
    
    # Aplicar mismos filtros al conteo
    if id_producto:
        count_query = count_query.where(ProductoVariante.id_producto == id_producto)
    if sku_variante:
        count_query = count_query.where(ProductoVariante.sku_variante.ilike(f"%{sku_variante}%"))
    if codigo_barras_var:
        count_query = count_query.where(ProductoVariante.codigo_barras_var.ilike(f"%{codigo_barras_var}%"))
    if precio is not None:
        count_query = count_query.where(ProductoVariante.precio == precio)
    if precio_min is not None:
        count_query = count_query.where(ProductoVariante.precio >= precio_min)
    if precio_max is not None:
        count_query = count_query.where(ProductoVariante.precio <= precio_max)
    if id_talla:
        count_query = count_query.where(ProductoVariante.id_talla == id_talla)
    if id_color:
        count_query = count_query.where(ProductoVariante.id_color == id_color)
    if id_tamano:
        count_query = count_query.where(ProductoVariante.id_tamano == id_tamano)
    
    # ===== NUEVOS FILTROS POR NOMBRES EN EL CONTEO =====
    if producto_nombre:
        count_query = count_query.where(Producto.nombre.ilike(f"%{producto_nombre}%"))
    if marca_nombre:
        count_query = count_query.where(Marca.nombre.ilike(f"%{marca_nombre}%"))
    if categoria_nombre:
        count_query = count_query.where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
    if subcategoria_nombre:
        count_query = count_query.where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))

    total = await db.scalar(count_query)

    # ===== EJECUTAR CONSULTA PAGINADA =====
    result = await db.execute(query.offset(skip).limit(limit))
    
    # ===== CONSTRUIR RESPUESTA =====
    data = []
    
    if expandir:
        # ===== RESPUESTA EXPANDIDA CON OBJETOS COMPLETOS =====
        for row in result:
            variante_obj = row[0]  # Objeto ProductoVariante
            producto_obj = row[1]  # Objeto Producto (puede ser None)
            talla_obj = row[2]     # Objeto CatTalla (puede ser None)
            color_obj = row[3]     # Objeto CatColor (puede ser None)
            tamano_obj = row[4]    # Objeto CatTamano (puede ser None)
            categoria_obj = row[5] # Objeto Categoria (puede ser None)
            subcategoria_obj = row[6] # Objeto Subcategoria (puede ser None)
            marca_obj = row[7]     # Objeto Marca (puede ser None)
            
            # Convertir variante base
            variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
            
            # Agregar objetos relacionados si existen
            variante_dict['producto'] = ProductoRead.model_validate(producto_obj).model_dump() if producto_obj else None
            variante_dict['talla'] = TallaRead.model_validate(talla_obj).model_dump() if talla_obj else None
            variante_dict['color'] = ColorRead.model_validate(color_obj).model_dump() if color_obj else None
            variante_dict['tamano'] = TamanoRead.model_validate(tamano_obj).model_dump() if tamano_obj else None
            variante_dict['categoria'] = CategoriaRead.model_validate(categoria_obj).model_dump() if categoria_obj else None
            variante_dict['subcategoria'] = SubcategoriaRead.model_validate(subcategoria_obj).model_dump() if subcategoria_obj else None
            variante_dict['marca'] = MarcaRead.model_validate(marca_obj).model_dump() if marca_obj else None
            
            # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
            variante_dict['producto_nombre'] = producto_obj.nombre if producto_obj else None
            variante_dict['categoria_nombre'] = categoria_obj.nombre if categoria_obj else None
            variante_dict['subcategoria_nombre'] = subcategoria_obj.nombre if subcategoria_obj else None
            variante_dict['marca_nombre'] = marca_obj.nombre if marca_obj else None
            
            data.append(variante_dict)

    else:
        # ===== RESPUESTA OPTIMIZADA PARA STRINGGRID =====
        for row in result:
            variante_obj = row[0]  # Objeto ProductoVariante
            producto_nombre = row[1]      # String
            categoria_nombre = row[2]     # String (puede ser None)
            subcategoria_nombre = row[3]  # String (puede ser None)
            marca_nombre = row[4]         # String (puede ser None)
            
            # Convertir variante base
            variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
            
            # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
            variante_dict['producto_nombre'] = producto_nombre
            variante_dict['categoria_nombre'] = categoria_nombre
            variante_dict['subcategoria_nombre'] = subcategoria_nombre
            variante_dict['marca_nombre'] = marca_nombre
            
            data.append(variante_dict)

    return {
        "success": True,
        "total_count": total,
        "expandido": expandir,
        "filtros_aplicados": {
            "basicos": {
                "id_producto": str(id_producto) if id_producto else None,
                "sku_variante": sku_variante,
                "codigo_barras_var": codigo_barras_var
            },
            "precio": {
                "exacto": precio,
                "min": precio_min,
                "max": precio_max
            },
            "atributos": {
                "id_talla": str(id_talla) if id_talla else None,
                "id_color": str(id_color) if id_color else None,
                "id_tamano": str(id_tamano) if id_tamano else None
            },
            "nombres": {
                "producto_nombre": producto_nombre,
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

@router.get("/{id_producto_variante}", response_model=dict)
async def obtener_variante(
    id_producto_variante: UUID,
    expandir: bool = Query(False, description="Incluir objetos relacionados completos"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una variante por su ID, con opción de expandir objetos relacionados.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    if expandir:
        # Consulta con joins para objetos relacionados
        query = select(
            ProductoVariante,
            Producto,
            CatTalla,
            CatColor,
            CatTamano,
            Categoria,
            Subcategoria,
            Marca
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTalla.__table__,
                and_(
                    ProductoVariante.id_talla == CatTalla.id_talla,
                    CatTalla.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatColor.__table__,
                and_(
                    ProductoVariante.id_color == CatColor.id_color,
                    CatColor.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTamano.__table__,
                and_(
                    ProductoVariante.id_tamano == CatTamano.id_tamano,
                    CatTamano.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(
            and_(
                ProductoVariante.id_producto_variante == id_producto_variante,
                ProductoVariante.id_estado == estado_activo_id
            )
        )
        
        result = await db.execute(query)
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Variante no encontrada")
        
        # Construir respuesta expandida
        variante_obj = row[0]
        producto_obj = row[1]
        talla_obj = row[2]
        color_obj = row[3]
        tamano_obj = row[4]
        categoria_obj = row[5]
        subcategoria_obj = row[6]
        marca_obj = row[7]
        
        variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
        
        variante_dict['producto'] = ProductoRead.model_validate(producto_obj).model_dump() if producto_obj else None
        variante_dict['talla'] = TallaRead.model_validate(talla_obj).model_dump() if talla_obj else None
        variante_dict['color'] = ColorRead.model_validate(color_obj).model_dump() if color_obj else None
        variante_dict['tamano'] = TamanoRead.model_validate(tamano_obj).model_dump() if tamano_obj else None
        variante_dict['categoria'] = CategoriaRead.model_validate(categoria_obj).model_dump() if categoria_obj else None
        variante_dict['subcategoria'] = SubcategoriaRead.model_validate(subcategoria_obj).model_dump() if subcategoria_obj else None
        variante_dict['marca'] = MarcaRead.model_validate(marca_obj).model_dump() if marca_obj else None
        
        # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
        variante_dict['producto_nombre'] = producto_obj.nombre if producto_obj else None
        variante_dict['categoria_nombre'] = categoria_obj.nombre if categoria_obj else None
        variante_dict['subcategoria_nombre'] = subcategoria_obj.nombre if subcategoria_obj else None
        variante_dict['marca_nombre'] = marca_obj.nombre if marca_obj else None
        
        return {
            "success": True,
            "expandido": expandir,
            "data": variante_dict
        }
    
    else:
        # Consulta optimizada con nombres
        query = select(
            ProductoVariante,
            Producto.nombre.label('producto_nombre'),
            Categoria.nombre.label('categoria_nombre'),
            Subcategoria.nombre.label('subcategoria_nombre'),
            Marca.nombre.label('marca_nombre')
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(
            and_(
                ProductoVariante.id_producto_variante == id_producto_variante,
                ProductoVariante.id_estado == estado_activo_id
            )
        )
        
        result = await db.execute(query)
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Variante no encontrada")
        
        variante_obj = row[0]
        producto_nombre = row[1]
        categoria_nombre = row[2]
        subcategoria_nombre = row[3]
        marca_nombre = row[4]
        
        variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
        
        # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
        variante_dict['producto_nombre'] = producto_nombre
        variante_dict['categoria_nombre'] = categoria_nombre
        variante_dict['subcategoria_nombre'] = subcategoria_nombre
        variante_dict['marca_nombre'] = marca_nombre
        
        return {
            "success": True,
            "expandido": expandir,
            "data": variante_dict
        }

@router.post("/", response_model=dict, status_code=201)
async def crear_variante(
    variante_data: ProductoVarianteCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva variante de producto.
    """
    from uuid import uuid4
    from sqlalchemy import text
    
    # ✅ IMPORTACIONES NECESARIAS para las validaciones
    # Asegúrate de que estos imports estén al inicio del archivo producto_variante.py
    # from producto import Producto
    # Ya tenemos: CatTalla, CatColor, CatTamano
    
    try:
        # ✅ CORRECCIÓN 1: Usar obtener_contexto() como diccionario
        estado_activo_id = await get_estado_id_por_clave("act", db)
        ctx = await obtener_contexto(db)  # ✅ Es un diccionario
        
        # ✅ VALIDACIÓN 1: Verificar que el producto existe
        producto_query = select(Producto).where(
            Producto.id_producto == variante_data.id_producto,
            Producto.id_estado == estado_activo_id
        )
        producto_result = await db.execute(producto_query)
        producto = producto_result.scalar_one_or_none()
        
        if not producto:
            raise HTTPException(
                status_code=404, 
                detail=f"No existe un producto con ID {variante_data.id_producto}"
            )
        
        # ✅ VALIDACIÓN 2: Verificar que el SKU no existe
        sku_query = select(ProductoVariante).where(
            ProductoVariante.sku_variante == variante_data.sku_variante,
            ProductoVariante.id_empresa == ctx["tenant_id"],
            ProductoVariante.id_estado == estado_activo_id
        )
        sku_result = await db.execute(sku_query)
        if sku_result.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe una variante con SKU '{variante_data.sku_variante}' en la empresa"
            )
        
        # ✅ VALIDACIÓN 3: Verificar código de barras si se proporciona
        if variante_data.codigo_barras_var:
            codigo_query = select(ProductoVariante).where(
                ProductoVariante.codigo_barras_var == variante_data.codigo_barras_var,
                ProductoVariante.id_empresa == ctx["tenant_id"],
                ProductoVariante.id_estado == estado_activo_id
            )
            codigo_result = await db.execute(codigo_query)
            if codigo_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe una variante con código de barras '{variante_data.codigo_barras_var}' en la empresa"
                )
        
        # ✅ VALIDACIÓN 4: Verificar atributos de variante si se proporcionan
        if variante_data.id_talla:
            talla_query = select(CatTalla).where(
                CatTalla.id_talla == variante_data.id_talla,
                CatTalla.id_empresa == ctx["tenant_id"],
                CatTalla.id_estado == estado_activo_id
            )
            talla_result = await db.execute(talla_query)
            if not talla_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe una talla con ID {variante_data.id_talla} en la empresa"
                )
        
        if variante_data.id_color:
            color_query = select(CatColor).where(
                CatColor.id_color == variante_data.id_color,
                CatColor.id_empresa == ctx["tenant_id"],
                CatColor.id_estado == estado_activo_id
            )
            color_result = await db.execute(color_query)
            if not color_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe un color con ID {variante_data.id_color} en la empresa"
                )
        
        if variante_data.id_tamano:
            tamano_query = select(CatTamano).where(
                CatTamano.id_tamano == variante_data.id_tamano,
                CatTamano.id_empresa == ctx["tenant_id"],
                CatTamano.id_estado == estado_activo_id
            )
            tamano_result = await db.execute(tamano_query)
            if not tamano_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail=f"No existe un tamaño con ID {variante_data.id_tamano} en la empresa"
                )
        
        # ✅ CREAR NUEVA VARIANTE CON CONTEXTO CORRECTO
        nueva_variante = ProductoVariante(
            id_empresa=ctx["tenant_id"],      # ✅ Usar diccionario
            id_estado=estado_activo_id,
            created_by=ctx["user_id"],        # ✅ Usar diccionario  
            modified_by=ctx["user_id"],       # ✅ Usar diccionario
            **variante_data.model_dump()
        )
        
        db.add(nueva_variante)
        await db.flush()      # ✅ Flush antes de refresh
        await db.refresh(nueva_variante)
        await db.commit()
        
        return {
            "success": True,
            "message": "Variante creada exitosamente",
            "data": ProductoVarianteRead.model_validate(nueva_variante).model_dump()
        }
        
    except HTTPException:
        # ✅ Re-lanzar HTTPExceptions existentes
        await db.rollback()
        raise
        
    except Exception as e:
        # ✅ MEJOR MANEJO DE ERRORES - Mostrar error específico
        await db.rollback()
        
        error_str = str(e).lower()
        
        # Errores de constraint específicos
        if "uq_variante_empresa_sku" in error_str:
            raise HTTPException(
                status_code=409, 
                detail="Ya existe una variante con ese SKU en la empresa"
            )
        elif "uq_variante_empresa_codbar" in error_str:
            raise HTTPException(
                status_code=409, 
                detail="Ya existe una variante con ese código de barras en la empresa"
            )
        elif "foreign key" in error_str:
            if "id_producto" in error_str:
                raise HTTPException(
                    status_code=400,
                    detail="El ID del producto no es válido"
                )
            elif "id_talla" in error_str:
                raise HTTPException(
                    status_code=400,
                    detail="El ID de talla no es válido"
                )
            elif "id_color" in error_str:
                raise HTTPException(
                    status_code=400,
                    detail="El ID de color no es válido"
                )
            elif "id_tamano" in error_str:
                raise HTTPException(
                    status_code=400,
                    detail="El ID de tamaño no es válido"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Error de referencia de clave foránea"
                )
        elif "check constraint" in error_str:
            raise HTTPException(
                status_code=400,
                detail="Error de validación en los datos proporcionados"
            )
        elif "not null" in error_str:
            raise HTTPException(
                status_code=400,
                detail="Faltan campos obligatorios"
            )
        else:
            # ✅ Mostrar error específico en desarrollo
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )

@router.put("/{id_producto_variante}", response_model=dict)
async def actualizar_variante(
    id_producto_variante: UUID,
    variante_data: ProductoVarianteUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza una variante existente.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    tenant_id, user_id = await obtener_contexto(db)
    
    # Buscar variante existente
    query = select(ProductoVariante).where(
        and_(
            ProductoVariante.id_producto_variante == id_producto_variante,
            ProductoVariante.id_estado == estado_activo_id
        )
    )
    
    result = await db.execute(query)
    variante = result.scalar_one_or_none()
    
    if not variante:
        raise HTTPException(status_code=404, detail="Variante no encontrada")
    
    # Actualizar campos proporcionados
    update_data = variante_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(variante, field, value)
    
    variante.modified_by = user_id
    
    try:
        await db.commit()
        await db.refresh(variante)
        
        return {
            "success": True,
            "message": "Variante actualizada exitosamente",
            "data": ProductoVarianteRead.model_validate(variante).model_dump()
        }
    except Exception as e:
        await db.rollback()
        if "uq_variante_empresa_sku" in str(e):
            raise HTTPException(status_code=409, detail="Ya existe una variante con ese SKU en la empresa")
        elif "uq_variante_empresa_codbar" in str(e):
            raise HTTPException(status_code=409, detail="Ya existe una variante con ese código de barras en la empresa")
        else:
            raise HTTPException(status_code=400, detail="Error al actualizar la variante")

@router.delete("/{id_producto_variante}", status_code=200)
async def eliminar_variante(
    id_producto_variante: UUID, 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una variante. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(
        select(ProductoVariante).where(
            ProductoVariante.id_producto_variante == id_producto_variante
        )
    )
    variante = result.scalar_one_or_none()
    if not variante:
        raise HTTPException(status_code=404, detail="Variante no encontrada")

    # 2) Ejecutar DELETE
    await db.execute(
        delete(ProductoVariante).where(
            ProductoVariante.id_producto_variante == id_producto_variante
        )
    )

    # 3) Confirmar transacción
    await db.commit()

    # 4) Responder al cliente
    return {"success": True, "message": "Variante eliminada permanentemente"}

# ===== ENDPOINTS ADICIONALES =====

@router.get("/producto/{id_producto}/variantes", response_model=dict)
async def listar_variantes_por_producto(
    id_producto: UUID = Path(..., description="ID del producto"),
    expandir: bool = Query(False, description="Incluir objetos relacionados completos"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista todas las variantes activas de un producto específico.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    if expandir:
        # Consulta con joins para objetos relacionados
        query = select(
            ProductoVariante,
            Producto,
            CatTalla,
            CatColor,
            CatTamano,
            Categoria,
            Subcategoria,
            Marca
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTalla.__table__,
                and_(
                    ProductoVariante.id_talla == CatTalla.id_talla,
                    CatTalla.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatColor.__table__,
                and_(
                    ProductoVariante.id_color == CatColor.id_color,
                    CatColor.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                CatTamano.__table__,
                and_(
                    ProductoVariante.id_tamano == CatTamano.id_tamano,
                    CatTamano.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(
            and_(
                ProductoVariante.id_producto == id_producto,
                ProductoVariante.id_estado == estado_activo_id
            )
        )

        # Contar total
        count_query = select(func.count(ProductoVariante.id_producto_variante)).where(
            and_(
                ProductoVariante.id_producto == id_producto,
                ProductoVariante.id_estado == estado_activo_id
            )
        )
        total = await db.scalar(count_query)

        # Obtener variantes paginadas
        result = await db.execute(query.offset(skip).limit(limit))
        
        # Construir respuesta expandida
        data = []
        for row in result:
            variante_obj = row[0]
            producto_obj = row[1]
            talla_obj = row[2]
            color_obj = row[3]
            tamano_obj = row[4]
            categoria_obj = row[5]
            subcategoria_obj = row[6]
            marca_obj = row[7]
            
            variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
            
            variante_dict['producto'] = ProductoRead.model_validate(producto_obj).model_dump() if producto_obj else None
            variante_dict['talla'] = TallaRead.model_validate(talla_obj).model_dump() if talla_obj else None
            variante_dict['color'] = ColorRead.model_validate(color_obj).model_dump() if color_obj else None
            variante_dict['tamano'] = TamanoRead.model_validate(tamano_obj).model_dump() if tamano_obj else None
            variante_dict['categoria'] = CategoriaRead.model_validate(categoria_obj).model_dump() if categoria_obj else None
            variante_dict['subcategoria'] = SubcategoriaRead.model_validate(subcategoria_obj).model_dump() if subcategoria_obj else None
            variante_dict['marca'] = MarcaRead.model_validate(marca_obj).model_dump() if marca_obj else None
            
            # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
            variante_dict['producto_nombre'] = producto_obj.nombre if producto_obj else None
            variante_dict['categoria_nombre'] = categoria_obj.nombre if categoria_obj else None
            variante_dict['subcategoria_nombre'] = subcategoria_obj.nombre if subcategoria_obj else None
            variante_dict['marca_nombre'] = marca_obj.nombre if marca_obj else None
            
            data.append(variante_dict)
    
    else:
        # Consulta simple con nombres
        count_query = select(func.count(ProductoVariante.id_producto_variante)).where(
            and_(
                ProductoVariante.id_producto == id_producto,
                ProductoVariante.id_estado == estado_activo_id
            )
        )
        total = await db.scalar(count_query)
        
        query = select(
            ProductoVariante,
            Producto.nombre.label('producto_nombre'),
            Categoria.nombre.label('categoria_nombre'),
            Subcategoria.nombre.label('subcategoria_nombre'),
            Marca.nombre.label('marca_nombre')
        ).select_from(
            ProductoVariante.__table__
            .outerjoin(
                Producto.__table__,
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
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
            .outerjoin(
                Marca.__table__,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
        ).where(
            and_(
                ProductoVariante.id_producto == id_producto,
                ProductoVariante.id_estado == estado_activo_id
            )
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        
        data = []
        for row in result:
            variante_obj = row[0]
            producto_nombre = row[1]
            categoria_nombre = row[2]
            subcategoria_nombre = row[3]
            marca_nombre = row[4]
            
            variante_dict = ProductoVarianteRead.model_validate(variante_obj).model_dump()
            
            # AÑADIR NOMBRES DIRECTOS PARA STRINGGRID
            variante_dict['producto_nombre'] = producto_nombre
            variante_dict['categoria_nombre'] = categoria_nombre
            variante_dict['subcategoria_nombre'] = subcategoria_nombre
            variante_dict['marca_nombre'] = marca_nombre
            
            data.append(variante_dict)
    
    return {
        "success": True,
        "total_count": total,
        "expandido": expandir,
        "paginacion": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "pagina_actual": (skip // limit) + 1,
            "total_paginas": ((total - 1) // limit) + 1 if total > 0 else 0
        },
        "data": data
    }