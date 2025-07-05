# producto.py - VERSIÓN EXPANDIDA CON FILTROS EXTENDIDOS
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Producto.
# Incluye objetos relacionados completos y filtros avanzados

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional                                      # Tipos para anotaciones
from uuid import UUID                                            # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from decimal import Decimal                                      # Para campos numéricos de alta precisión
from sqlalchemy import (
    Column, String, Text, DateTime, Numeric, Boolean, Integer,
    func, select, text, delete, and_, or_
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
    articulo       = Column(String(20))
    guid           = Column(String(36))
    costo_u        = Column(Numeric(14, 2))
    linea          = Column(String(100))
    sublinea       = Column(String(100))
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
    articulo: Optional[str] = None
    guid: Optional[str] = None
    costo_u: Optional[Decimal] = None
    linea: Optional[str] = None
    sublinea: Optional[str] = None
    id_categoria: Optional[UUID] = None
    id_subcategoria: Optional[UUID] = None

class ProductoCreate(ProductoBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ProductoUpdate(ProductoBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

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
    
    ✅ FILTROS SOPORTADOS:
    - Básicos: nombre, sku, codigo_barras
    - Precio: exacto, rangos (min/max), comparaciones (>/< y >=/<=)
    - Entidades relacionadas: búsqueda por nombre en marca, categoría, subcategoría
    
    ✅ EJEMPLOS DE USO:
    - /productos?nombre=iPhone&marca_nombre=Apple
    - /productos?precio_min=500&precio_max=1000&categoria_nombre=Tecnología
    - /productos?precio_mayor=300&subcategoria_nombre=Smartphones
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # ===== FUNCIÓN AUXILIAR PARA APLICAR FILTROS =====
    def aplicar_filtros_basicos(stmt):
        """Aplica filtros básicos que funcionan tanto con joins como sin joins"""
        if nombre:
            stmt = stmt.where(Producto.nombre.ilike(f"%{nombre}%"))
        if sku:
            stmt = stmt.where(Producto.sku.ilike(f"%{sku}%"))
        if codigo_barras:
            stmt = stmt.where(Producto.codigo_barras.ilike(f"%{codigo_barras}%"))
        
        # ===== FILTROS DE PRECIO =====
        if precio is not None:
            stmt = stmt.where(Producto.precio_base == precio)
        if precio_min is not None:
            stmt = stmt.where(Producto.precio_base >= precio_min)
        if precio_max is not None:
            stmt = stmt.where(Producto.precio_base <= precio_max)
        if precio_mayor is not None:
            stmt = stmt.where(Producto.precio_base > precio_mayor)
        if precio_menor is not None:
            stmt = stmt.where(Producto.precio_base < precio_menor)
        if precio_texto:
            # Búsqueda textual en precio (útil para formatos como "$100.00")
            stmt = stmt.where(func.cast(Producto.precio_base, String).ilike(f"%{precio_texto}%"))
        
        return stmt
    
    def aplicar_filtros_entidades(stmt):
        """Aplica filtros por nombres de entidades relacionadas (solo para consultas con joins)"""
        if marca_nombre:
            stmt = stmt.where(Marca.nombre.ilike(f"%{marca_nombre}%"))
        if categoria_nombre:
            stmt = stmt.where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
        if subcategoria_nombre:
            stmt = stmt.where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))
        return stmt
    
    if expandir:
        # ===== CONSULTA CON JOINS PARA OBJETOS RELACIONADOS =====
        stmt = (
            select(
                Producto,
                Marca,
                UMedida,
                Categoria,
                Subcategoria
            )
            .outerjoin(
                Marca, 
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                UMedida, 
                and_(
                    Producto.id_umedida == UMedida.id_umedida,
                    UMedida.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Categoria, 
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Subcategoria, 
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            )
            .where(Producto.id_estado == estado_activo_id)
        )
        
        # Aplicar todos los filtros
        stmt = aplicar_filtros_basicos(stmt)
        stmt = aplicar_filtros_entidades(stmt)
        
        # ===== CONTAR TOTAL PARA PAGINACIÓN (con los mismos filtros) =====
        count_stmt = (
            select(func.count(Producto.id_producto))
            .select_from(
                Producto
                .outerjoin(
                    Marca, 
                    and_(
                        Producto.id_marca == Marca.id_marca,
                        Marca.id_estado == estado_activo_id
                    )
                )
                .outerjoin(
                    Categoria, 
                    and_(
                        Producto.id_categoria == Categoria.id_categoria,
                        Categoria.id_estado == estado_activo_id
                    )
                )
                .outerjoin(
                    Subcategoria, 
                    and_(
                        Producto.id_subcategoria == Subcategoria.id_subcategoria,
                        Subcategoria.id_estado == estado_activo_id
                    )
                )
            )
            .where(Producto.id_estado == estado_activo_id)
        )
        count_stmt = aplicar_filtros_basicos(count_stmt)
        count_stmt = aplicar_filtros_entidades(count_stmt)
        
        total = await db.scalar(count_stmt)
        
        # Ejecutar consulta paginada
        result = await db.execute(stmt.offset(skip).limit(limit))
        
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
        # ===== CONSULTA SIN JOINS (CON JOINS CONDICIONALES PARA FILTROS DE ENTIDADES) =====
        stmt = select(Producto).where(Producto.id_estado == estado_activo_id)
        
        # Aplicar filtros básicos
        stmt = aplicar_filtros_basicos(stmt)
        
        # ===== APLICAR FILTROS DE ENTIDADES RELACIONADAS (requieren joins específicos) =====
        joins_added = []
        
        if marca_nombre:
            stmt = stmt.join(
                Marca,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            ).where(Marca.nombre.ilike(f"%{marca_nombre}%"))
            joins_added.append("marca")
        
        if categoria_nombre:
            stmt = stmt.join(
                Categoria,
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            ).where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
            joins_added.append("categoria")
        
        if subcategoria_nombre:
            stmt = stmt.join(
                Subcategoria,
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            ).where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))
            joins_added.append("subcategoria")
        
        # Contar total (replicando los mismos joins y filtros)
        count_stmt = select(func.count(Producto.id_producto)).where(Producto.id_estado == estado_activo_id)
        count_stmt = aplicar_filtros_basicos(count_stmt)
        
        if marca_nombre:
            count_stmt = count_stmt.join(
                Marca,
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            ).where(Marca.nombre.ilike(f"%{marca_nombre}%"))
        
        if categoria_nombre:
            count_stmt = count_stmt.join(
                Categoria,
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            ).where(Categoria.nombre.ilike(f"%{categoria_nombre}%"))
        
        if subcategoria_nombre:
            count_stmt = count_stmt.join(
                Subcategoria,
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            ).where(Subcategoria.nombre.ilike(f"%{subcategoria_nombre}%"))
        
        total = await db.scalar(count_stmt)
        
        # Ejecutar consulta paginada
        result = await db.execute(stmt.offset(skip).limit(limit))
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
        # Consulta con joins
        stmt = (
            select(
                Producto,
                Marca,
                UMedida,
                Categoria,
                Subcategoria
            )
            .outerjoin(
                Marca, 
                and_(
                    Producto.id_marca == Marca.id_marca,
                    Marca.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                UMedida, 
                and_(
                    Producto.id_umedida == UMedida.id_umedida,
                    UMedida.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Categoria, 
                and_(
                    Producto.id_categoria == Categoria.id_categoria,
                    Categoria.id_estado == estado_activo_id
                )
            )
            .outerjoin(
                Subcategoria, 
                and_(
                    Producto.id_subcategoria == Subcategoria.id_subcategoria,
                    Subcategoria.id_estado == estado_activo_id
                )
            )
            .where(
                Producto.id_producto == id_producto,
                Producto.id_estado == estado_activo_id
            )
        )
        
        result = await db.execute(stmt)
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
        stmt = select(Producto).where(
            Producto.id_producto == id_producto,
            Producto.id_estado == estado_activo_id
        )
        result = await db.execute(stmt)
        producto = result.scalar_one_or_none()
        
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        
        return {
            "success": True,
            "expandido": False,
            "data": ProductoRead.model_validate(producto).model_dump()
        }

# ===== RESTO DE ENDPOINTS PERMANECEN IGUAL =====

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
        articulo        = entrada.articulo,
        guid            = entrada.guid,
        costo_u         = entrada.costo_u,
        linea           = entrada.linea,
        sublinea        = entrada.sublinea,
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
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    stmt = select(Producto).where(
        Producto.id_producto == id_producto,
        Producto.id_estado    == estado_activo_id
    )
    result = await db.execute(stmt)
    producto = result.scalar_one_or_none()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    ctx = await obtener_contexto(db)
    producto.sku             = entrada.sku
    producto.codigo_barras   = entrada.codigo_barras
    producto.nombre          = entrada.nombre
    producto.descripcion     = entrada.descripcion
    producto.precio_base     = entrada.precio_base
    producto.es_kit          = entrada.es_kit
    producto.vida_util_dias  = entrada.vida_util_dias
    producto.id_marca        = entrada.id_marca
    producto.id_umedida      = entrada.id_umedida
    producto.articulo        = entrada.articulo
    producto.guid            = entrada.guid
    producto.costo_u         = entrada.costo_u
    producto.linea           = entrada.linea
    producto.sublinea        = entrada.sublinea
    producto.id_categoria    = entrada.id_categoria
    producto.id_subcategoria = entrada.id_subcategoria
    producto.modified_by     = ctx["user_id"]
    await db.flush()
    await db.refresh(producto)
    await db.commit()
    return {"success": True, "data": ProductoRead.model_validate(producto)}

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