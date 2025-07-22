# megacontrol.py
# ---------------------------
# Módulo de endpoints REST para activación de licencias.
# Versión mínima y limpia - SIN dependencias problemáticas
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid as uuid_lib

# Importar SOLO lo necesario
from db import AsyncSessionLocal

# -------------------------
# Dependencia SIN RLS
# -------------------------
async def get_db_simple() -> AsyncGenerator[AsyncSession, None]:
    """Sesión de BD simple sin RLS."""
    async with AsyncSessionLocal() as db:
        yield db

# -------------------------
# Schemas
# -------------------------
class LicenseActivationRequest(BaseModel):
    hardware_fingerprint: str = Field(..., min_length=64, max_length=64)
    company_uuid: str = Field(...)
    
    @validator('hardware_fingerprint')
    def validate_hardware_fingerprint(cls, v):
        if len(v) != 64:
            raise ValueError('La huella del hardware debe tener exactamente 64 caracteres')
        return v
    
    @validator('company_uuid')
    def validate_company_uuid(cls, v):
        try:
            uuid_lib.UUID(v)
        except ValueError:
            raise ValueError('El UUID de empresa no tiene un formato válido')
        return v

class LicenseActivationResponse(BaseModel):
    success: bool
    message: str
    activation_id: Optional[str] = None
    activation_timestamp: Optional[datetime] = None
    empresa_data: Optional[dict] = None  # Datos de la empresa

# -------------------------
# Router
# -------------------------
router = APIRouter()

@router.post("/", response_model=LicenseActivationResponse, summary="Activar Licencia")
async def activar_licencia(
    request: LicenseActivationRequest,
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    db: AsyncSession = Depends(get_db_simple)
):
    """Activa una licencia."""
    try:
        # Insertar directamente - PostgreSQL validará la foreign key
        insert_query = text("""
            INSERT INTO licencias 
            (id_empresa, hardware_fingerprint, activation_timestamp, status)
            VALUES 
            (:id_empresa, :hardware_fingerprint, :activation_timestamp, 'activa')
            RETURNING id, activation_timestamp
        """)
        
        activation_timestamp = datetime.now(timezone.utc)
        
        result = await db.execute(insert_query, {
            "id_empresa": request.company_uuid,
            "hardware_fingerprint": request.hardware_fingerprint,
            "activation_timestamp": activation_timestamp
        })
        
        new_activation = result.fetchone()
        
        # Consultar datos de la empresa para mostrar en respuesta
        empresa_query = text("""
            SELECT 
                rfc,
                razon_social,
                nombre_comercial,
                email_contacto,
                telefono
            FROM empresa 
            WHERE id_empresa = :id_empresa
        """)
        
        empresa_result = await db.execute(empresa_query, {"id_empresa": request.company_uuid})
        empresa_data = empresa_result.fetchone()
        
        await db.commit()
        
        # Preparar datos de la empresa para la respuesta
        empresa_info = None
        if empresa_data:
            empresa_info = {
                "rfc": empresa_data.rfc,
                "razon_social": empresa_data.razon_social,
                "nombre_comercial": empresa_data.nombre_comercial,
                "email_contacto": empresa_data.email_contacto,
                "telefono": empresa_data.telefono
            }
        
        return LicenseActivationResponse(
            success=True,
            message="Licencia activada exitosamente",
            activation_id=str(new_activation.id),
            activation_timestamp=new_activation.activation_timestamp,
            empresa_data=empresa_info
        )
        
    except Exception as e:
        await db.rollback()
        
        # Detectar error de foreign key
        if "fk_licencias_empresa" in str(e) or "foreign key constraint" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={"message": "La empresa especificada no existe en el sistema"}
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={"message": f"Error interno del servidor: {str(e)}"}
            )

@router.get("/activations/{company_uuid}", summary="Consultar Activaciones")
async def consultar_activaciones(
    company_uuid: str,
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    db: AsyncSession = Depends(get_db_simple),
    limit: int = 100
):
    """Consulta activaciones de una empresa."""
    try:
        query = text("""
            SELECT 
                l.id,
                l.hardware_fingerprint,
                l.activation_timestamp,
                l.status
            FROM licencias l
            WHERE l.id_empresa = :company_uuid
            ORDER BY l.activation_timestamp DESC
            LIMIT :limit
        """)
        
        result = await db.execute(query, {
            "company_uuid": company_uuid,
            "limit": limit
        })
        
        activations = []
        for row in result.fetchall():
            activations.append({
                "id": str(row.id),
                "hardware_fingerprint": row.hardware_fingerprint,
                "activation_timestamp": row.activation_timestamp,
                "status": row.status
            })
        
        return {
            "success": True,
            "company_uuid": company_uuid,
            "total_activations": len(activations),
            "activations": activations
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error al consultar activaciones: {str(e)}"}
        )