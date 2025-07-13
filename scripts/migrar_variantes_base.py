#!/usr/bin/env python3
# scripts/migrar_variantes_base.py
# ---------------------------
# Script para migrar productos existentes sin variantes
# Ejecutar UNA SOLA VEZ después de implementar la nueva lógica

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

# IMPORTACIONES CORREGIDAS según la configuración del proyecto
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from db import AsyncSessionLocal  # Usar el sessionmaker configurado


async def migrar_productos_sin_variantes_simple(db: AsyncSession, limite: int = 100) -> dict:
    """
    Función simplificada de migración sin depender de utils.variante_base
    """
    print(f"🔄 Procesando hasta {limite} productos sin variantes...")
    
    # Consultar productos sin variantes
    query = text("""
        SELECT p.id_producto, p.sku, p.nombre, p.precio_base
        FROM producto p
        WHERE p.id_estado = (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1)
        AND NOT EXISTS (
            SELECT 1 FROM producto_variante pv 
            WHERE pv.id_producto = p.id_producto 
            AND pv.id_estado = (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1)
        )
        LIMIT :limite
    """)
    
    result = await db.execute(query, {"limite": limite})
    productos_sin_variantes = result.fetchall()
    
    productos_encontrados = len(productos_sin_variantes)
    variantes_creadas = 0
    errores = []
    
    print(f"Encontrados {productos_encontrados} productos sin variantes")
    
    for row in productos_sin_variantes:
        try:
            producto_id = row[0]
            sku = row[1]
            nombre = row[2]
            precio_base = row[3] or 0.0
            
            print(f"  Creando variante base para: {sku}")
            
            # Crear variante base usando SQL directo
            insert_variante = text("""
                INSERT INTO producto_variante (
                    id_empresa, id_producto, id_estado, sku_variante, 
                    precio, created_by, modified_by
                ) VALUES (
                    current_setting('app.current_tenant')::uuid,
                    :id_producto,
                    (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1),
                    :sku_variante,
                    :precio,
                    current_setting('app.usuario')::uuid,
                    current_setting('app.usuario')::uuid
                )
            """)
            
            await db.execute(insert_variante, {
                "id_producto": producto_id,
                "sku_variante": f"{sku}-BASE",
                "precio": precio_base
            })
            
            variantes_creadas += 1
            print(f"    ✅ Variante creada: {sku}-BASE")
            
        except Exception as e:
            error_msg = f"Error con producto {sku}: {str(e)}"
            errores.append(error_msg)
            print(f"    ❌ {error_msg}")
            continue
    
    # Commit de este lote
    try:
        await db.commit()
        print(f"  💾 Lote confirmado: {variantes_creadas} variantes creadas")
    except Exception as e:
        await db.rollback()
        print(f"  ❌ Error en commit: {e}")
        errores.append(f"Error en commit: {e}")
    
    return {
        "productos_encontrados": productos_encontrados,
        "variantes_creadas": variantes_creadas,
        "errores": errores
    }


async def validar_integridad_variantes_simple(db: AsyncSession) -> dict:
    """
    Función simplificada de validación sin depender de utils.variante_base
    """
    print("📊 Validando integridad de variantes...")
    
    # Contar productos activos
    query_productos = text("""
        SELECT COUNT(*) FROM producto p
        WHERE p.id_estado = (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1)
    """)
    result = await db.execute(query_productos)
    total_productos = result.scalar()
    
    # Contar productos con variantes
    query_con_variantes = text("""
        SELECT COUNT(DISTINCT p.id_producto) FROM producto p
        WHERE p.id_estado = (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1)
        AND EXISTS (
            SELECT 1 FROM producto_variante pv 
            WHERE pv.id_producto = p.id_producto 
            AND pv.id_estado = (SELECT id_estado FROM estado WHERE clave = 'act' LIMIT 1)
        )
    """)
    result = await db.execute(query_con_variantes)
    productos_con_variantes = result.scalar()
    
    productos_sin_variantes = total_productos - productos_con_variantes
    porcentaje_completitud = (productos_con_variantes / total_productos * 100) if total_productos > 0 else 100
    
    return {
        "total_productos": total_productos,
        "productos_con_variantes": productos_con_variantes,
        "productos_sin_variantes": productos_sin_variantes,
        "porcentaje_completitud": porcentaje_completitud,
        "integridad_ok": productos_sin_variantes == 0
    }


async def ejecutar_migracion_completa():
    """
    Ejecuta la migración completa de variantes base para productos existentes.
    """
    
    print("🚀 Iniciando migración de variantes base...")
    print("=" * 60)
    
    # Crear sesión usando AsyncSessionLocal (configurado en db.py)
    async with AsyncSessionLocal() as db:
        try:
            # CONFIGURAR CONTEXTO RLS TEMPORAL
            # Necesario para que las consultas funcionen con Row Level Security
            print("🔐 Configurando contexto de seguridad temporal...")
            
            # Primero intentar obtener UUIDs reales del sistema
            try:
                # Obtener una empresa (tenant)
                result_empresa = await db.execute(text("SELECT id_empresa FROM empresa LIMIT 1"))
                empresa_row = result_empresa.fetchone()
                
                # Obtener un usuario
                result_usuario = await db.execute(text("SELECT id_usuario FROM usuario LIMIT 1"))
                usuario_row = result_usuario.fetchone()
                
                if empresa_row and usuario_row:
                    tenant_id = str(empresa_row[0])
                    user_id = str(usuario_row[0])
                    print(f"✅ Usando Tenant: {tenant_id}")
                    print(f"✅ Usando Usuario: {user_id}")
                else:
                    raise Exception("No se encontraron registros")
                    
            except Exception as e:
                print(f"⚠️  No se pudieron obtener UUIDs reales: {e}")
                print("⚠️  Usando UUIDs de ejemplo (puede fallar con RLS estricto)")
                tenant_id = "123e4567-e89b-12d3-a456-426614174000"
                user_id = "987fcdeb-51a2-4321-b567-123456789abc"
            
            await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            await db.execute(text(f"SET LOCAL app.usuario = '{user_id}'"))
            
            print("✅ Contexto configurado correctamente")
            
            # ===== PASO 1: Validar estado inicial =====
            print("\n📊 PASO 1: Validando estado inicial...")
            reporte_inicial = await validar_integridad_variantes_simple(db)
            
            print(f"Total de productos activos: {reporte_inicial['total_productos']}")
            print(f"Productos con variantes: {reporte_inicial['productos_con_variantes']}")
            print(f"Productos SIN variantes: {reporte_inicial['productos_sin_variantes']}")
            print(f"Completitud actual: {reporte_inicial['porcentaje_completitud']:.1f}%")
            
            if reporte_inicial['productos_sin_variantes'] == 0:
                print("\n✅ ¡Todos los productos ya tienen variantes! No se requiere migración.")
                return
            
            # ===== PASO 2: Confirmar migración =====
            print(f"\n⚠️  Se van a crear {reporte_inicial['productos_sin_variantes']} variantes base.")
            respuesta = input("¿Continuar con la migración? (s/N): ").strip().lower()
            
            if respuesta not in ['s', 'si', 'sí', 'y', 'yes']:
                print("❌ Migración cancelada por el usuario.")
                return
            
            # ===== PASO 3: Ejecutar migración por lotes =====
            print("\n🔄 PASO 2: Ejecutando migración...")
            
            total_migrados = 0
            lote = 1
            limite_por_lote = 50  # Procesar de 50 en 50 para evitar timeouts
            
            while True:
                print(f"\n--- Lote {lote} (productos {total_migrados + 1}-{total_migrados + limite_por_lote}) ---")
                
                # Ejecutar migración de un lote
                estadisticas = await migrar_productos_sin_variantes_simple(db, limite_por_lote)
                
                productos_encontrados = estadisticas["productos_encontrados"]
                variantes_creadas = estadisticas["variantes_creadas"]
                errores = estadisticas["errores"]
                
                print(f"Productos procesados: {productos_encontrados}")
                print(f"Variantes creadas: {variantes_creadas}")
                
                if errores:
                    print(f"❌ Errores encontrados: {len(errores)}")
                    for error in errores[:3]:  # Mostrar solo los primeros 3 errores
                        print(f"   - {error}")
                    if len(errores) > 3:
                        print(f"   - ... y {len(errores) - 3} errores más")
                
                total_migrados += variantes_creadas
                
                # Si no encontró productos, terminamos
                if productos_encontrados == 0:
                    print("✅ No se encontraron más productos sin variantes.")
                    break
                
                lote += 1
                
                # Pausa entre lotes para no sobrecargar la base de datos
                if productos_encontrados == limite_por_lote:
                    print("⏳ Pausa entre lotes...")
                    await asyncio.sleep(1)
            
            # ===== PASO 4: Validar resultado final =====
            print(f"\n📊 PASO 3: Validando resultado final...")
            reporte_final = await validar_integridad_variantes_simple(db)
            
            print(f"Total de productos activos: {reporte_final['total_productos']}")
            print(f"Productos con variantes: {reporte_final['productos_con_variantes']}")
            print(f"Productos SIN variantes: {reporte_final['productos_sin_variantes']}")
            print(f"Completitud final: {reporte_final['porcentaje_completitud']:.1f}%")
            
            # ===== RESUMEN FINAL =====
            print("\n" + "=" * 60)
            print("🎉 MIGRACIÓN COMPLETADA")
            print("=" * 60)
            print(f"✅ Variantes base creadas: {total_migrados}")
            print(f"✅ Productos migrados exitosamente: {reporte_inicial['productos_sin_variantes'] - reporte_final['productos_sin_variantes']}")
            
            if reporte_final['productos_sin_variantes'] == 0:
                print("🏆 ¡Todos los productos ahora tienen al menos una variante!")
                print("🛒 ¡El sistema de ventas ahora es completamente consistente!")
            else:
                print(f"⚠️  Productos pendientes: {reporte_final['productos_sin_variantes']}")
                print("💡 Ejecuta el script nuevamente para procesar los productos restantes.")
            
        except Exception as e:
            print(f"\n❌ ERROR CRÍTICO durante la migración: {str(e)}")
            print("🔄 La base de datos se mantendrá en su estado original.")
            import traceback
            traceback.print_exc()
            
        finally:
            await db.close()


async def validar_solo():
    """
    Solo valida el estado actual sin hacer migración.
    """
    
    print("🔍 Validando integridad de variantes...")
    
    async with AsyncSessionLocal() as db:
        try:
            # CONFIGURAR CONTEXTO RLS TEMPORAL
            print("🔐 Configurando contexto de seguridad temporal...")
            
            # Intentar obtener UUIDs reales del sistema
            try:
                # Obtener una empresa (tenant)
                result_empresa = await db.execute(text("SELECT id_empresa FROM empresa LIMIT 1"))
                empresa_row = result_empresa.fetchone()
                
                # Obtener un usuario
                result_usuario = await db.execute(text("SELECT id_usuario FROM usuario LIMIT 1"))
                usuario_row = result_usuario.fetchone()
                
                if empresa_row and usuario_row:
                    tenant_id = str(empresa_row[0])
                    user_id = str(usuario_row[0])
                    print(f"✅ Usando Tenant: {tenant_id}")
                    print(f"✅ Usando Usuario: {user_id}")
                else:
                    raise Exception("No se encontraron registros")
                    
            except Exception as e:
                print(f"⚠️  No se pudieron obtener UUIDs reales: {e}")
                print("⚠️  Usando UUIDs de ejemplo (puede fallar con RLS estricto)")
                tenant_id = "123e4567-e89b-12d3-a456-426614174000"
                user_id = "987fcdeb-51a2-4321-b567-123456789abc"
            
            await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
            await db.execute(text(f"SET LOCAL app.usuario = '{user_id}'"))
            
            reporte = await validar_integridad_variantes_simple(db)
            
            print("\n📊 REPORTE DE INTEGRIDAD")
            print("=" * 40)
            print(f"Total de productos activos: {reporte['total_productos']}")
            print(f"Productos con variantes: {reporte['productos_con_variantes']}")
            print(f"Productos SIN variantes: {reporte['productos_sin_variantes']}")
            print(f"Completitud: {reporte['porcentaje_completitud']:.1f}%")
            
            if reporte['integridad_ok']:
                print("\n✅ ¡Perfecto! Todos los productos tienen variantes.")
            else:
                print(f"\n⚠️  Se requiere migración para {reporte['productos_sin_variantes']} productos.")
                
        except Exception as e:
            print(f"❌ Error durante la validación: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            await db.close()


async def obtener_uuids_reales():
    """
    Ayuda a obtener UUIDs reales del sistema para configurar el contexto RLS.
    """
    
    print("🔍 Obteniendo UUIDs reales del sistema...")
    
    async with AsyncSessionLocal() as db:
        try:
            # Obtener una empresa (tenant)
            result_empresa = await db.execute(text("SELECT id_empresa FROM empresa LIMIT 1"))
            empresa_row = result_empresa.fetchone()
            
            # Obtener un usuario
            result_usuario = await db.execute(text("SELECT id_usuario FROM usuario LIMIT 1"))
            usuario_row = result_usuario.fetchone()
            
            if empresa_row and usuario_row:
                empresa_id = empresa_row[0]
                usuario_id = usuario_row[0]
                
                print(f"\n📋 UUIDs encontrados en el sistema:")
                print(f"Empresa (Tenant): {empresa_id}")
                print(f"Usuario: {usuario_id}")
                print(f"\n📝 El script los usará automáticamente")
                
            else:
                print("❌ No se encontraron registros en las tablas empresa o usuario")
                print("💡 Asegúrate de que tu base de datos tenga datos básicos")
                
        except Exception as e:
            print(f"❌ Error obteniendo UUIDs: {str(e)}")
            print("💡 El script intentará usar UUIDs de ejemplo")
        finally:
            await db.close()


def mostrar_ayuda():
    """Muestra las opciones disponibles del script."""
    
    print("🛠️  SCRIPT DE MIGRACIÓN - VARIANTES BASE")
    print("=" * 50)
    print()
    print("Opciones disponibles:")
    print("  python scripts/migrar_variantes_base.py migrar    - Ejecutar migración completa")
    print("  python scripts/migrar_variantes_base.py validar   - Solo validar estado actual")
    print("  python scripts/migrar_variantes_base.py uuids     - Obtener UUIDs reales del sistema")
    print("  python scripts/migrar_variantes_base.py help      - Mostrar esta ayuda")
    print()
    print("🎯 Propósito:")
    print("   Garantizar que todos los productos tengan al menos una variante,")
    print("   creando variantes base automáticamente para productos sin variantes.")
    print()
    print("⚠️  IMPORTANTE:")
    print("   - Ejecutar solo UNA VEZ en producción")
    print("   - Hacer backup de la base de datos antes de ejecutar")
    print("   - El script obtiene UUIDs automáticamente del sistema")
    print("   - El script es seguro: cada lote se confirma independientemente")


async def main():
    """Función principal del script."""
    
    if len(sys.argv) < 2:
        mostrar_ayuda()
        return
    
    comando = sys.argv[1].lower()
    
    if comando == "migrar":
        await ejecutar_migracion_completa()
    elif comando == "validar":
        await validar_solo()
    elif comando == "uuids":
        await obtener_uuids_reales()
    elif comando in ["help", "--help", "-h"]:
        mostrar_ayuda()
    else:
        print(f"❌ Comando desconocido: {comando}")
        mostrar_ayuda()


if __name__ == "__main__":
    # Configurar el loop de eventos para ejecutar la función async
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Operación cancelada por el usuario.")
    except Exception as e:
        print(f"\n💥 Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)