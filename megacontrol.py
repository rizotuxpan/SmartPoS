# megacontrol.py
# ---------------------------
# Módulo de endpoints REST para activación de licencias.
# Versión actualizada para nueva estructura de tabla 'licencia'
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field, validator
from typing import Optional, AsyncGenerator, Literal
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
    tipo_licencia: Optional[Literal["trial", "perpetua", "suscripción", "OEM"]] = Field(default="trial")
    created_by: Optional[str] = Field(default=None)  # Opcional - se usará user_id del header si no se proporciona
    
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
        
    @validator('created_by')
    def validate_created_by(cls, v):
        if v is not None:
            try:
                uuid_lib.UUID(v)
            except ValueError:
                raise ValueError('El UUID de created_by no tiene un formato válido')
        return v

class LicenseActivationResponse(BaseModel):
    success: bool
    message: str
    activation_id: Optional[str] = None
    activation_timestamp: Optional[datetime] = None
    tipo_licencia: Optional[str] = None
    estatus: Optional[str] = None
    empresa_data: Optional[dict] = None  # Datos de la empresa

class LicenseStatusUpdate(BaseModel):
    nuevo_estatus: Literal["activa", "revocada", "expirada", "suspendida"] = Field(...)
    modified_by: Optional[str] = Field(default=None)  # Opcional - se usará user_id del header si no se proporciona
    
    @validator('modified_by')
    def validate_modified_by(cls, v):
        if v is not None:
            try:
                uuid_lib.UUID(v)
            except ValueError:
                raise ValueError('El UUID de modified_by no tiene un formato válido')
        return v

class LicenseInfo(BaseModel):
    id_licencia: str
    hardware_fingerprint: str
    activation_timestamp: datetime
    tipo_licencia: str
    estatus: str
    created_at: datetime
    updated_at: datetime

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
    
    - **hardware_fingerprint**: Huella única del hardware (64 caracteres)
    - **company_uuid**: UUID de la empresa
    - **tipo_licencia**: Tipo de licencia (trial, perpetua, suscripción, OEM)
    - **created_by**: UUID del usuario que crea la licencia
    """
    try:
        # Usar created_by del request o user_id del header como fallback
        created_by_value = request.created_by or user_id
        
        # Insertar nueva licencia
        insert_query = text("""
            INSERT INTO licencia 
            (id_empresa, hardware_fingerprint, activation_timestamp, tipo_licencia, estatus, created_by, modified_by)
            VALUES 
            (:id_empresa, :hardware_fingerprint, :activation_timestamp, :tipo_licencia, 'activa', :created_by, :created_by)
            RETURNING id_licencia, activation_timestamp, tipo_licencia, estatus
        """)
        
        activation_timestamp = datetime.now(timezone.utc)
        
        result = await db.execute(insert_query, {
            "id_empresa": request.company_uuid,
            "hardware_fingerprint": request.hardware_fingerprint,
            "activation_timestamp": activation_timestamp,
            "tipo_licencia": request.tipo_licencia or "trial",
            "created_by": created_by_value
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
            activation_id=str(new_activation.id_licencia),
            activation_timestamp=new_activation.activation_timestamp,
            tipo_licencia=new_activation.tipo_licencia,
            estatus=new_activation.estatus,
            empresa_data=empresa_info
        )
        
    except HTTPException:
        await db.rollback()
        raise
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
    """
    Consulta todas las activaciones de licencias de una empresa específica.
    
    - **company_uuid**: UUID de la empresa
    - **limit**: Número máximo de registros a retornar (default: 100)
    """
    try:
        # Validar UUID de empresa
        try:
            uuid_lib.UUID(company_uuid)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": "El UUID de empresa no tiene un formato válido"}
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

@router.patch("/license/{license_id}/status", summary="Actualizar Estatus de Licencia")
async def actualizar_estatus_licencia(
    license_id: str,
    request: LicenseStatusUpdate,
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    db: AsyncSession = Depends(get_db_simple)
):
    """
    Actualiza el estatus de una licencia específica.
    
    - **license_id**: UUID de la licencia
    - **nuevo_estatus**: Nuevo estatus (activa, revocada, expirada, suspendida)
    - **modified_by**: UUID del usuario que realiza la modificación
    """
    try:
        # Validar UUID de licencia
        try:
            uuid_lib.UUID(license_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": "El UUID de licencia no tiene un formato válido"}
            )

        # Verificar que la licencia existe
        check_query = text("""
            SELECT id_licencia, estatus 
            FROM licencia 
            WHERE id_licencia = :license_id
        """)
        
        existing = await db.execute(check_query, {"license_id": license_id})
        license_data = existing.fetchone()
        
        if not license_data:
            raise HTTPException(
                status_code=404,
                detail={"message": "La licencia especificada no existe"}
            )

        # Usar modified_by del request o user_id del header como fallback
        modified_by_value = request.modified_by or user_id
        
        # Actualizar estatus
        update_query = text("""
            UPDATE licencia 
            SET estatus = :nuevo_estatus,
                modified_by = :modified_by,
                updated_at = CURRENT_TIMESTAMP
            WHERE id_licencia = :license_id
            RETURNING id_licencia, estatus, updated_at
        """)
        
        result = await db.execute(update_query, {
            "license_id": license_id,
            "nuevo_estatus": request.nuevo_estatus,
            "modified_by": modified_by_value
        })
        
        updated_license = result.fetchone()
        await db.commit()
        
        return {
            "success": True,
            "message": f"Estatus de licencia actualizado de '{license_data.estatus}' a '{request.nuevo_estatus}'",
            "license_id": str(updated_license.id_licencia),
            "nuevo_estatus": updated_license.estatus,
            "updated_at": updated_license.updated_at
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error al actualizar estatus: {str(e)}"}
        )

@router.get("/license/{license_id}", response_model=LicenseInfo, summary="Consultar Licencia")
async def consultar_licencia(
    license_id: str,
    tenant_id: str = Header(..., alias="Tenant_ID"),
    user_id: str = Header(..., alias="User_ID"),
    db: AsyncSession = Depends(get_db_simple)
):
    """
    Consulta información detallada de una licencia específica.
    
    - **license_id**: UUID de la licencia
    """
    try:
        # Validar UUID
        try:
            uuid_lib.UUID(license_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"message": "El UUID de licencia no tiene un formato válido"}
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
        
        return LicenseInfo(
            id_licencia=str(license_data.id_licencia),
            hardware_fingerprint=license_data.hardware_fingerprint,
            activation_timestamp=license_data.activation_timestamp,
            tipo_licencia=license_data.tipo_licencia,
            estatus=license_data.estatus,
            created_at=license_data.created_at,
            updated_at=license_data.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": f"Error al consultar licencia: {str(e)}"}
        )