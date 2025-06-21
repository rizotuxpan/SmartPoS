# utils/contexto.py

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi import HTTPException


async def obtener_contexto(db: AsyncSession) -> dict:
    """
    Recupera los valores de tenant y usuario desde las variables de sesión de PostgreSQL.
    Requiere que hayan sido seteadas previamente con SET LOCAL.

    Retorna:
        dict: {
            "tenant_id": UUID,
            "user_id": UUID
        }

    Lanza:
        HTTPException 500 si no se pueden recuperar o convertir los valores.
    """
    try:
        result = await db.execute(
            text("SELECT current_setting('app.current_tenant'), current_setting('app.usuario')")
        )
        tenant_id_str, user_id_str = result.fetchone()

        return {
            "tenant_id": UUID(tenant_id_str),
            "user_id": UUID(user_id_str)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo obtener el contexto del usuario: {str(e)}"
        )
