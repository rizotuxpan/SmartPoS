# megacontrol.py
# ---------------------------
# Módulo de endpoints REST para activación de licencias.
# Versión limpia y funcional
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
# Dependencia con configuración de variables de sesión
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
            raise ValueError('La clave de empresa no tiene un formato válido')
        return v

class LicenseActivationResponse(BaseModel):
    success: bool
    message: str
    activation_id: Optional[str] = None
    activation_timestamp: Optional[datetime] = None
    empresa_data: Optional[dict] = None

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
    """
    Activa una licencia para una empresa específica.
    Permite múltiples activaciones para el mismo hardware.
    """
    try:
        # Configurar variables de sesión requeridas por los triggers
        # PostgreSQL SET no acepta parámetros, usar valores literales
        await db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
        await db.execute(text(f"SET app.usuario = '{user_id}'"))
        
        # Insertar nueva licencia
        insert_query = text("""
            INSERT INTO licencia 
            (id_empresa, hardware_fingerprint, activation_timestamp, tipo_licencia, estatus, created_by, modified_by)
            VALUES 
            (:id_empresa, :hardware_fingerprint, :activation_timestamp, :tipo_licencia, 'activa', :created_by, :created_by)
            RETURNING id_licencia, activation_timestamp
        """)
        
        activation_timestamp = datetime.now(timezone.utc)
        
        result = await db.execute(insert_query, {
            "id_empresa": request.company_uuid,
            "hardware_fingerprint": request.hardware_fingerprint,
            "activation_timestamp": activation_timestamp,
            "tipo_licencia": "suscripción",
            "created_by": user_id
        })
        
        new_activation = result.fetchone()
        
        # Consultar datos de la empresa
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
        
        # Preparar datos de la empresa
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
            activation_id=str(new_activation.id_licencia),
            activation_timestamp=new_activation.activation_timestamp,
            empresa_data=empresa_info
        )
        
    except Exception as e:
        await db.rollback()
        
        # Detectar error de foreign key
        if "fk_licencias_empresa" in str(e) or "foreign key constraint" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail={"message": "La clave de empresa no es válida"}
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
    """
    Consulta todas las activaciones de licencias de una empresa específica.
    """
    try:
        # Configurar variables de sesión
        await db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
        await db.execute(text(f"SET app.usuario = '{user_id}'"))
        
        # Validar UUID de empresa
        try:
            uuid_lib.UUID(company_uuid)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": "La clave de empresa no tiene un formato válido"}
            )

        query = text("""
            SELECT 
                l.id_licencia,
                l.hardware_fingerprint,
                l.activation_timestamp,
                l.tipo_licencia,
                l.estatus,
                l.created_at,
                l.updated_at
            FROM licencia l
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
                "id_licencia": str(row.id_licencia),
                "hardware_fingerprint": row.hardware_fingerprint,
                "activation_timestamp": row.activation_timestamp,
                "tipo_licencia": row.tipo_licencia,
                "estatus": row.estatus,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        
        return {
            "success": True,
            "company_uuid": company_uuid,
            "total_activations": len(activations),
            "activations": activations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error al consultar activaciones: {str(e)}"}
        )

@router.get("/license/{license_id}", summary="Consultar Licencia")
async def consultar_licencia(
    license_id: str,
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    db: AsyncSession = Depends(get_db_simple)
):
    """
    Consulta información detallada de una licencia específica.
    """
    try:
        # Configurar variables de sesión
        await db.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
        await db.execute(text(f"SET app.usuario = '{user_id}'"))
        
        # Validar UUID
        try:
            uuid_lib.UUID(license_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": "La clave de licencia no tiene un formato válido"}
            )

        query = text("""
            SELECT 
                id_licencia,
                hardware_fingerprint,
                activation_timestamp,
                tipo_licencia,
                estatus,
                created_at,
                updated_at
            FROM licencia
            WHERE id_licencia = :license_id
        """)
        
        result = await db.execute(query, {"license_id": license_id})
        license_data = result.fetchone()
        
        if not license_data:
            raise HTTPException(
                status_code=404,
                detail={"message": "La licencia especificada no existe"}
            )
        
        return {
            "id_licencia": str(license_data.id_licencia),
            "hardware_fingerprint": license_data.hardware_fingerprint,
            "activation_timestamp": license_data.activation_timestamp,
            "tipo_licencia": license_data.tipo_licencia,
            "estatus": license_data.estatus,
            "created_at": license_data.created_at,
            "updated_at": license_data.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error al consultar licencia: {str(e)}"}
        )