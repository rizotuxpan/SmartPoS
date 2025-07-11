# producto_variante.py
# ---------------------------
# Módulo de endpoints REST para gestión de Variantes de Productos.
# Incluye filtros avanzados y opción de expandir objetos relacionados.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel, model_validator                 # Pydantic para schemas de entrada/salida
from typing import Optional                                     # Tipos para anotaciones
from uuid import UUID                                           # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from decimal import Decimal                                     # Para campos numéricos de alta precisión
from sqlalchemy import (
    Column, String, Numeric, Integer, DateTime, func, select, text, 
    delete, and_, or_, cast, join
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto

# ===== IMPORTAR MODELOS Y ESQUEMAS RELACIONADOS =====
from producto import Producto, ProductoRead

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class ProductoVariante(Base):
    __tablename__ = "producto_variante"
    
    id_producto_variante = Column(
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
    id_producto = Column(PG_UUID(as_uuid=True), nullable=False)
    id_talla = Column(PG_UUID(as_uuid=True))
    id_color = Column(PG_UUID(as_uuid=True))
    id_tamano = Column(PG_UUID(as_uuid=True))
    sku_variante = Column(String(50), nullable=False)
    codigo_barras_var = Column(CITEXT)
    precio = Column(Numeric(14,2), default=0)
    peso_gr = Column(Numeric(10,2), default=0)
    vida_util_dias = Column(Integer)
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
class ProductoVarianteBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Variante de 
Producto.
    """
    id_producto: UUID
    id_talla: Optional[UUID] = None
    id_color: Optional[UUID] = None
    id_tamano: Optional[UUID] = None
    sku_variante: str
    codigo_barras_var: Optional[str] = None
    precio: Optional[Decimal] = 0
    peso_gr: Optional[Decimal] = 0
    vida_util_dias: Optional[int] = None

class ProductoVarianteCreate(ProductoVarianteBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ProductoVarianteUpdate(BaseModel):
    """
    Esquema para actualización; todos los campos son opcionales.
    """
    id_producto: Optional[UUID] = None
    id_talla: Optional[UUID] = None
    id_color: Optional[UUID] = None
    id_tamano: Optional[UUID] = None
    sku_variante: Optional[str] = None
    codigo_barras_var: Optional[str] = None
    precio: Optional[Decimal] = None
    peso_gr: Optional[Decimal] = None
    vida_util_dias: Optional[int] = None

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

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ===== ESQUEMA EXPANDIDO =====
class ProductoVarianteReadExpanded(ProductoVarianteBase):
    """
    Esquema de lectura expandido con objeto producto relacionado completo.
    """
    id_producto_variante: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    # Objeto producto relacionado completo
    producto: Optional[ProductoRead] = None
    
    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_variantes(
    # ===== FILTROS BÁSICOS =====
    id_producto: Optional[UUID] = Query(None, description="Filtro por producto padre"),
    sku_variante: Optional[str] = Query(None, description="Filtro por SKU de variante"),
    codigo_barras_var: Optional[str] = Query(None, description="Filtro por código de barras de variante"),
    
    # ===== FILTROS DE PRECIO =====
    precio: Optional[float] = Query(None, description="Precio exacto"),
    precio_min: Optional[float] = Query(None, description="Precio mínimo (>=)"),
    precio_max: Optional[float] = Query(None, description="Precio máximo (<=)"),
    precio_mayor: Optional[float] = Query(None, description="Precio mayor que (>)"),
    precio_menor: Optional[float] = Query(None, description="Precio menor que (<)"),
    
    # ===== FILTROS POR ATRIBUTOS DE VARIANTE =====
    id_talla: Optional[UUID] = Query(None, description="Filtro por talla"),
    id_color: Optional[UUID] = Query(None, description="Filtro por color"),
    id_tamano: Optional[UUID] = Query(None, description="Filtro por tamaño"),
    
    # ===== FILTROS POR PRODUCTO PADRE =====
    producto_nombre: Optional[str] = Query(None, description="Filtro por nombre del producto padre"),
    producto_sku: Optional[str] = Query(None, description="Filtro por SKU del producto padre"),
    
    # ===== PARÁMETROS DE CONFIGURACIÓN =====
    expandir: bool = Query(False, description="Incluir objeto producto relacionado completo"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista variantes de productos en estado "activo" con paginación, filtros opcionales extendidos
    y opción de expandir objeto producto relacionado.
    """
    # 1) Obtener UUID del estado "activo" desde caché/contexto
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta base
    if expandir:
        # Si expandir=True, hacer join con producto
        query = select(ProductoVariante).join(Producto).where(
            and_(
                ProductoVariante.id_estado == estado_activo_id,
                ProductoVariante.id_producto == Producto.id_producto,
                Producto.id_estado == estado_activo_id
            )
        )
    else:
        # Si expandir=False, consulta simple
        query = select(ProductoVariante).where(ProductoVariante.id_estado == estado_activo_id)

    # 3) Aplicar filtros básicos
    if id_producto:
        query = query.where(ProductoVariante.id_producto == id_producto)
    if sku_variante:
        query = query.where(ProductoVariante.sku_variante.ilike(f"%{sku_variante}%"))
    if codigo_barras_var:
        query = query.where(ProductoVariante.codigo_barras_var.ilike(f"%{codigo_barras_var}%"))

    # 4) Aplicar filtros de precio
    if precio is not None:
        query = query.where(ProductoVariante.precio == precio)
    if precio_min is not None:
        query = query.where(ProductoVariante.precio >= precio_min)
    if precio_max is not None:
        query = query.where(ProductoVariante.precio <= precio_max)
    if precio_mayor is not None:
        query = query.where(ProductoVariante.precio > precio_mayor)
    if precio_menor is not None:
        query = query.where(ProductoVariante.precio < precio_menor)

    # 5) Aplicar filtros por atributos de variante
    if id_talla:
        query = query.where(ProductoVariante.id_talla == id_talla)
    if id_color:
        query = query.where(ProductoVariante.id_color == id_color)
    if id_tamano:
        query = query.where(ProductoVariante.id_tamano == id_tamano)

    # 6) Aplicar filtros por producto padre (requiere join si no está ya hecho)
    if producto_nombre or producto_sku:
        if not expandir:
            # Si no estamos expandiendo, necesitamos hacer join para filtrar
            query = query.join(Producto).where(
                and_(
                    ProductoVariante.id_producto == Producto.id_producto,
                    Producto.id_estado == estado_activo_id
                )
            )
        
        if producto_nombre:
            query = query.where(Producto.nombre.ilike(f"%{producto_nombre}%"))
        if producto_sku:
            query = query.where(Producto.sku.ilike(f"%{producto_sku}%"))

    # 7) Ordenar por fecha de creación descendente
    query = query.order_by(ProductoVariante.created_at.desc())

    # 8) Contar total de registros (replicando la misma lógica sin offset/limit)
    count_query = select(func.count(ProductoVariante.id_producto_variante)).where(
        ProductoVariante.id_estado == estado_activo_id
    )
    
    # Aplicar mismos filtros al count_query
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
    if precio_mayor is not None:
        count_query = count_query.where(ProductoVariante.precio > precio_mayor)
    if precio_menor is not None:
        count_query = count_query.where(ProductoVariante.precio < precio_menor)
    if id_talla:
        count_query = count_query.where(ProductoVariante.id_talla == id_talla)
    if id_color:
        count_query = count_query.where(ProductoVariante.id_color == id_color)
    if id_tamano:
        count_query = count_query.where(ProductoVariante.id_tamano == id_tamano)
    
    if producto_nombre or producto_sku:
        count_query = count_query.join(Producto).where(
            and_(
                ProductoVariante.id_producto == Producto.id_producto,
                Producto.id_estado == estado_activo_id
            )
        )
        if producto_nombre:
            count_query = count_query.where(Producto.nombre.ilike(f"%{producto_nombre}%"))
        if producto_sku:
            count_query = count_query.where(Producto.sku.ilike(f"%{producto_sku}%"))

    # 9) Ejecutar count
    total = await db.scalar(count_query)

    # 10) Ejecutar consulta principal con paginación
    result = await db.execute(query.offset(skip).limit(limit))
    variantes = result.scalars().all()

    # 11) Si expandir=True, cargar objetos producto relacionados
    if expandir and variantes:
        # Obtener IDs de productos para una consulta batch
        producto_ids = list(set(v.id_producto for v in variantes))
        
        # Cargar productos en batch
        productos_query = select(Producto).where(
            and_(
                Producto.id_producto.in_(producto_ids),
                Producto.id_estado == estado_activo_id
            )
        )
        productos_result = await db.execute(productos_query)
        productos = {p.id_producto: p for p in productos_result.scalars().all()}
        
        # Crear respuesta expandida
        variantes_expandidas = []
        for variante in variantes:
            variante_dict = ProductoVarianteRead.model_validate(variante).model_dump()
            variante_dict['producto'] = ProductoRead.model_validate(productos[variante.id_producto]).model_dump() if variante.id_producto in productos else None
            variantes_expandidas.append(variante_dict)
        
        return {
            "success": True,
            "total_count": total,
            "expandido": True,
            "data": variantes_expandidas
        }
    else:
        # 12) Respuesta estándar sin expandir
        return {
            "success": True,
            "total_count": total,
            "expandido": False,
            "data": [ProductoVarianteRead.model_validate(v) for v in variantes]
        }

@router.get("/combo", response_model=dict)
async def listar_variantes_combo(
    id_producto: Optional[UUID] = Query(None, description="Filtro por 
producto padre"),
    db: AsyncSession = Depends(get_async_db)
):
    """Endpoint optimizado para llenar ComboBox de variantes de productos"""
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    query = select(
        ProductoVariante.id_producto_variante, 
        ProductoVariante.sku_variante,
        ProductoVariante.precio
    ).where(ProductoVariante.id_estado == estado_activo_id)
    
    if id_producto:
        query = query.where(ProductoVariante.id_producto == id_producto)
    
    query = query.order_by(ProductoVariante.sku_variante)
    
    result = await db.execute(query)
    variantes = [
        {
            "id": str(row[0]), 
            "sku_variante": row[1],
            "precio": float(row[2]) if row[2] else 0.0,
            "display": f"{row[1]} - ${row[2] or 0:.2f}"
        } 
        for row in result
    ]
    
    return {"success": True, "data": variantes}

@router.get("/producto/{id_producto}", response_model=dict)
async def listar_variantes_por_producto(
    id_producto: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista todas las variantes de un producto específico.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Verificar que el producto existe y está activo
    producto_query = select(Producto).where(
        Producto.id_producto == id_producto,
        Producto.id_estado == estado_activo_id
    )
    producto_result = await db.execute(producto_query)
    producto = producto_result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Obtener variantes del producto
    stmt = select(ProductoVariante).where(
        ProductoVariante.id_producto == id_producto,
        ProductoVariante.id_estado == estado_activo_id
    ).order_by(ProductoVariante.sku_variante)
    
    # Contar total
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)
    
    # Ejecutar con paginación
    result = await db.execute(stmt.offset(skip).limit(limit))
    variantes = result.scalars().all()
    
    return {
        "success": True,
        "total_count": total,
        "producto": ProductoRead.model_validate(producto).model_dump(),
        "data": [ProductoVarianteRead.model_validate(v) for v in variantes]
    }

@router.get("/{id_producto_variante}", 
response_model=ProductoVarianteRead)
async def obtener_variante(
    id_producto_variante: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una variante de producto por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(ProductoVariante).where(
        ProductoVariante.id_producto_variante == id_producto_variante,
        ProductoVariante.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    variante = result.scalar_one_or_none()

    if not variante:
        raise HTTPException(status_code=404, detail="Variante de producto no encontrada")

    return ProductoVarianteRead.model_validate(variante)

@router.post("/", response_model=dict, status_code=201)
async def crear_variante(
    entrada: ProductoVarianteCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva variante de producto. Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)
    
    # 2) Verificar que el producto padre existe y está activo
    estado_activo_id = await get_estado_id_por_clave("act", db)
    producto_query = select(Producto).where(
        Producto.id_producto == entrada.id_producto,
        Producto.id_estado == estado_activo_id
    )
    producto_result = await db.execute(producto_query)
    producto = producto_result.scalar_one_or_none()
    
    if not producto:
        raise HTTPException(status_code=400, detail="Producto padre no encontrado o inactivo")

    # 3) Construir instancia ORM
    nueva = ProductoVariante(
        id_producto=entrada.id_producto,
        id_talla=entrada.id_talla,
        id_color=entrada.id_color,
        id_tamano=entrada.id_tamano,
        sku_variante=entrada.sku_variante,
        codigo_barras_var=entrada.codigo_barras_var,
        precio=entrada.precio or 0,
        peso_gr=entrada.peso_gr or 0,
        vida_util_dias=entrada.vida_util_dias,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"]
    )
    db.add(nueva)

    # 4) Ejecutar INSERT y refrescar antes de commit para respetar RLS
    await db.flush()        # Realiza INSERT RETURNING …
    await db.refresh(nueva) # Ejecuta SELECT dentro de la misma tx

    # 5) Finalizar tx
    await db.commit()

    # 6) Devolver datos completos
    return {"success": True, "data": 
ProductoVarianteRead.model_validate(nueva)}

@router.put("/{id_producto_variante}", response_model=dict)
async def actualizar_variante(
    id_producto_variante: UUID,
    entrada: ProductoVarianteUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de una variante de producto en estado "activo".
    Solo actualiza los campos que se proporcionen en el request.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Buscar la variante existente
    stmt = select(ProductoVariante).where(
        ProductoVariante.id_producto_variante == id_producto_variante,
        ProductoVariante.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    variante = result.scalar_one_or_none()
    if not variante:
        raise HTTPException(status_code=404, detail="Variante de producto no encontrada")

    # 3) Obtener contexto del usuario
    ctx = await obtener_contexto(db)

    # 4) Si se cambia el producto padre, verificar que existe
    if entrada.id_producto is not None and entrada.id_producto != variante.id_producto:
        producto_query = select(Producto).where(
            Producto.id_producto == entrada.id_producto,
            Producto.id_estado == estado_activo_id
        )
        producto_result = await db.execute(producto_query)
        producto = producto_result.scalar_one_or_none()
        
        if not producto:
            raise HTTPException(status_code=400, detail="Producto padre no encontrado o inactivo")

    # 5) Actualizar solo los campos proporcionados
    if entrada.id_producto is not None:
        variante.id_producto = entrada.id_producto
    if entrada.id_talla is not None:
        variante.id_talla = entrada.id_talla
    if entrada.id_color is not None:
        variante.id_color = entrada.id_color
    if entrada.id_tamano is not None:
        variante.id_tamano = entrada.id_tamano
    if entrada.sku_variante is not None:
        variante.sku_variante = entrada.sku_variante
    if entrada.codigo_barras_var is not None:
        variante.codigo_barras_var = entrada.codigo_barras_var
    if entrada.precio is not None:
        variante.precio = entrada.precio
    if entrada.peso_gr is not None:
        variante.peso_gr = entrada.peso_gr
    if entrada.vida_util_dias is not None:
        variante.vida_util_dias = entrada.vida_util_dias
    
    # Actualizar metadatos de auditoría
    variante.modified_by = ctx["user_id"]

    # 6) Guardar cambios
    await db.flush()
    await db.refresh(variante)
    await db.commit()

    return {"success": True, "data": 
ProductoVarianteRead.model_validate(variante)}

@router.delete("/{id_producto_variante}", status_code=200)
async def eliminar_variante(
    id_producto_variante: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una variante de producto. Se respetan políticas RLS.
    """
    # Verificar que la variante existe
    result = await db.execute(
        
select(ProductoVariante).where(ProductoVariante.id_producto_variante == 
id_producto_variante)
    )
    variante = result.scalar_one_or_none()
    if not variante:
        raise HTTPException(status_code=404, detail="Variante de producto no encontrada")

    # Eliminar físicamente
    await db.execute(
        
delete(ProductoVariante).where(ProductoVariante.id_producto_variante == id_producto_variante)
    )
    await db.commit()

    return {"success": True, "message": "Variante de producto eliminada permanentemente"}
