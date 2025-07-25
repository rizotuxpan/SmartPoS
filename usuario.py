# usuario.py - VERSIÓN FINAL CORREGIDA
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Usuario.
# Incluye CRUD completo, autenticación y manejo seguro de contraseñas.
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# Implementa Row-Level Security (RLS) vía variables de sesión en PostgreSQL.

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel, EmailStr                       # Pydantic para schemas de entrada/salida
from typing import Optional                                     # Tipos para anotaciones
from uuid import UUID                                           # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import Column, String, DateTime, func, select, text, delete
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
from sqlalchemy.ext.asyncio import AsyncSession                # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_estado = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    id_rol = Column(PG_UUID(as_uuid=True), nullable=True)
    nombre = Column(String(80), nullable=False)
    apellido = Column(String(80), nullable=False)
    telefono = Column(String(50), nullable=True) 
    email = Column(CITEXT, nullable=True)  # ✅ Ahora es NULL según DDL
    password_hash = Column(String, nullable=False)
    usuario = Column(String(20), nullable=False)  # ✅ Ahora es NOT NULL según DDL
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)  # ✅ Campo faltante
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)  # ✅ Campo faltante
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

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class UsuarioBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Usuario.
    """
    nombre: str
    apellido: str
    telefono: Optional[str] = None  # ✅ Teléfono es opcional según DDL
    email: Optional[EmailStr] = None  # ✅ Email ahora es opcional según DDL
    usuario: str  # ✅ Usuario ahora es obligatorio según DDL
    id_rol: Optional[UUID] = None

class UsuarioCreate(UsuarioBase):
    """Esquema para creación; incluye password en texto plano."""
    password: str  # Contraseña en texto plano (se hasheará automáticamente)

class UsuarioUpdate(BaseModel):
    """
    Esquema para actualización con todos los campos opcionales.
    Solo se actualizarán los campos que se proporcionen.
    """
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None  # Teléfono es opcional
    email: Optional[EmailStr] = None
    usuario: Optional[str] = None
    id_rol: Optional[UUID] = None
    password: Optional[str] = None  # Contraseña en texto plano (se hasheará automáticamente)

class UsuarioRead(UsuarioBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    NUNCA incluye password_hash por seguridad.
    """
    id_usuario: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class LoginRequest(BaseModel):
    """
    Esquema para solicitud de login.
    Busca ÚNICAMENTE por el campo 'usuario' (no por email).
    """
    usuario: str  # Campo 'usuario' de la tabla (no email)
    password: str

class LoginResponse(BaseModel):
    """
    Esquema para respuesta de login exitoso.
    """
    success: bool
    message: str
    usuario: UsuarioRead

class PasswordChangeRequest(BaseModel):
    """
    Esquema para cambio de contraseña.
    """
    password_actual: str
    password_nueva: str

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_usuarios(
    nombre: Optional[str] = Query(None),        # Filtro por nombre (ilike)
    apellido: Optional[str] = Query(None),      # Filtro por apellido (ilike)
    telefono: Optional[str] = Query(None),      # Filtro por teléfono (ilike)
    email: Optional[str] = Query(None),         # Filtro por email (ilike)
    usuario: Optional[str] = Query(None),       # Filtro por usuario (ilike)
    skip: int = 0,                              # Paginación: offset
    limit: int = 100,                           # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)    # Sesión RLS inyectada
):
    """
    Lista usuarios en estado "activo" con paginación y filtros opcionales.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta con filtros
    stmt = select(Usuario).where(Usuario.id_estado == estado_activo_id)
    if nombre:
        stmt = stmt.where(Usuario.nombre.ilike(f"%{nombre}%"))
    if apellido:
        stmt = stmt.where(Usuario.apellido.ilike(f"%{apellido}%"))
    if telefono:
        stmt = stmt.where(Usuario.telefono.ilike(f"%{telefono}%"))
    if email:
        stmt = stmt.where(Usuario.email.ilike(f"%{email}%"))
    if usuario:
        stmt = stmt.where(Usuario.usuario.ilike(f"%{usuario}%"))

    # 3) Contar total para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Serializar y devolver
    return {
        "success": True,
        "total_count": total,
        "data": [UsuarioRead.model_validate(u) for u in data]
    }

@router.get("/{id_usuario}", response_model=UsuarioRead)
async def obtener_usuario(
    id_usuario: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un usuario por su ID, sólo si está en estado "activo".
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Consulta con filtros de ID y estado
    stmt = select(Usuario).where(
        Usuario.id_usuario == id_usuario,
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario = result.scalar_one_or_none()

    # 3) Si no existe o no está activo, devolver 404
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 4) Retornar serializado
    return UsuarioRead.model_validate(usuario)

@router.post("/", response_model=dict, status_code=201)
async def crear_usuario(
    entrada: UsuarioCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo usuario. La contraseña se hashea automáticamente.
    Aplica RLS y defaults de servidor.
    """
    # 1) Recuperar tenant y usuario del contexto RLS
    ctx = await obtener_contexto(db)   

    # 3) Verificar que el usuario no esté duplicado (ahora es obligatorio)
    usuario_check = await db.execute(
        select(Usuario).where(
            Usuario.usuario == entrada.usuario,
            Usuario.id_empresa == ctx["tenant_id"],
            Usuario.id_estado == await get_estado_id_por_clave("act", db)
        )
    )
    if usuario_check.scalar_one_or_none():
        raise HTTPException(
            status_code=409, 
            detail="Ya existe un usuario con ese nombre de usuario en la empresa"
        )

    # 4) Hashear contraseña usando función de PostgreSQL
    password_hash_result = await db.execute(
        select(func.hash_password(entrada.password))
    )
    password_hash = password_hash_result.scalar()

    # 5) Construir instancia ORM
    nuevo = Usuario(
        nombre=entrada.nombre,
        apellido=entrada.apellido,
        telefono=entrada.telefono,  # ✅ Teléfono es opcional
        email=entrada.email,
        usuario=entrada.usuario,
        password_hash=password_hash,
        id_rol=entrada.id_rol,
        id_empresa=ctx["tenant_id"],
        created_by=ctx["user_id"],  # ✅ Campo obligatorio
        modified_by=ctx["user_id"]  # ✅ Campo obligatorio
    )
    db.add(nuevo)

    # 6) Insert + Refresh
    try:
        await db.flush()
        await db.refresh(nuevo)
        await db.commit()

        # 7) Devolver datos completos (sin password_hash)
        return {"success": True, "data": UsuarioRead.model_validate(nuevo)}
    
    except Exception as e:
        await db.rollback()
        if "uq_usuario_empresa_email_ci" in str(e):
            raise HTTPException(
                status_code=409, 
                detail="Ya existe un usuario con ese email en la empresa"
            )
        elif "uq_usuario_empresa_usuario_ci" in str(e):  # ✅ Constraint que ahora SÍ existe
            raise HTTPException(
                status_code=409, 
                detail="Ya existe un usuario con ese nombre de usuario en la empresa"
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

@router.put("/{id_usuario}", response_model=dict)
async def actualizar_usuario(
    id_usuario: UUID,
    entrada: UsuarioUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un usuario en estado "activo".
    Si se proporciona password, se hashea automáticamente.
    """
    # 1) UUID de estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Carga sólo si existe y está activo
    stmt = select(Usuario).where(
        Usuario.id_usuario == id_usuario,
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario = result.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 3) Aplicar cambios
    ctx = await obtener_contexto(db)
    
    if entrada.nombre is not None:
        usuario.nombre = entrada.nombre
    if entrada.apellido is not None:
        usuario.apellido = entrada.apellido
    if entrada.telefono is not None:
        usuario.telefono = entrada.telefono
    if entrada.email is not None:       
        usuario.email = entrada.email
    
    if entrada.usuario is not None:
        # Verificar usuario duplicado
        usuario_check = await db.execute(
            select(Usuario).where(
                Usuario.usuario == entrada.usuario,
                Usuario.id_empresa == ctx["tenant_id"],
                Usuario.id_usuario != id_usuario,
                Usuario.id_estado == await get_estado_id_por_clave("act", db)
            )
        )
        if usuario_check.scalar_one_or_none():
            raise HTTPException(
                status_code=409, 
                detail="Ya existe otro usuario con ese nombre de usuario en la empresa"
            )
        usuario.usuario = entrada.usuario
    
    if entrada.id_rol is not None:
        usuario.id_rol = entrada.id_rol
    
    # 4) Manejo especial de contraseña
    if entrada.password is not None:
        password_hash_result = await db.execute(
            select(func.hash_password(entrada.password))
        )
        usuario.password_hash = password_hash_result.scalar()

    # 5) Actualizar auditoría
    usuario.modified_by = ctx["user_id"]

    # 6) Flush + Refresh
    try:
        await db.flush()
        await db.refresh(usuario)
        await db.commit()

        return {"success": True, "data": UsuarioRead.model_validate(usuario)}
    
    except Exception as e:
        await db.rollback()
        if "uq_usuario_empresa_email_ci" in str(e):
            raise HTTPException(
                status_code=409, 
                detail="Ya existe otro usuario con ese email en la empresa"
            )
        elif "uq_usuario_empresa_usuario_ci" in str(e):  # ✅ Constraint que ahora SÍ existe
            raise HTTPException(
                status_code=409, 
                detail="Ya existe otro usuario con ese nombre de usuario en la empresa"
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

@router.delete("/{id_usuario}", status_code=200)
async def eliminar_usuario(
    id_usuario: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un usuario. Se respetan políticas RLS.
    """
    # 1) Verificar existencia bajo RLS
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id_usuario))
    usuario = result.scalar_one_or_none()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 2) Ejecutar DELETE
    await db.execute(delete(Usuario).where(Usuario.id_usuario == id_usuario))
    await db.commit()

    # 3) Responder al cliente
    return {"success": True, "message": "Usuario eliminado permanentemente"}

# ==============================================
# ENDPOINTS ESPECIALES PARA AUTENTICACIÓN
# ==============================================

@router.post("/login", response_model=LoginResponse)
async def validar_usuario(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Valida credenciales de usuario (usuario + password).
    Busca ÚNICAMENTE por el campo 'usuario', NO por email.
    Retorna información del usuario si las credenciales son correctas.
    """
    # 1) Buscar usuario SOLO por campo 'usuario' en estado activo
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Usuario).where(
        Usuario.usuario == credentials.usuario,
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario = result.scalar_one_or_none()

    # 2) Si no existe usuario con ese nombre de usuario
    if not usuario:
        raise HTTPException(
            status_code=401, 
            detail="Credenciales inválidas"
        )

    # 3) Verificar contraseña usando función de PostgreSQL
    password_valid_result = await db.execute(
        select(func.verify_password(credentials.password, usuario.password_hash))
    )
    password_valid = password_valid_result.scalar()

    # 4) Si la contraseña no es válida
    if not password_valid:
        raise HTTPException(
            status_code=401, 
            detail="Credenciales inválidas"
        )

    # 5) Login exitoso
    return LoginResponse(
        success=True,
        message="Login exitoso",
        usuario=UsuarioRead.model_validate(usuario)
    )

@router.put("/{id_usuario}/password", response_model=dict)
async def cambiar_password(
    id_usuario: UUID,
    request: PasswordChangeRequest,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Cambia la contraseña de un usuario específico.
    Requiere la contraseña actual para validación.
    """
    # 1) Buscar usuario
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Usuario).where(
        Usuario.id_usuario == id_usuario,
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario = result.scalar_one_or_none()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # 2) Verificar contraseña actual
    password_valid_result = await db.execute(
        select(func.verify_password(request.password_actual, usuario.password_hash))
    )
    password_valid = password_valid_result.scalar()

    if not password_valid:
        raise HTTPException(
            status_code=401, 
            detail="Contraseña actual incorrecta"
        )

    # 3) Hashear nueva contraseña
    new_password_hash_result = await db.execute(
        select(func.hash_password(request.password_nueva))
    )
    new_password_hash = new_password_hash_result.scalar()

    # 4) Actualizar contraseña
    ctx = await obtener_contexto(db)
    usuario.password_hash = new_password_hash
    usuario.modified_by = ctx["user_id"]
    
    await db.flush()
    await db.commit()

    return {
        "success": True, 
        "message": "Contraseña actualizada correctamente"
    }

@router.get("/username/{usuario}/exists", response_model=dict)
async def verificar_disponibilidad_usuario(
    usuario: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Verifica si un nombre de usuario está disponible.
    Útil para validar duplicados antes de crear/actualizar usuarios.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Usuario).where(
        Usuario.usuario == usuario,
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario_encontrado = result.scalar_one_or_none()

    if usuario_encontrado:
        return {
            "success": False,
            "message": "Nombre de usuario no disponible",
            "available": False
        }
    
    return {
        "success": True,
        "message": "Nombre de usuario disponible",
        "available": True
    }

@router.get("/email/{email}", response_model=dict)
async def buscar_usuario_por_email(
    email: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Busca un usuario por su email.
    Útil para verificar si un email ya está registrado.
    Nota: El email ahora es opcional en la tabla.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    stmt = select(Usuario).where(
        Usuario.email == email,
        Usuario.email.is_not(None),  # ✅ Excluir registros con email NULL
        Usuario.id_estado == estado_activo_id
    )
    result = await db.execute(stmt)
    usuario_encontrado = result.scalar_one_or_none()

    if not usuario_encontrado:
        return {
            "success": False,
            "message": "Usuario no encontrado",
            "exists": False
        }
    
    return {
        "success": True,
        "message": "Usuario encontrado",
        "exists": True,
        "data": UsuarioRead.model_validate(usuario_encontrado)
    }

@router.get("/rol/{id_rol}", response_model=dict)
async def listar_usuarios_por_rol(
    id_rol: UUID,
    skip: int = 0,                              # Paginación: offset
    limit: int = 100,                           # Paginación: máximo de registros
    db: AsyncSession = Depends(get_async_db)    # Sesión RLS inyectada
):
    """
    Lista usuarios que pertenecen a un rol específico.
    Solo incluye usuarios en estado "activo" con paginación.
    """
    # 1) Obtener UUID del estado "activo"
    estado_activo_id = await get_estado_id_por_clave("act", db)

    # 2) Construir consulta filtrada por id_rol y estado activo
    stmt = select(Usuario).where(
        Usuario.id_rol == id_rol,
        Usuario.id_estado == estado_activo_id
    )

    # 3) Contar total para paginación
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    # 4) Ejecutar consulta paginada
    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    # 5) Serializar y devolver
    return {
        "success": True,
        "total_count": total,
        "id_rol": id_rol,
        "data": [UsuarioRead.model_validate(u) for u in data]
    }