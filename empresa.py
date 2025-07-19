# empresa.py
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Empresa.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.
# Crea automáticamente un usuario admin al crear empresa.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel                                  # Pydantic para schemas de entrada/salida
from typing import Optional, List                               # Tipos para anotaciones
from uuid import UUID, uuid4                                    # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, Text, DateTime, func, select, text, insert, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# IMPORTANTE: Importar modelos Usuario, Sucursal y Terminal desde donde ya están definidos
# Asumiendo que están en archivos separados
# Ajusta la ruta según tu estructura de proyecto
try:
    from models.usuario import Usuario  # Ajusta la ruta según tu estructura
    from models.sucursal import Sucursal
    from models.terminal import Terminal
except ImportError:
    # Si no funciona, intenta con otras rutas comunes
    try:
        from usuario import Usuario
        from sucursal import Sucursal
        from terminal import Terminal
    except ImportError:
        from models import Usuario, Sucursal, Terminal

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Empresa(Base):
    __tablename__ = "empresa"  # Nombre de la tabla en la BD

    id_empresa = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    razon_social = Column(String(255), nullable=False)
    nombre_comercial = Column(String(150))
    rfc = Column(CITEXT, nullable=False)
    email_contacto = Column(CITEXT)
    telefono = Column(String(30))
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_by = Column(PG_UUID(as_uuid=True), nullable=True)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=True)

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class EmpresaBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Empresa.
    """
    razon_social: str
    nombre_comercial: Optional[str] = None
    rfc: str
    email_contacto: Optional[str] = None
    telefono: Optional[str] = None

class EmpresaCreate(EmpresaBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class EmpresaUpdate(EmpresaBase):
    """Esquema para actualización; hereda todos los campos base."""
    pass

class EmpresaRead(EmpresaBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_empresa: UUID
    id_estado: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]
    modified_by: Optional[UUID]

    model_config = {"from_attributes": True}  # Permitir conversión desde objeto ORM

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_empresas(
    razon_social: Optional[str] = Query(None),  # Filtro por razón social (ilike)
    skip: int = 0,                              # Paginación: offset
    limit: int = 100,                           # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)    # Sesión RLS inyectada
):
    """
    Lista empresas en estado "activo" con paginación y filtro opcional.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(Empresa.id_estado == estado_activo_id)
    if razon_social:
        stmt = stmt.where(Empresa.razon_social.ilike(f"%{razon_social}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [EmpresaRead.model_validate(e) for e in data]
    }

@router.get("/{id_empresa}", response_model=EmpresaRead)
async def obtener_empresa(
    id_empresa: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una empresa por su ID, sólo si está en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(
        Empresa.id_empresa == id_empresa,
        Empresa.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    empresa = result.scalar_one_or_none()

    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    return EmpresaRead.model_validate(empresa)

@router.post("/", response_model=dict, status_code=201)
async def crear_empresa(
    entrada: EmpresaCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea una nueva empresa y automáticamente crea un usuario admin asociado.
    Aplica RLS y defaults de servidor.
    """
    try:
        ctx = await obtener_contexto(db)

        # 1) Crear la empresa
        nueva = Empresa(
            razon_social      = entrada.razon_social,
            nombre_comercial  = entrada.nombre_comercial,
            rfc               = entrada.rfc,
            email_contacto    = entrada.email_contacto,
            telefono          = entrada.telefono,
            created_by        = ctx["user_id"],
            modified_by       = ctx["user_id"]
        )
        db.add(nueva)
        await db.flush()  # Obtener el ID de la empresa sin hacer commit
        await db.refresh(nueva)

        # 2) Establecer el contexto RLS para la nueva empresa
        await db.execute(text("SELECT set_config('app.current_tenant', :tenant_id, false)"), 
                        {"tenant_id": str(nueva.id_empresa)})

        # 3) Hashear contraseña para el usuario admin
        password_hash_result = await db.execute(
            select(func.hash_password("12345"))
        )
        password_hash = password_hash_result.scalar()

        # 4) Crear usuario admin automáticamente
        usuario_admin = Usuario(
            nombre="Administrador",
            apellido="Mega Ventas",
            email="usuario@mail.com",
            usuario="admin",
            password_hash=password_hash,
            id_rol=UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
            id_empresa=nueva.id_empresa,  # Asignar la empresa recién creada
            created_by=ctx["user_id"],
            modified_by=ctx["user_id"]
        )
        db.add(usuario_admin)
        await db.flush()

        # 5) Crear sucursal principal automáticamente
        sucursal_principal = Sucursal(
            codigo="00",
            nombre="PRINCIPAL",
            direccion="CONOCIDO",
            telefono="0123456789",
            id_empresa=nueva.id_empresa,  # Asignar la empresa recién creada
            created_by=ctx["user_id"],
            modified_by=ctx["user_id"]
        )
        db.add(sucursal_principal)
        await db.flush()
        await db.refresh(sucursal_principal)  # Obtener el ID de la sucursal

        # 6) Crear terminal principal automáticamente
        terminal_principal = Terminal(
            id_sucursal=sucursal_principal.id_sucursal,  # Usar el ID de la sucursal recién creada
            codigo="00",
            nombre="CAJA 0",
            created_by=ctx["user_id"],
            modified_by=ctx["user_id"]
        )
        db.add(terminal_principal)
        await db.flush()

        # 7) Commit de toda la transacción
        await db.commit()

        return {
            "success": True, 
            "message": "Empresa creada exitosamente con usuario admin, sucursal principal y terminal",
            "data": EmpresaRead.model_validate(nueva),
            "admin_usuario": "admin",
            "sucursal_principal": "00",
            "terminal_principal": "00"
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Error al crear empresa, usuario admin, sucursal principal y terminal: {str(e)}"
        )

@router.put("/{id_empresa}", response_model=dict)
async def actualizar_empresa(
    id_empresa: UUID,
    entrada: EmpresaUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de una empresa en estado "activo".
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)

    stmt = select(Empresa).where(
        Empresa.id_empresa == id_empresa,
        Empresa.id_estado   == estado_activo_id
    )
    result = await db.execute(stmt)
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    ctx = await obtener_contexto(db)
    empresa.razon_social     = entrada.razon_social
    empresa.nombre_comercial = entrada.nombre_comercial
    empresa.rfc              = entrada.rfc
    empresa.email_contacto   = entrada.email_contacto
    empresa.telefono         = entrada.telefono
    empresa.modified_by      = ctx["user_id"]

    await db.flush()
    await db.refresh(empresa)
    await db.commit()

    return {"success": True, "data": EmpresaRead.model_validate(empresa)}

@router.delete("/{id_empresa}", status_code=200)
async def eliminar_empresa(
    id_empresa: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente una empresa y su usuario admin asociado.
    Se respetan políticas RLS.
    """
    try:
        # 1) Verificar que la empresa existe
        result = await db.execute(
            select(Empresa).where(Empresa.id_empresa == id_empresa)
        )
        empresa = result.scalar_one_or_none()
        if not empresa:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")

        # 2) Establecer contexto RLS para la empresa que se va a eliminar
        await db.execute(text("SELECT set_config('app.current_tenant', :tenant_id, false)"), 
                        {"tenant_id": str(id_empresa)})

        # 3) Eliminar el usuario admin de esta empresa
        await db.execute(
            delete(Usuario).where(
                Usuario.id_empresa == id_empresa,
                Usuario.usuario == "admin"
            )
        )

        # 4) Eliminar la terminal principal "00" de esta empresa
        # Primero obtenemos el ID de la sucursal para eliminar la terminal
        sucursal_result = await db.execute(
            select(Sucursal.id_sucursal).where(
                Sucursal.id_empresa == id_empresa,
                Sucursal.codigo == "00"
            )
        )
        sucursal_id = sucursal_result.scalar_one_or_none()
        
        if sucursal_id:
            await db.execute(
                delete(Terminal).where(
                    Terminal.id_sucursal == sucursal_id,
                    Terminal.codigo == "00"
                )
            )

        # 5) Eliminar la sucursal principal "00" de esta empresa
        await db.execute(
            delete(Sucursal).where(
                Sucursal.id_empresa == id_empresa,
                Sucursal.codigo == "00"
            )
        )

        # 6) Eliminar la empresa
        await db.execute(delete(Empresa).where(Empresa.id_empresa == id_empresa))

        # 7) Commit de toda la transacción
        await db.commit()

        return {
            "success": True, 
            "message": "Empresa, usuario admin, sucursal principal y terminal eliminados permanentemente"
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Error al eliminar empresa, usuario admin, sucursal principal y terminal: {str(e)}"
        )