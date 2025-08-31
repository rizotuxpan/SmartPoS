@echo off

:: Script simple para depuración
echo === DEPURACIÓN UVICORN ===

:: Verificar directorio actual
echo Directorio actual: %CD%
echo.

:: Verificar archivos Python
echo Archivos Python encontrados:
dir *.py
echo.

:: Activar entorno virtual
echo Activando entorno virtual...
call .\venv\Scripts\activate.bat

:: Verificar instalaciones
echo Verificando instalaciones...
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import uvicorn; print(f'Uvicorn instalado: {uvicorn.__version__}')" 2>nul || echo "❌ Uvicorn NO instalado"
python -c "import fastapi; print(f'FastAPI instalado: {fastapi.__version__}')" 2>nul || echo "❌ FastAPI NO instalado"

:: Verificar main.py
echo.
echo Verificando main.py...
if exist main.py (
    echo main.py existe
    python -c "import main; print(' main.py importa correctamente')" 2>nul || echo "Error al importar main.py"
    python -c "import main; print(f'app encontrada: {hasattr(main, \"app\")}')" 2>nul || echo "Variable app no encontrada"
) else (
    echo main.py NO existe
)

:: Verificar puerto
echo.
echo Verificando puerto 8000...
netstat -an | findstr ":8000" >nul && echo "Puerto 8000 en uso" || echo "Puerto 8000 disponible"

:: Configurar variables
echo.
echo Configurando variables de entorno...
set DB_PASSWORD=Gg3sT50J9fhk55Af
set DB_USER=smartuser
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=smart_db

echo Variables configuradas:
echo DB_HOST=%DB_HOST% DB_PORT=%DB_PORT% DB_NAME=%DB_NAME% DB_USER=%DB_USER%

:: Intentar inicio
echo.
echo ========================
echo Intentando iniciar uvicorn...
echo ========================
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

pause
