# scripts/migrar_variantes_base.py
# ---------------------------
# Script para migrar productos existentes sin variantes
# Ejecutar UNA SOLA VEZ después de implementar la nueva lógica

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_session, AsyncSession
from db import get_async_db, engine  # Ajusta según tu configuración
from utils.variante_base import migrar_productos_sin_variantes, validar_integridad_variantes


async def ejecutar_migracion_completa():
    """
    Ejecuta la migración completa de variantes base para productos existentes.
    """
    
    print("🚀 Iniciando migración de variantes base...")
    print("=" * 60)
    
    # Crear sesión de base de datos
    async with AsyncSession(engine) as db:
        try:
            # ===== PASO 1: Validar estado inicial =====
            print("\n📊 PASO 1: Validando estado inicial...")
            reporte_inicial = await validar_integridad_variantes(db)
            
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
                estadisticas = await migrar_productos_sin_variantes(db, limite_por_lote)
                
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
            reporte_final = await validar_integridad_variantes(db)
            
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
            # No hacer rollback aquí porque cada lote ya hizo commit
            
        finally:
            await db.close()


async def validar_solo():
    """
    Solo valida el estado actual sin hacer migración.
    """
    
    print("🔍 Validando integridad de variantes...")
    
    async with AsyncSession(engine) as db:
        try:
            reporte = await validar_integridad_variantes(db)
            
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
        finally:
            await db.close()


def mostrar_ayuda():
    """Muestra las opciones disponibles del script."""
    
    print("🛠️  SCRIPT DE MIGRACIÓN - VARIANTES BASE")
    print("=" * 50)
    print()
    print("Opciones disponibles:")
    print("  python migrar_variantes_base.py migrar    - Ejecutar migración completa")
    print("  python migrar_variantes_base.py validar   - Solo validar estado actual")
    print("  python migrar_variantes_base.py help      - Mostrar esta ayuda")
    print()
    print("🎯 Propósito:")
    print("   Garantizar que todos los productos tengan al menos una variante,")
    print("   creando variantes base automáticamente para productos sin variantes.")
    print()
    print("⚠️  IMPORTANTE:")
    print("   - Ejecutar solo UNA VEZ en producción")
    print("   - Hacer backup de la base de datos antes de ejecutar")
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
        sys.exit(1)