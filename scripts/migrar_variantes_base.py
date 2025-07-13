# ===== SCRIPT DE VERIFICACIÓN ESPECÍFICO PARA caba0056 =====
# Archivo: verificar_caba0056.py

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, text
from db import AsyncSessionLocal
from models import Producto, ProductoVariante
from utils.estado_helpers import get_estado_id_por_clave

async def verificar_estado_caba0056():
    """
    Verifica específicamente el estado del producto caba0056 para diagnosticar el error 500
    """
    
    print("🔍 VERIFICANDO ESTADO DEL CÓDIGO: caba0056")
    print("=" * 50)
    
    async with AsyncSessionLocal() as db:
        try:
            # CONFIGURAR CONTEXTO RLS TEMPORAL
            print("🔐 Configurando contexto de seguridad temporal...")
            
            # Usar UUIDs específicos para tu sistema
            tenant_id_temporal = "d077f79f-7731-4b15-84b3-1a226762c8c7"
            user_id_temporal = "023b3905-435d-40e3-8447-eb1f444ff3fe"
            
            await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id_temporal}'"))
            await db.execute(text(f"SET LOCAL app.usuario = '{user_id_temporal}'"))
            
            estado_activo_id = await get_estado_id_por_clave("act", db)
            print(f"✅ Estado activo ID: {estado_activo_id}")
            
            # 1. BUSCAR EN PRODUCTOS BASE
            print(f"\n1️⃣ Buscando en productos base...")
            productos_query = select(Producto).where(
                and_(
                    Producto.id_estado == estado_activo_id,
                    (Producto.sku.ilike('%caba0056%')) |
                    (Producto.codigo_barras.ilike('%caba0056%'))
                )
            )
            
            result = await db.execute(productos_query)
            productos = result.scalars().all()
            
            if productos:
                print(f"✅ ENCONTRADO {len(productos)} producto(s) base:")
                for producto in productos:
                    print(f"   ID: {producto.id_producto}")
                    print(f"   SKU: {producto.sku}")
                    print(f"   Nombre: {producto.nombre}")
                    print(f"   Precio Base: ${producto.precio_base}")
                    print(f"   Código Barras: {producto.codigo_barras or 'N/A'}")
                    
                    # 2. VERIFICAR VARIANTES DE ESTE PRODUCTO
                    print(f"\n2️⃣ Verificando variantes del producto {producto.sku}...")
                    variantes_query = select(ProductoVariante).where(
                        and_(
                            ProductoVariante.id_producto == producto.id_producto,
                            ProductoVariante.id_estado == estado_activo_id
                        )
                    )
                    
                    var_result = await db.execute(variantes_query)
                    variantes = var_result.scalars().all()
                    
                    if variantes:
                        print(f"✅ TIENE {len(variantes)} variante(s):")
                        for variante in variantes:
                            print(f"   - ID Variante: {variante.id_producto_variante}")
                            print(f"   - SKU Variante: {variante.sku_variante}")
                            print(f"   - Precio: ${variante.precio}")
                            print(f"   - Código Barras Var: {variante.codigo_barras_var or 'N/A'}")
                    else:
                        print("❌ NO TIENE VARIANTES - ¡AQUÍ ESTÁ EL PROBLEMA!")
                        print("💡 Solución: Ejecutar la migración de variantes base")
                        
                    print("   " + "-" * 40)
            else:
                print("❌ NO SE ENCONTRÓ EN PRODUCTOS BASE")
                
            # 3. BUSCAR DIRECTAMENTE EN VARIANTES
            print(f"\n3️⃣ Buscando directamente en variantes...")
            variantes_directas_query = select(ProductoVariante).where(
                and_(
                    ProductoVariante.id_estado == estado_activo_id,
                    (ProductoVariante.sku_variante.ilike('%caba0056%')) |
                    (ProductoVariante.codigo_barras_var.ilike('%caba0056%'))
                )
            )
            
            var_directas_result = await db.execute(variantes_directas_query)
            variantes_directas = var_directas_result.scalars().all()
            
            if variantes_directas:
                print(f"✅ ENCONTRADO {len(variantes_directas)} variante(s) directa(s):")
                for variante in variantes_directas:
                    print(f"   - ID Variante: {variante.id_producto_variante}")
                    print(f"   - SKU Variante: {variante.sku_variante}")
                    print(f"   - ID Producto: {variante.id_producto}")
                    print(f"   - Precio: ${variante.precio}")
            else:
                print("❌ NO SE ENCONTRÓ EN VARIANTES")
                
            # 4. DIAGNÓSTICO Y RECOMENDACIONES
            print(f"\n🎯 DIAGNÓSTICO:")
            if productos and not any(variantes for _ in productos):
                print("❌ PROBLEMA IDENTIFICADO:")
                print("   El producto 'caba0056' existe como producto base")
                print("   pero NO tiene variantes asociadas.")
                print("   Esto causa el error 500 cuando el endpoint intenta")
                print("   crear una variante base automáticamente.")
                print("")
                print("🔧 SOLUCIÓN RECOMENDADA:")
                print("   1. Ejecutar: python migrar_variantes_base.py validar")
                print("   2. Ejecutar: python migrar_variantes_base.py migrar")
                print("   3. Volver a probar la búsqueda en punto de venta")
                
            elif variantes_directas:
                print("✅ El código tiene variantes directas.")
                print("   El error 500 puede ser por otro motivo.")
                print("   Revisar logs del servidor para más detalles.")
                
            elif not productos and not variantes_directas:
                print("❌ El código 'caba0056' NO EXISTE en el sistema.")
                print("   Verificar que el código sea correcto.")
                
            else:
                print("✅ El producto y sus variantes parecen estar bien.")
                print("   El error 500 puede ser por otro motivo.")
                
        except Exception as e:
            print(f"❌ ERROR durante la verificación: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(verificar_estado_caba0056())
    except KeyboardInterrupt:
        print("\n❌ Verificación cancelada por el usuario.")
    except Exception as e:
        print(f"\n💥 Error inesperado: {str(e)}")
        sys.exit(1)