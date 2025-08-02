# main.py
# -----------------------------------------------
# Aplicación FastAPI principal para SmartPoS 2025
# -----------------------------------------------

from fastapi import FastAPI                              # Importa la clase principal de FastAPI

# Importa routers definidos en sus respectivos módulos
from marca             import router as marcas_router         # marca.py
from forma_pago        import router as formas_pago_router    # forma_pago.py
from categoria         import router as categorias_router     # categoria.py
from umedida           import router as umedida_router        # umedida.py
from subcategoria      import router as subcategoria_router   # subcategoria.py
from empresa           import router as empresa_router        # empresa.py
from sucursal          import router as sucursal_router       # sucursal.py
from almacen           import router as almacen_router        # almacen.py
from cliente           import router as cliente_router        # cliente.py
from producto          import router as producto_router       # producto.py
from terminal          import router as terminal_router       # terminal.py
from eml               import router as entidades_router      # eml.py
from regimenfiscal     import router as regimenfiscal_router  # regimenfiscal.py
from inventario        import router as inventario_router
from venta             import router as venta_router
from venta_detalle     import router as venta_detalle_router
from pago              import router as pago_router
from producto_variante import router as producto_variante_router
from usuario           import router as usuario_router
from megacontrol       import router as megacontrol_router
from sesion_caja       import router as sesion_caja_router

# -------------------------------
# Inicialización de la aplicación
# -------------------------------
app = FastAPI(
    title="MEGAVENTA 2025"            # Nombre de la API que aparecerá en la documentación Swagger
)

@app.get("/megacontrol/latest")
async def get_latest_version():
    """
    Devuelve la versión actual del sistema como string plano
    """
    return "2025.1.1"

@app.get("/megalicencias/latest")
async def get_latest_version():
    """
    Devuelve la versión actual del sistema como string plano
    """
    return "2025.1.2"

@app.get("/megaventa/latest")
async def get_latest_version():
    """
    Devuelve la versión actual del sistema como string plano
    """
    return "2025.1.3"

# -------------------------------------------
# Inclusión de routers (módulos de endpoints)
# -------------------------------------------
app.include_router(
    marcas_router,
    prefix="/marcas",
    tags=["Marcas"]
)

app.include_router(
    formas_pago_router,
    prefix="/formas_pago",
    tags=["Formas de Pago"]
)

app.include_router(
    categorias_router,
    prefix="/categorias",
    tags=["Categorias de Productos"]
)

app.include_router(
    umedida_router,
    prefix="/umedidas",
    tags=["Unidades de medida"]
)

app.include_router(
    subcategoria_router,
    prefix="/subcategorias",
    tags=["Sub Categorías de Productos"]
)

app.include_router(
    empresa_router,
    prefix="/empresas",
    tags=["Empresas"]
)

app.include_router(
    sucursal_router,
    prefix="/sucursales",
    tags=["Sucursales"]
)

app.include_router(
    almacen_router,
    prefix="/almacenes",
    tags=["Almacenes"]
)

app.include_router(
    cliente_router,
    prefix="/clientes",
    tags=["Clientes"]
)

app.include_router(
    producto_router,
    prefix="/productos",
    tags=["Productos"]
)

app.include_router(
    terminal_router,
    prefix="/terminales",
    tags=["Terminales"]
)

app.include_router(
    entidades_router,
    prefix="/eml",
    tags=["Entidades, Municipios y Localidades"]
)

app.include_router(
    regimenfiscal_router,
    prefix="/regimen_fiscal",
    tags=["Regimen Fiscal"]
)

# Incluir los routers
app.include_router(
    inventario_router,
    prefix="/inventario",
    tags=["Inventario"]
)

app.include_router(
    venta_router,
    prefix="/ventas",
    tags=["Ventas"]
)

app.include_router(
    venta_detalle_router,
    prefix="/venta-detalles",
    tags=["Detalle de Ventas"]
)

app.include_router(
    pago_router,
    prefix="/pagos",
    tags=["Pagos de Ventas"]
)

app.include_router(
    producto_variante_router,
    prefix="/variantes",
    tags=["Variantes de Productos"]
)

app.include_router(
    usuario_router,
    prefix="/usuarios",
    tags=["Usuarios"]
)

app.include_router(
    megacontrol_router,
    prefix="/megacontrol",
    tags=["Activación de Licencias"]
)

app.include_router(
    sesion_caja_router,
    prefix="/sesion-caja",
    tags=["Sesión de Caja y Cortes X, Z"]
)

# ---------------------------
# Endpoint raíz
# ---------------------------
@app.get("/")
async def root():
    """Retorna un mensaje simple para verificar que el servicio esté en línea"""
    return {"Estatus": "Online"}
