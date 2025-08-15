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

# producto.py - ENDPOINT CREAR PRODUCTO ACTUALIZADO
# ---------------------------
# Reemplazar el endpoint de creación de productos existente

from utils.variante_base import crear_variante_base_automatica

@router.post("/", response_model=dict, status_code=201)
async def crear_producto(
    entrada: ProductoCreate,
    crear_variante_base: bool = Query(True, description="Crear variante base automáticamente si no se especifican variantes"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo producto con variante base automática.
    
    NUEVA FUNCIONALIDAD:
    - Si crear_variante_base=True (default), siempre crea una variante base
    - Garantiza que el producto sea vendible inmediatamente
    - Mantiene consistencia en la base de datos
    - DEVUELVE INFORMACIÓN EXPANDIDA con nombres de entidades relacionadas
    """
    
    ctx = await obtener_contexto(db)
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Verificar que el SKU no exista
    sku_existente = await db.execute(
        select(Producto).where(Producto.sku == entrada.sku)
    )
    if sku_existente.scalar_one_or_none():
        raise HTTPException(
            status_code=409, 
            detail=f"Ya existe un producto con el SKU: {entrada.sku}"
        )
    
    # Verificar código de barras si se proporciona
    if entrada.codigo_barras:
        codigo_existente = await db.execute(
            select(Producto).where(Producto.codigo_barras == entrada.codigo_barras)
        )
        if codigo_existente.scalar_one_or_none():
            raise HTTPException(
                status_code=409, 
                detail=f"Ya existe un producto con el código de barras: {entrada.codigo_barras}"
            )
    
    try:
        # ===== CREAR EL PRODUCTO =====
        nuevo_producto = Producto(
            sku=entrada.sku,
            codigo_barras=entrada.codigo_barras,
            nombre=entrada.nombre,
            descripcion=entrada.descripcion,
            precio_base=entrada.precio_base,
            costo_u=entrada.costo_u,
            es_kit=entrada.es_kit,
            vida_util_dias=entrada.vida_util_dias,
            guid=entrada.guid,
            
            # Relaciones
            id_marca=entrada.id_marca,
            id_umedida=entrada.id_umedida,
            id_categoria=entrada.id_categoria,
            id_subcategoria=entrada.id_subcategoria,
            
            # Campos de auditoría
            id_estado=estado_activo_id,
            created_by=ctx["user_id"],
            modified_by=ctx["user_id"]
        )
        
        db.add(nuevo_producto)
        await db.flush()  # Para obtener el ID
        await db.refresh(nuevo_producto)
        
        # ===== CREAR VARIANTE BASE AUTOMÁTICAMENTE =====
        variante_base = None
        if crear_variante_base:
            try:
                variante_base = await crear_variante_base_automatica(
                    id_producto=nuevo_producto.id_producto,
                    db=db,
                    precio_override=float(entrada.precio_base) if entrada.precio_base else None
                )
                
                print(f"✅ Variante base creada automáticamente: {variante_base.sku_variante}")
                
            except Exception as e:
                # Si falla la creación de variante, rollback todo
                await db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Error creando variante base automática: {str(e)}"
                )
        
        # Confirmar transacción
        await db.commit()
        
        # ===== RESPUESTA SIMPLIFICADA =====
        respuesta = {
            "success": True,
            "message": "Producto creado correctamente",
            "data": {
                "id_producto": str(nuevo_producto.id_producto),
                "sku": nuevo_producto.sku,
                "codigo_barras": nuevo_producto.codigo_barras,
                "nombre": nuevo_producto.nombre,
                "descripcion": nuevo_producto.descripcion,
                "precio_base": float(nuevo_producto.precio_base) if nuevo_producto.precio_base else 0.0,
                "es_kit": nuevo_producto.es_kit,
                "vida_util_dias": nuevo_producto.vida_util_dias,
                "id_marca": str(nuevo_producto.id_marca) if nuevo_producto.id_marca else None,
                "id_umedida": str(nuevo_producto.id_umedida) if nuevo_producto.id_umedida else None,
                "id_categoria": str(nuevo_producto.id_categoria) if nuevo_producto.id_categoria else None,
                "id_subcategoria": str(nuevo_producto.id_subcategoria) if nuevo_producto.id_subcategoria else None,
                "created_at": nuevo_producto.created_at.isoformat() if nuevo_producto.created_at else None
            }
        }
        
        # Agregar información de variante base si se creó
        if variante_base:
            respuesta["variante_base"] = {
                "id_producto_variante": str(variante_base.id_producto_variante),
                "sku_variante": variante_base.sku_variante,
                "precio": float(variante_base.precio) if variante_base.precio else 0.0,
                "codigo_barras_var": variante_base.codigo_barras_var,
                "peso_gr": float(variante_base.peso_gr) if variante_base.peso_gr else 0.0,
                "vida_util_dias": variante_base.vida_util_dias,
                "created_at": variante_base.created_at.isoformat() if variante_base.created_at else None
            }
            respuesta["message"] += " (con variante base automática)"
            
            # Cambiar el data principal para que sea la variante
            respuesta["data"] = respuesta["variante_base"]
        
        return respuesta
        
    except HTTPException:
        # Re-lanzar excepciones HTTP
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        
        # Manejo específico de errores de constraint
        error_msg = str(e).lower()
        if "unique" in error_msg or "duplicate" in error_msg:
            if "sku" in error_msg:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un producto con el SKU: {entrada.sku}"
                )
            elif "codigo_barras" in error_msg:
                raise HTTPException(
                    status_code=409,
                    detail=f"Ya existe un producto con el código de barras: {entrada.codigo_barras}"
                )
            else:
                raise HTTPException(
                    status_code=409,
                    detail="Error de duplicidad en los datos del producto"
                )
        elif "xxxcat_subcategoria" in error_msg:
            raise HTTPException(
                status_code=400,
                detail="Error de relación entre categoría y subcategoría"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error interno del servidor: {str(e)}"
            )


# ===== ENDPOINT ADICIONAL PARA CREAR PRODUCTO SIN VARIANTE BASE =====

@router.post("/sin_variante_base", response_model=dict, status_code=201)
async def crear_producto_sin_variante_base(
    entrada: ProductoCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un producto SIN variante base automática.
    
    USAR SOLO SI:
    - Vas a crear las variantes manualmente después
    - Es un producto que requiere configuración específica de variantes
    
    ADVERTENCIA: El producto NO será vendible hasta que tenga al menos una variante.
    """
    
    # Llamar al endpoint principal con crear_variante_base=False
    return await crear_producto(entrada, crear_variante_base=False, db=db)


# ===== ENDPOINT PARA AGREGAR VARIANTE BASE A PRODUCTO EXISTENTE =====

@router.post("/{id_producto}/crear_variante_base", response_model=dict)
async def crear_variante_base_para_producto(
    id_producto: UUID,
    precio_override: Optional[float] = Query(None, description="Precio específico para la variante base"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una variante base para un producto existente que no tiene variantes.
    Útil para productos creados antes de implementar variantes obligatorias.
    """
    
    # Verificar que el producto existe
    producto_query = select(Producto).where(Producto.id_producto == id_producto)
    result = await db.execute(producto_query)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar que no tenga variantes ya
    estado_activo_id = await get_estado_id_por_clave("act", db)
    variantes_existentes_query = select(ProductoVariante).where(
        ProductoVariante.id_producto == id_producto,
        ProductoVariante.id_estado == estado_activo_id
    )
    result = await db.execute(variantes_existentes_query)
    variantes_existentes = result.scalars().all()
    
    if variantes_existentes:
        return {
            "success": False,
            "message": f"El producto ya tiene {len(variantes_existentes)} variante(s)",
            "variantes_existentes": [
                {
                    "id_producto_variante": str(v.id_producto_variante),
                    "sku_variante": v.sku_variante
                } for v in variantes_existentes
            ]
        }
    
    try:
        # Crear la variante base
        variante_base = await crear_variante_base_automatica(
            id_producto=id_producto,
            db=db,
            precio_override=precio_override
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": "Variante base creada exitosamente",
            "variante_base": {
                "id_producto_variante": str(variante_base.id_producto_variante),
                "sku_variante": variante_base.sku_variante,
                "precio": float(variante_base.precio) if variante_base.precio else 0.0,
                "codigo_barras_var": variante_base.codigo_barras_var
            }
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creando variante base: {str(e)}"
        )

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




# producto.py - ENDPOINT ACTUALIZADO
# ---------------------------
# Reemplazar el endpoint buscar_producto_por_codigo existente

from utils.variante_base import garantizar_variante_base

@router.get("/buscar_por_codigo/{codigo}", response_model=dict)
async def buscar_producto_por_codigo(
    codigo: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint inteligente para búsqueda de productos por código.
    
    NUEVA LÓGICA (Opción 1 - Variantes Obligatorias):
    1. Busca como variante específica
    2. Si no encuentra, busca como producto base
    3. Si el producto no tiene variantes, crea automáticamente una variante base
    4. SIEMPRE retorna variantes reales (nunca virtuales)
    
    Returns:
        dict: Información del producto/variante encontrado con acción sugerida
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
        # ✅ ENCONTRADO COMO VARIANTE ESPECÍFICA
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
            "descripcion_variante": " | ".join(atributos) if atributos else "Producto Base",
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
        # ✅ ENCONTRADO COMO PRODUCTO BASE
        
        # Construir información del producto
        producto_info = {
            "id_producto": str(producto_row.id_producto),
            "sku": producto_row.sku,
            "codigo_barras": producto_row.codigo_barras,
            "nombre": producto_row.nombre,
            "descripcion": producto_row.descripcion,
            "precio_base": float(producto_row.precio_base) if producto_row.precio_base else 0.0,
            "es_kit": producto_row.es_kit,
            "vida_util_dias": producto_row.vida_util_dias
        }
        
        # =================
        # NUEVA LÓGICA: Garantizar que tenga variantes
        # =================
        try:
            # Esto creará una variante base si no existe
            variante_base = await garantizar_variante_base(producto_row.id_producto, db)
            await db.commit()  # Confirmar la creación de variante base
            
            # Buscar todas las variantes del producto (incluyendo la recién creada)
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
                
                descripcion_variante = " | ".join(atributos) if atributos else "Producto Base"
                
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
            
            # Actualizar total de variantes
            producto_info["total_variantes"] = len(variantes_info)
            
            # Determinar acción sugerida
            if len(variantes_info) == 1:
                accion = "agregar_directo"
                mensaje = f"Producto encontrado: {producto_row.nombre} (variante base creada automáticamente)"
                variante_seleccionada = variantes_info[0]
            else:
                accion = "mostrar_selector"
                mensaje = f"Producto encontrado con {len(variantes_info)} variantes disponibles"
                variante_seleccionada = None
            
            return {
                "success": True,
                "tipo": "producto_base",
                "accion_sugerida": accion,
                "mensaje": mensaje,
                "variante": variante_seleccionada,
                "producto": producto_info,
                "variantes": variantes_info
            }
            
        except Exception as e:
            # Si hay error creando la variante base, rollback
            await db.rollback()
            raise HTTPException(
                status_code=500, 
                detail=f"Error garantizando variante base para producto {producto_row.nombre}: {str(e)}"
            )
    
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


# ===== ENDPOINT ADICIONAL PARA MIGRACIÓN =====

@router.post("/migrar_variantes_base", response_model=dict)
async def migrar_variantes_base_endpoint(
    limite: int = Query(100, ge=1, le=1000, description="Productos a procesar por lote"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Endpoint para ejecutar la migración de productos sin variantes.
    Crea variantes base automáticamente para productos existentes.
    
    USAR CON PRECAUCIÓN: Solo ejecutar una vez en producción.
    """
    
    from utils.variante_base import migrar_productos_sin_variantes
    
    try:
        estadisticas = await migrar_productos_sin_variantes(db, limite)
        
        return {
            "success": True,
            "message": "Migración de variantes base completada",
            "estadisticas": estadisticas
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error durante la migración: {str(e)}"
        )


# ===== ENDPOINT DE VALIDACIÓN =====

@router.get("/validar_integridad_variantes", response_model=dict)
async def validar_integridad_variantes_endpoint(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Valida que todos los productos activos tengan al menos una variante.
    Útil para monitorear la integridad después de la migración.
    """
    
    from utils.variante_base import validar_integridad_variantes
    
    reporte = await validar_integridad_variantes(db)
    
    return {
        "success": True,
        "message": "Validación de integridad completada",
        "reporte": reporte
    }


@router.get("/consecutivo/proximo/{categoria_id}", response_model=dict)
async def obtener_proximo_consecutivo(
    categoria_id: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene el próximo número consecutivo para una categoría específica.
    
    Args:
        categoria_id: UUID de la categoría para la cual obtener el consecutivo
        
    Returns:
        dict: Contiene el próximo número consecutivo disponible
    """
    
    try:
        # Obtener contexto para id_empresa
        ctx = await obtener_contexto(db)
        
        # Ejecutar query para obtener próximo consecutivo
        query = text("""
            WITH siguiente AS (
                SELECT COALESCE(ultimo_numero, 0) + 1 AS proximo
                FROM categoria_consecutivos
                WHERE id_empresa = :id_empresa
                  AND categoria_id = :categoria_id
            )
            SELECT COALESCE((SELECT proximo FROM siguiente), 1) AS proximo_consecutivo;
        """)
        
        result = await db.execute(query, {
            "id_empresa": str(ctx["tenant_id"]),
            "categoria_id": str(categoria_id)
        })
        
        row = result.first()
        
        if not row:
            # Si no hay resultado, comenzar desde 1
            proximo_consecutivo = 1
        else:
            proximo_consecutivo = row.proximo_consecutivo
        
        return {
            "success": True,
            "message": "Próximo consecutivo obtenido exitosamente",
            "data": {
                "categoria_id": str(categoria_id),
                "proximo_consecutivo": proximo_consecutivo,
                "id_empresa": str(ctx["tenant_id"])
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo próximo consecutivo: {str(e)}"
        )