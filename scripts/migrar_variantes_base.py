#!/usr/bin/env python3
"""
Script para migrar productos sin variantes creando variantes base automáticamente.

Uso:
    python migrar_variantes_base.py [--limite NUMERO] [--dry-run]

Variables de entorno requeridas:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Ejemplo:
    export DB_HOST=localhost
    export DB_PORT=5432
    export DB_NAME=smart_db
    export DB_USER=smartuser
    export DB_PASSWORD=Gg3sT50J9fhk55Af
    
    python migrar_variantes_base.py --limite 50
"""

import os
import sys
import argparse
import asyncio
import asyncpg
import uuid
from typing import Dict, List, Optional
from datetime import datetime

class MigradorVariantes:
    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.estado_activo_id = "75aff5e4-d984-44aa-8f19-71892ff6757c"  # ACT
        self.connection = None
        
    async def conectar(self):
        """Establece conexión a PostgreSQL"""
        try:
            self.connection = await asyncpg.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 5432)),
                database=os.getenv('DB_NAME', 'smart_db'),
                user=os.getenv('DB_USER', 'smartuser'),
                password=os.getenv('DB_PASSWORD')
            )
            
            # Establecer contexto RLS
            await self.connection.execute(f"SET app.current_tenant = '{self.tenant_id}'")
            await self.connection.execute(f"SET app.usuario = '{self.user_id}'")
            
            print("✅ Conexión establecida y contexto RLS configurado")
            
        except Exception as e:
            print(f"❌ Error conectando a la base de datos: {e}")
            sys.exit(1)
    
    async def cerrar(self):
        """Cierra la conexión"""
        if self.connection:
            await self.connection.close()
            print("🔌 Conexión cerrada")
    
    async def obtener_productos_sin_variantes(self, limite: int = 100) -> List[Dict]:
        """Obtiene productos activos que no tienen variantes"""
        query = """
        SELECT p.id_producto, p.sku, p.nombre, p.precio_base, p.codigo_barras
        FROM producto p
        WHERE p.id_estado = $1
        AND NOT EXISTS (
            SELECT 1 
            FROM producto_variante pv 
            WHERE pv.id_producto = p.id_producto 
            AND pv.id_estado = $1
        )
        ORDER BY p.created_at
        LIMIT $2
        """
        
        try:
            rows = await self.connection.fetch(query, self.estado_activo_id, limite)
            productos = []
            
            for row in rows:
                productos.append({
                    'id_producto': str(row['id_producto']),
                    'sku': row['sku'],
                    'nombre': row['nombre'],
                    'precio_base': float(row['precio_base']) if row['precio_base'] else 0.0,
                    'codigo_barras': row['codigo_barras']
                })
            
            return productos
            
        except Exception as e:
            print(f"❌ Error obteniendo productos sin variantes: {e}")
            return []
    
    def generar_sku_variante(self, producto: Dict) -> str:
        """Genera SKU único para la variante base"""
        sku_base = producto['sku'] or producto['nombre'][:20].upper().replace(" ", "_")
        #return f"{sku_base}-BASE"
        return f"{sku_base}"
    
    async def sku_variante_existe(self, sku_variante: str) -> bool:
        """Verifica si un SKU de variante ya existe"""
        query = "SELECT COUNT(*) FROM producto_variante WHERE sku_variante = $1"
        try:
            count = await self.connection.fetchval(query, sku_variante)
            return count > 0
        except:
            return False
    
    async def generar_sku_unico(self, producto: Dict) -> str:
        """Genera un SKU único verificando duplicados"""
        sku_base = self.generar_sku_variante(producto)
        sku_final = sku_base
        contador = 1
        
        while await self.sku_variante_existe(sku_final):
            sku_final = f"{sku_base}-{contador}"
            contador += 1
        
        return sku_final
    
    async def crear_variante_base(self, producto: Dict, dry_run: bool = False) -> Dict:
        """Crea una variante base para un producto"""
        try:
            sku_variante = await self.generar_sku_unico(producto)
            precio = producto['precio_base'] or 0.0
            
            if dry_run:
                return {
                    'success': True,
                    'id_producto': producto['id_producto'],
                    'sku_producto': producto['sku'],
                    'sku_variante': sku_variante,
                    'precio': precio,
                    'action': 'DRY_RUN - No se insertó'
                }
            
            # INSERT real
            query = """
            INSERT INTO producto_variante (
                id_producto,
                sku_variante,
                precio,
                peso_gr,
                codigo_barras_var,
                id_empresa,
                id_estado,
                created_by,
                modified_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id_producto_variante
            """
            
            variante_id = await self.connection.fetchval(
                query,
                uuid.UUID(producto['id_producto']),
                sku_variante,
                precio,
                0.0,  # peso_gr
                producto['codigo_barras'],  # puede ser None
                uuid.UUID(self.tenant_id),
                uuid.UUID(self.estado_activo_id),
                uuid.UUID(self.user_id),
                uuid.UUID(self.user_id)
            )
            
            return {
                'success': True,
                'id_producto': producto['id_producto'],
                'id_variante': str(variante_id),
                'sku_producto': producto['sku'],
                'sku_variante': sku_variante,
                'precio': precio,
                'action': 'CREADA'
            }
            
        except Exception as e:
            return {
                'success': False,
                'id_producto': producto['id_producto'],
                'sku_producto': producto['sku'],
                'error': str(e),
                'action': 'ERROR'
            }
    
    async def migrar(self, limite: int = 100, dry_run: bool = False):
        """Ejecuta la migración completa"""
        print(f"🚀 Iniciando migración de variantes base...")
        print(f"📊 Límite: {limite} productos")
        print(f"🧪 Modo: {'DRY RUN' if dry_run else 'PRODUCCIÓN'}")
        print(f"🏢 Tenant: {self.tenant_id}")
        print(f"👤 Usuario: {self.user_id}")
        print("-" * 70)
        
        # Obtener productos sin variantes
        productos = await self.obtener_productos_sin_variantes(limite)
        
        if not productos:
            print("ℹ️  No se encontraron productos sin variantes")
            return
        
        print(f"📦 Encontrados {len(productos)} productos sin variantes")
        print()
        
        # Estadísticas
        estadisticas = {
            'total_productos': len(productos),
            'variantes_creadas': 0,
            'errores': 0,
            'detalles': []
        }
        
        # Procesar cada producto
        for i, producto in enumerate(productos, 1):
            print(f"[{i:3d}/{len(productos)}] Procesando: {producto['sku']} - {producto['nombre'][:40]}...")
            
            resultado = await self.crear_variante_base(producto, dry_run)
            estadisticas['detalles'].append(resultado)
            
            if resultado['success']:
                estadisticas['variantes_creadas'] += 1
                print(f"    ✅ {resultado['action']}: {resultado['sku_variante']} (${resultado['precio']})")
            else:
                estadisticas['errores'] += 1
                print(f"    ❌ ERROR: {resultado['error']}")
        
        # Mostrar resumen
        print()
        print("=" * 70)
        print("📋 RESUMEN DE MIGRACIÓN")
        print("=" * 70)
        print(f"📦 Total productos procesados: {estadisticas['total_productos']}")
        print(f"✅ Variantes creadas: {estadisticas['variantes_creadas']}")
        print(f"❌ Errores: {estadisticas['errores']}")
        print(f"💯 Tasa de éxito: {(estadisticas['variantes_creadas']/estadisticas['total_productos']*100):.1f}%")
        
        if estadisticas['errores'] > 0:
            print()
            print("❌ ERRORES ENCONTRADOS:")
            for detalle in estadisticas['detalles']:
                if not detalle['success']:
                    print(f"  - {detalle['sku_producto']}: {detalle['error']}")
        
        print()
        if dry_run:
            print("🧪 MODO DRY RUN: No se realizaron cambios en la base de datos")
        else:
            print("🎉 MIGRACIÓN COMPLETADA!")
        
        return estadisticas

async def main():
    parser = argparse.ArgumentParser(description='Migrador de variantes base')
    parser.add_argument('--limite', type=int, default=100, help='Número máximo de productos a procesar')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar en modo simulación (no hace cambios)')
    parser.add_argument('--tenant-id', default='d077f79f-7731-4b15-84b3-1a226762c8c7', help='ID del tenant')
    parser.add_argument('--user-id', default='023b3905-435d-40e3-8447-eb1f444ff3fe', help='ID del usuario')
    
    args = parser.parse_args()
    
    # Verificar variables de entorno
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
        print("\nEjemplo de configuración:")
        print("export DB_HOST=localhost")
        print("export DB_PORT=5432")
        print("export DB_NAME=smart_db")
        print("export DB_USER=smartuser")
        print("export DB_PASSWORD=Gg3sT50J9fhk55Af")
        sys.exit(1)
    
    # Crear migrador y ejecutar
    migrador = MigradorVariantes(args.tenant_id, args.user_id)
    
    try:
        await migrador.conectar()
        await migrador.migrar(args.limite, args.dry_run)
    except KeyboardInterrupt:
        print("\n⚠️  Migración interrumpida por el usuario")
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")
    finally:
        await migrador.cerrar()

if __name__ == "__main__":
    asyncio.run(main())