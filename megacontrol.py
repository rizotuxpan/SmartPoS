# megacontrol.py
# ---------------------------
# Módulo de endpoints REST para activación de licencias.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field, validator
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid as uuid_lib

from db import get_async_db

# -------------------------
# Schemas Pydantic
# -------------------------
class LicenseActivationRequest(BaseModel):
    hardware_fingerprint: str = Field(..., min_length=64, max_length=64, description="Huella del hardware (64 caracteres)")
    company_uuid: str = Field(..., description="UUID de la empresa")
    
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
    activation_id: Optional[str] = None  # UUID como string
    activation_timestamp: Optional[datetime] = None

# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.post("/", response_model=LicenseActivationResponse, summary="Activar Licencia")
async def activar_licencia(
    request: LicenseActivationRequest,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID")
):
    """
    Activa una licencia verificando que el UUID de empresa exista 
    y registrando la activación en la tabla license_activations.
    """
    try:
        # Establecer variables de sesión para RLS
        await db.execute(text("SET SESSION app.tenant_id = :tenant_id"), {"tenant_id": tenant_id})
        await db.execute(text("SET SESSION app.user_id = :user_id"), {"user_id": user_id})
        
        # Verificar que existe la empresa
        empresa_query = text("""
            SELECT id_empresa 
            FROM empresa 
            WHERE id_empresa = :company_uuid
        """)
        
        result = await db.execute(empresa_query, {"company_uuid": request.company_uuid})
        empresa = result.fetchone()
        
        if not empresa:
            raise HTTPException(
                status_code=404, 
                detail={"message": "La empresa especificada no existe en el sistema"}
            )
        
        # Insertar registro de activación
        insert_query = text("""
            INSERT INTO licencias 
            (id_empresa, hardware_fingerprint, activation_timestamp, status)
            VALUES 
            (:id_empresa, :hardware_fingerprint, :activation_timestamp, 'activa')
            RETURNING id, activation_timestamp
        """)
        
        activation_timestamp = datetime.now(timezone.utc)
        
        activation_result = await db.execute(insert_query, {
            "id_empresa": request.company_uuid,
            "hardware_fingerprint": request.hardware_fingerprint,
            "activation_timestamp": activation_timestamp
        })
        
        new_activation = activation_result.fetchone()
        await db.commit()
        
        return LicenseActivationResponse(
            success=True,
            message="Licencia activada exitosamente",
            activation_id=new_activation.id,
            activation_timestamp=new_activation.activation_timestamp
        )
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error interno del servidor: {str(e)}"}
        )

@router.get("/activations/{company_uuid}", summary="Consultar Activaciones")
async def consultar_activaciones(
    company_uuid: str,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    limit: int = 100
):
    """
    Consulta el historial de activaciones para una empresa específica.
    """
    try:
        # Establecer variables de sesión para RLS
        await db.execute(text("SET SESSION app.tenant_id = :tenant_id"), {"tenant_id": tenant_id})
        await db.execute(text("SET SESSION app.user_id = :user_id"), {"user_id": user_id})
        
        query = text("""
            SELECT 
                l.id,
                l.hardware_fingerprint,
                l.activation_timestamp,
                l.status,
                e.nombre as empresa_nombre
            FROM licencias l
            JOIN empresa e ON l.id_empresa = e.id_empresa
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
                "id": row.id,
                "hardware_fingerprint": row.hardware_fingerprint,
                "activation_timestamp": row.activation_timestamp,
                "status": row.status,
                "empresa_nombre": row.empresa_nombre
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