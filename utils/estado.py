# utils/estado.py

from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

# -------------------------------
# Caché en memoria de estados
# -------------------------------
# Este diccionario almacena en RAM los UUID ya consultados,
# evitando múltiples viajes a la base de datos para la misma clave.
# La clave del dict es la clave de estado en minúsculas ("act", "ina", etc.)
# y el valor es el UUID correspondiente.
estado_cache: dict[str, UUID] = {}

async def get_estado_id_por_clave(clave: str, db: AsyncSession) -> UUID:
    """
    Recupera el UUID de un estado dado su clave única (columna 'clave' en cat_estado).

    Parámetros:
    - clave (str): clave del estado a buscar (p.ej. "act", "ina").
    - db (AsyncSession): sesión asíncrona de SQLAlchemy ya configurada con RLS.

    Retorna:
    - UUID del estado encontrado.

    Excepciones:
    - HTTPException 404 si no se encuentra ningún registro con esa clave.
    """
    # 1) Normalizar la clave a minúsculas para consulta uniforme.
    clave_lower = clave.lower()

    # 2) Si ya la tenemos en caché, devolvemos inmediatamente el UUID:
    if clave_lower in estado_cache:
        return estado_cache[clave_lower]

    # 3) Construir y ejecutar la consulta SQL para buscar el id_estado.
    #    Usamos la sesión 'db' para mantener las variables SET LOCAL
    #    (app.current_tenant, app.usuario) y respetar las políticas RLS.
    result = await db.execute(
        text("""
            SELECT id_estado
              FROM cat_estado
             WHERE lower(clave) = :clave
             LIMIT 1
        """),
        {"clave": clave_lower}
    )

    # 4) Extraer el resultado: puede ser None si no existe.
    row = result.scalar_one_or_none()
    if not row:
        # 5) Lanzar excepción HTTP 404 para que FastAPI devuelva un Not Found.
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró el estado '{clave}'"
        )

    # 6) Convertir el valor obtenido (row) a UUID.
    #    row puede venir como str o UUID; lo envolvemos en UUID(...) para garantizar el tipo.
    estado_id = UUID(str(row))

    # 7) Guardar en caché para futuras llamadas durante el ciclo de vida de la app.
    estado_cache[clave_lower] = estado_id

    # 8) Devolver el UUID encontrado.
    return estado_id
