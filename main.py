# main.py
# -----------------------------------------------
# Aplicación FastAPI principal para SmartPoS 2025
# -----------------------------------------------

from fastapi import FastAPI                              # Importa la clase principal de FastAPI
                                                         # Importa endpoints definidos en:
from marca        import router as marcas_router         # marca.py
from forma_pago   import router as formas_pago_router    # forma_pago.py
from categoria    import router as categorias_router     # categoria.py
from umedida      import router as umedida_router        # umedida.py
from subcategoria import router as subcategoria_router   # subcategoria.py
from empresa      import router as empresa_router        # empresa.py
from sucursal     import router as sucursal_router       # sucursal.py
from almacen      import router as almacen_router        # almacen.py
from cliente      import router as cliente_router        # cliente.py
from producto     import router as producto_router       # producto.py

# -------------------------------
# Inicialización de la aplicación
# -------------------------------
app = FastAPI(
    title="SmartPoS 2025"            # Nombre de la API que aparecerá en la documentación Swagger
)

# -------------------------------------------
# Inclusión de routers (módulos de endpoints)
# -------------------------------------------
# Aquí montamos el router de marcas bajo el prefijo /marcas
# - prefix: ruta base para todos los endpoints del router
# - tags: agrupa en la UI de documentación las operaciones bajo "Marcas"
app.include_router(
    marcas_router,                         # Router importado de marca.py
    prefix="/marcas",                      # Todas las rutas definidas en ese router irán bajo /marcas
    tags=["Marcas"]                        # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    formas_pago_router,                    # Router importado de marca.py
    prefix="/formas_pago",                 # Todas las rutas definidas en ese router irán bajo /formas_pago
    tags=["Formas de Pago"]                # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    categorias_router,                     # Router importado de categoria.py
    prefix="/categorias",                  # Todas las rutas definidas en ese router irán bajo /categorias
    tags=["Categorias de Productos"]       # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    umedida_router,                        # Router importado de umedida.py
    prefix="/umedidas",                    # Todas las rutas definidas en ese router irán bajo /umedidas
    tags=["Unidades de medida"]            # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    subcategoria_router,                   # Router importado de subcategoria.py
    prefix="/subcategorias",               # Todas las rutas definidas en ese router irán bajo /subcategorias
    tags=["Sub Categorías de Productos"]   # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    empresa_router,                        # Router importado de empresa.py
    prefix="/empresas",                    # Todas las rutas definidas en ese router irán bajo /empresas
    tags=["Empresas"]                      # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    sucursal_router,                       # Router importado de sucursal.py
    prefix="/sucursales",                  # Todas las rutas definidas en ese router irán bajo /sucursales
    tags=["Sucursales"]                    # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    almacen_router,                        # Router importado de almacen.py
    prefix="/almacenes",                   # Todas las rutas definidas en ese router irán bajo /almacenes
    tags=["Almacenes"]                     # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    cliente_router,                        # Router importado de cliente.py
    prefix="/clientes",                    # Todas las rutas definidas en ese router irán bajo /clientes
    tags=["Clientes"]                      # Etiqueta para organizar la documentación de OpenAPI
)

app.include_router(
    producto_router,                        # Router importado de producto.py
    prefix="/productos",                    # Todas las rutas definidas en ese router irán bajo /productos
    tags=["Productos"]                      # Etiqueta para organizar la documentación de OpenAPI
)

# ---------------------------
# Endpoint raíz
# ---------------------------
@app.get("/")                           # Define un GET en la ruta raíz '/'
async def root():                       # Función asíncrona que maneja la petición
    # Retorna un mensaje JSON simple para verificar que el servicio esté en línea
    return {"Welcome": "SmartPoS 2025"}

