# utils/variante_base.py
# ---------------------------
# Utilidades para manejo de variantes base automáticas
# Garantiza que todo producto tenga al menos una variante

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import Optional

# Importar modelos (ajusta según tu estructura)
from producto import Producto
from producto_variante import ProductoVariante
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto


async def crear_variante_base_automatica(
    id_producto: UUID, 
    db: AsyncSession,
    precio_override: Optional[float] = None
) -> ProductoVariante:
    """
    Crea una variante base automática para un producto que no tiene variantes.
    
    Args:
        id_producto: UUID del producto padre
        db: Sesión de base de datos
        precio_override: Precio específico para la variante (opcional)
    
    Returns:
        ProductoVariante: La variante base creada
    """
    
    # Obtener información del producto
    producto_query = select(Producto).where(Producto.id_producto == id_producto)
    result = await db.execute(producto_query)
    producto = result.scalar_one_or_none()
    
    if not producto:
        raise ValueError(f"Producto con ID {id_producto} no encontrado")
    
    # Obtener contexto y estado activo
    ctx = await obtener_contexto(db)
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Determinar SKU de variante base
    sku_base = producto.sku or producto.nombre[:20].upper().replace(" ", "_")
    sku_variante = f"{sku_base}-BASE"
    #sku_variante = f"{sku_base}-BASE"   Probar quitar BASE
    
    # Verificar que el SKU no exista
    contador = 1
    sku_final = sku_variante
    while await _sku_variante_existe(sku_final, db):
        sku_final = f"{sku_variante}_{contador}"
        contador += 1
    
    # Determinar precio
    precio_final = precio_override or producto.precio_base or 0.0
    
    # Crear la variante base
    variante_base = ProductoVariante(
        id_producto=id_producto,
        sku_variante=sku_final,
        codigo_barras_var=producto.codigo_barras,  # Puede ser None
        precio=precio_final,
        peso_gr=0.0,
        vida_util_dias=producto.vida_util_dias,
        
        # Atributos de variante = NULL (sin talla, color, tamaño)
        id_talla=None,
        id_color=None,
        id_tamano=None,
        
        # Campos de auditoría
        id_empresa=ctx["tenant_id"],  # ← Campo obligatorio que faltaba
        id_estado=estado_activo_id,
        created_by=ctx["user_id"],
        modified_by=ctx["user_id"]
    )
    
    db.add(variante_base)
    await db.flush()
    await db.refresh(variante_base)
    
    return variante_base


async def _sku_variante_existe(sku: str, db: AsyncSession) -> bool:
    """Verifica si un SKU de variante ya existe"""
    query = select(ProductoVariante).where(ProductoVariante.sku_variante == sku)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


async def garantizar_variante_base(id_producto: UUID, db: AsyncSession) -> ProductoVariante:
    """
    Garantiza que un producto tenga al menos una variante.
    Si no tiene variantes, crea una variante base automáticamente.
    
    Returns:
        ProductoVariante: La variante existente o la recién creada
    """
    
    # Buscar variantes existentes
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    variantes_query = select(ProductoVariante).where(
        ProductoVariante.id_producto == id_producto,
        ProductoVariante.id_estado == estado_activo_id
    )
    result = await db.execute(variantes_query)
    variantes = result.scalars().all()
    
    if variantes:
        # Ya tiene variantes, retornar la primera
        return variantes[0]
    else:
        # No tiene variantes, crear una base
        return await crear_variante_base_automatica(id_producto, db)


async def migrar_productos_sin_variantes(db: AsyncSession, limite: int = 100) -> dict:
    """
    Migra productos existentes que no tienen variantes, creando variantes base.
    
    Args:
        db: Sesión de base de datos
        limite: Número máximo de productos a procesar en una ejecución
    
    Returns:
        dict: Estadísticas de la migración
    """
    
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Encontrar productos sin variantes usando subconsulta
    productos_sin_variantes_query = text("""
        SELECT p.id_producto, p.sku, p.nombre, p.precio_base
        FROM producto p
        WHERE p.id_estado = :estado_activo_id
        AND NOT EXISTS (
            SELECT 1 
            FROM producto_variante pv 
            WHERE pv.id_producto = p.id_producto 
            AND pv.id_estado = :estado_activo_id
        )
        ORDER BY p.created_at
        LIMIT :limite
    """)
    
    result = await db.execute(productos_sin_variantes_query, {
        "estado_activo_id": estado_activo_id,
        "limite": limite
    })
    productos_sin_variantes = result.fetchall()
    
    estadisticas = {
        "productos_encontrados": len(productos_sin_variantes),
        "variantes_creadas": 0,
        "errores": []
    }
    
    for producto_row in productos_sin_variantes:
        try:
            # Crear variante base para este producto
            variante_base = await crear_variante_base_automatica(
                id_producto=producto_row.id_producto,
                db=db,
                precio_override=float(producto_row.precio_base) if producto_row.precio_base else None
            )
            
            estadisticas["variantes_creadas"] += 1
            
            print(f"✅ Variante base creada para '{producto_row.nombre}': {variante_base.sku_variante}")
            
        except Exception as e:
            error_msg = f"Error en producto {producto_row.sku}: {str(e)}"
            estadisticas["errores"].append(error_msg)
            print(f"❌ {error_msg}")
    
    # Confirmar transacción solo si no hubo errores críticos
    if estadisticas["variantes_creadas"] > 0:
        await db.commit()
        print(f"\n🎉 Migración completada: {estadisticas['variantes_creadas']} variantes base creadas")
    
    return estadisticas


# ===== FUNCIONES AUXILIARES DE VALIDACIÓN =====

async def validar_integridad_variantes(db: AsyncSession) -> dict:
    """
    Valida que todos los productos activos tengan al menos una variante activa.
    
    Returns:
        dict: Reporte de integridad
    """
    
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Contar productos activos
    total_productos_query = select(Producto).where(Producto.id_estado == estado_activo_id)
    result = await db.execute(total_productos_query)
    total_productos = len(result.scalars().all())
    
    # Contar productos con variantes
    productos_con_variantes_query = text("""
        SELECT COUNT(DISTINCT p.id_producto) as count
        FROM producto p
        INNER JOIN producto_variante pv ON p.id_producto = pv.id_producto
        WHERE p.id_estado = :estado_activo_id
        AND pv.id_estado = :estado_activo_id
    """)
    
    result = await db.execute(productos_con_variantes_query, {
        "estado_activo_id": estado_activo_id
    })
    productos_con_variantes = result.scalar()
    
    productos_sin_variantes = total_productos - productos_con_variantes
    
    return {
        "total_productos": total_productos,
        "productos_con_variantes": productos_con_variantes,
        "productos_sin_variantes": productos_sin_variantes,
        "integridad_ok": productos_sin_variantes == 0,
        "porcentaje_completitud": (productos_con_variantes / total_productos * 100) if total_productos > 0 else 0
    }