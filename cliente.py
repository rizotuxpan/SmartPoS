# cliente.py - VERSIÓN CORREGIDA PARA SQLALCHEMY 2.x
# ---------------------------
# Módulo de endpoints REST para gestión de la entidad Cliente.
# Incluye objetos relacionados completos y filtros avanzados
# VERSIÓN SIMPLIFICADA: Siempre retorna objetos expandidos

from fastapi import APIRouter, Depends, HTTPException, Query    # FastAPI para rutas y dependencias
from pydantic import BaseModel, model_validator, EmailStr      # Pydantic para schemas de entrada/salida
from typing import Optional                                     # Tipos para anotaciones
from uuid import UUID                                           # UUID para identificadores únicos
from datetime import datetime                                   # Fecha y hora
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, CHAR,
    func, select, text, delete, and_, or_, cast
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, CITEXT  # Tipos PostgreSQL específicos
from sqlalchemy.ext.asyncio import AsyncSession                 # Sesión asíncrona de SQLAlchemy

# Importa base de modelos y función de sesión configurada con RLS
from db import Base, engine, get_async_db
# Utilidad para resolver claves de estado con caché
from utils.estado import get_estado_id_por_clave
# Utilidad para extraer tenant y usuario desde la sesión (RLS)
from utils.contexto import obtener_contexto  # IMPORTANTE

# ===== IMPORTAR MODELOS Y ESQUEMAS RELACIONADOS =====
from geografia import Entidad, Municipio, Localidad
from regimenfiscal import RegimenFiscal

# --------------------------------------
# Definición del modelo ORM (SQLAlchemy)
# --------------------------------------
class Cliente(Base):
    __tablename__ = "cliente"
    id_cliente      = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    id_empresa      = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("current_setting('app.current_tenant'::text)::uuid")
    )
    id_estado       = Column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text("f_default_estatus_activo()")
    )
    nombre          = Column(String(120), nullable=False)
    apellido        = Column(String(120))
    razon_social    = Column(String(255))
    rfc             = Column(CITEXT)
    email           = Column(CITEXT)
    telefono        = Column(String(30))
    domicilio       = Column(Text)
    cp              = Column(String(20))
    cve_ent         = Column(CHAR(2))
    cve_mun         = Column(String(4))
    cve_loc         = Column(String(5))
    id_regimenfiscal = Column(String(3), nullable=False, server_default=text("'616'"))
    created_by      = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by     = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at      = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at      = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

# ----------------------------------
# Schemas de validación con Pydantic
# ----------------------------------
class ClienteBase(BaseModel):
    """
    Esquema base con campos comunes para crear/actualizar Cliente.
    """
    nombre: str
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    email: Optional[str] = None  # Usar str en lugar de EmailStr para flexibilidad
    telefono: Optional[str] = None
    domicilio: Optional[str] = None
    cp: Optional[str] = None
    cve_ent: Optional[str] = None
    cve_mun: Optional[str] = None
    cve_loc: Optional[str] = None
    id_regimenfiscal: Optional[str] = None

class ClienteCreate(ClienteBase):
    """Esquema para creación; hereda todos los campos base."""
    pass

class ClienteUpdate(BaseModel):
    """
    Esquema para actualización con todos los campos opcionales.
    Solo se actualizarán los campos que se proporcionen.
    """
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    domicilio: Optional[str] = None
    cp: Optional[str] = None
    cve_ent: Optional[str] = None
    cve_mun: Optional[str] = None
    cve_loc: Optional[str] = None
    id_regimenfiscal: Optional[str] = None
    
    # Validador personalizado para ubicación geográfica
    @model_validator(mode='after')
    def validate_ubicacion_geografica(self):
        # Si se proporciona localidad, debe haber municipio y entidad
        if self.cve_loc is not None:
            if self.cve_mun is None or self.cve_ent is None:
                raise ValueError("Si se proporciona localidad, debe incluir municipio y entidad")
        
        # Si se proporciona municipio, debe haber entidad
        elif self.cve_mun is not None:
            if self.cve_ent is None:
                raise ValueError("Si se proporciona municipio, debe incluir entidad")
        
        return self

class ClienteRead(ClienteBase):
    """
    Esquema de lectura (salida) con atributos del modelo ORM.
    """
    id_cliente: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# ===== ESQUEMAS PARA ENTIDADES GEOGRÁFICAS =====
class EntidadRead(BaseModel):
    cve_ent: str
    nomgeo: str
    model_config = {"from_attributes": True}

class MunicipioRead(BaseModel):
    cve_ent: str
    cve_mun: str
    nomgeo: str
    model_config = {"from_attributes": True}

class LocalidadRead(BaseModel):
    cve_ent: str
    cve_mun: str
    cve_loc: str
    nomgeo: str
    model_config = {"from_attributes": True}

# ===== ESQUEMA PARA RÉGIMEN FISCAL =====
class RegimenFiscalRead(BaseModel):
    id_regimenfiscal: str
    nombre: str
    id_empresa: UUID
    id_estado: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    modified_by: UUID
    model_config = {"from_attributes": True}

# ===== ESQUEMA EXPANDIDO =====
class ClienteReadExpanded(ClienteBase):
    """
    Esquema de lectura expandido con objetos relacionados completos.
    """
    id_cliente: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime
    
    # Objetos relacionados completos
    entidad: Optional[EntidadRead] = None
    municipio_obj: Optional[MunicipioRead] = None  # Usar municipio_obj para evitar conflicto
    localidad: Optional[LocalidadRead] = None
    regimen_fiscal: Optional[RegimenFiscalRead] = None
    
    model_config = {"from_attributes": True}

# ---------------------------
# Definición del router y endpoints
# ---------------------------
router = APIRouter()

@router.get("/", response_model=dict)
async def listar_clientes(
    # ===== FILTROS BÁSICOS =====
    nombre: Optional[str] = Query(None, description="Filtro por nombre del cliente"),
    apellido: Optional[str] = Query(None, description="Filtro por apellido del cliente"),
    razon_social: Optional[str] = Query(None, description="Filtro por razón social"),
    rfc: Optional[str] = Query(None, description="Filtro por RFC"),
    telefono: Optional[str] = Query(None, description="Filtro por teléfono"),
    email: Optional[str] = Query(None, description="Filtro por email"),
    domicilio: Optional[str] = Query(None, description="Filtro por domicilio"),
    cp: Optional[str] = Query(None, description="Filtro por código postal"),
    
    # ===== FILTROS POR NOMBRES DE ENTIDADES RELACIONADAS =====
    entidad_nombre: Optional[str] = Query(None, description="Filtro por nombre de entidad"),
    municipio_nombre: Optional[str] = Query(None, description="Filtro por nombre de municipio"),
    localidad_nombre: Optional[str] = Query(None, description="Filtro por nombre de localidad"),
    regimen_fiscal_nombre: Optional[str] = Query(None, description="Filtro por nombre de régimen fiscal"),
    
    # ===== PARÁMETROS DE PAGINACIÓN =====
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(100, ge=1, le=1000, description="Número máximo de registros a retornar"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista clientes en estado "activo" con paginación, filtros opcionales extendidos
    y objetos relacionados completos.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # ===== CONSULTA CON JOINS PARA OBJETOS RELACIONADOS =====
    # Crear query base
    query = select(
        Cliente,
        Entidad,
        Municipio,
        Localidad,
        RegimenFiscal
    )
    
    # Especificar FROM explícitamente para SQLAlchemy 2.x
    query = query.select_from(
        Cliente.__table__
        .outerjoin(
            Entidad.__table__,
            Cliente.cve_ent == Entidad.cve_ent
        )
        .outerjoin(
            Municipio.__table__,
            and_(
                Cliente.cve_ent == Municipio.cve_ent,
                Cliente.cve_mun == Municipio.cve_mun
            )
        )
        .outerjoin(
            Localidad.__table__,
            and_(
                Cliente.cve_ent == Localidad.cve_ent,
                Cliente.cve_mun == Localidad.cve_mun,
                Cliente.cve_loc == Localidad.cve_loc
            )
        )
        .outerjoin(
            RegimenFiscal.__table__,
            Cliente.id_regimenfiscal == RegimenFiscal.id_regimenfiscal
        )
    )
    
    # Filtro base
    query = query.where(Cliente.id_estado == estado_activo_id)
    
    # ===== APLICAR FILTROS BÁSICOS =====
    if nombre:
        query = query.where(Cliente.nombre.ilike(f"%{nombre}%"))
    if apellido:
        query = query.where(Cliente.apellido.ilike(f"%{apellido}%"))
    if razon_social:
        query = query.where(Cliente.razon_social.ilike(f"%{razon_social}%"))
    if rfc:
        query = query.where(Cliente.rfc.ilike(f"%{rfc}%"))
    if telefono:
        query = query.where(Cliente.telefono.ilike(f"%{telefono}%"))
    if email:
        query = query.where(Cliente.email.ilike(f"%{email}%"))
    if domicilio:
        query = query.where(Cliente.domicilio.ilike(f"%{domicilio}%"))
    if cp:
        query = query.where(Cliente.cp.ilike(f"%{cp}%"))
    
    # ===== APLICAR FILTROS DE ENTIDADES RELACIONADAS =====
    if entidad_nombre:
        query = query.where(Entidad.nomgeo.ilike(f"%{entidad_nombre}%"))
    if municipio_nombre:
        query = query.where(Municipio.nomgeo.ilike(f"%{municipio_nombre}%"))
    if localidad_nombre:
        query = query.where(Localidad.nomgeo.ilike(f"%{localidad_nombre}%"))
    if regimen_fiscal_nombre:
        query = query.where(RegimenFiscal.nombre.ilike(f"%{regimen_fiscal_nombre}%"))
    
    # ===== CONTAR TOTAL PARA PAGINACIÓN =====
    count_query = select(func.count(Cliente.id_cliente)).select_from(
        Cliente.__table__
        .outerjoin(
            Entidad.__table__,
            Cliente.cve_ent == Entidad.cve_ent
        )
        .outerjoin(
            Municipio.__table__,
            and_(
                Cliente.cve_ent == Municipio.cve_ent,
                Cliente.cve_mun == Municipio.cve_mun
            )
        )
        .outerjoin(
            Localidad.__table__,
            and_(
                Cliente.cve_ent == Localidad.cve_ent,
                Cliente.cve_mun == Localidad.cve_mun,
                Cliente.cve_loc == Localidad.cve_loc
            )
        )
        .outerjoin(
            RegimenFiscal.__table__,
            Cliente.id_regimenfiscal == RegimenFiscal.id_regimenfiscal
        )
    ).where(Cliente.id_estado == estado_activo_id)
    
    # Aplicar los mismos filtros al count
    if nombre:
        count_query = count_query.where(Cliente.nombre.ilike(f"%{nombre}%"))
    if apellido:
        count_query = count_query.where(Cliente.apellido.ilike(f"%{apellido}%"))
    if razon_social:
        count_query = count_query.where(Cliente.razon_social.ilike(f"%{razon_social}%"))
    if rfc:
        count_query = count_query.where(Cliente.rfc.ilike(f"%{rfc}%"))
    if telefono:
        count_query = count_query.where(Cliente.telefono.ilike(f"%{telefono}%"))
    if email:
        count_query = count_query.where(Cliente.email.ilike(f"%{email}%"))
    if domicilio:
        count_query = count_query.where(Cliente.domicilio.ilike(f"%{domicilio}%"))
    if cp:
        count_query = count_query.where(Cliente.cp.ilike(f"%{cp}%"))
    if entidad_nombre:
        count_query = count_query.where(Entidad.nomgeo.ilike(f"%{entidad_nombre}%"))
    if municipio_nombre:
        count_query = count_query.where(Municipio.nomgeo.ilike(f"%{municipio_nombre}%"))
    if localidad_nombre:
        count_query = count_query.where(Localidad.nomgeo.ilike(f"%{localidad_nombre}%"))
    if regimen_fiscal_nombre:
        count_query = count_query.where(RegimenFiscal.nombre.ilike(f"%{regimen_fiscal_nombre}%"))
    
    total = await db.scalar(count_query)
    
    # Ejecutar consulta paginada
    result = await db.execute(query.offset(skip).limit(limit))
    
    # ===== CONSTRUIR RESPUESTA EXPANDIDA =====
    data = []
    for row in result:
        cliente_obj   = row[0]    # Objeto Cliente
        entidad_obj   = row[1]    # Objeto Entidad (puede ser None)
        municipio_obj = row[2]    # Objeto Municipio (puede ser None)
        localidad_obj = row[3]    # Objeto Localidad (puede ser None)
        regimen_obj   = row[4]    # Objeto RegimenFiscal (puede ser None)
        
        # Convertir cliente base
        cliente_dict = ClienteRead.model_validate(cliente_obj).model_dump()
        
        # Agregar objetos relacionados si existen
        cliente_dict['entidad'] = EntidadRead.model_validate(entidad_obj).model_dump() if entidad_obj else None
        cliente_dict['municipio_obj'] = MunicipioRead.model_validate(municipio_obj).model_dump() if municipio_obj else None
        cliente_dict['localidad'] = LocalidadRead.model_validate(localidad_obj).model_dump() if localidad_obj else None
        cliente_dict['regimen_fiscal'] = RegimenFiscalRead.model_validate(regimen_obj).model_dump() if regimen_obj else None
        
        data.append(cliente_dict)

    return {
        "success": True,
        "total_count": total,
        "filtros_aplicados": {
            "basicos": {
                "nombre": nombre,
                "apellido": apellido,
                "razon_social": razon_social,
                "rfc": rfc,
                "telefono": telefono,
                "email": email,
                "domicilio": domicilio,
                "cp": cp
            },
            "entidades": {
                "entidad_nombre": entidad_nombre,
                "municipio_nombre": municipio_nombre,
                "localidad_nombre": localidad_nombre,
                "regimen_fiscal_nombre": regimen_fiscal_nombre
            }
        },
        "paginacion": {
            "skip": skip,
            "limit": limit,
            "total": total,
            "pagina_actual": (skip // limit) + 1,
            "total_paginas": ((total - 1) // limit) + 1 if total > 0 else 0
        },
        "data": data
    }

@router.get("/{id_cliente}", response_model=dict)
async def obtener_cliente(
    id_cliente: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene un cliente por su ID con objetos relacionados completos.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Consulta con joins usando tabla base
    query = select(
        Cliente,
        Entidad,
        Municipio,
        Localidad,
        RegimenFiscal
    ).select_from(
        Cliente.__table__
        .outerjoin(
            Entidad.__table__,
            Cliente.cve_ent == Entidad.cve_ent
        )
        .outerjoin(
            Municipio.__table__,
            and_(
                Cliente.cve_ent == Municipio.cve_ent,
                Cliente.cve_mun == Municipio.cve_mun
            )
        )
        .outerjoin(
            Localidad.__table__,
            and_(
                Cliente.cve_ent == Localidad.cve_ent,
                Cliente.cve_mun == Localidad.cve_mun,
                Cliente.cve_loc == Localidad.cve_loc
            )
        )
        .outerjoin(
            RegimenFiscal.__table__,
            Cliente.id_regimenfiscal == RegimenFiscal.id_regimenfiscal
        )
    ).where(
        Cliente.id_cliente == id_cliente,
        Cliente.id_estado == estado_activo_id
    )
    
    result = await db.execute(query)
    row = result.first()
    
    if not row:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Construir respuesta expandida
    cliente_obj = row[0]
    entidad_obj = row[1]
    municipio_obj = row[2]
    localidad_obj = row[3]
    regimen_obj = row[4]
    
    cliente_dict = ClienteRead.model_validate(cliente_obj).model_dump()
    
    cliente_dict['entidad'] = EntidadRead.model_validate(entidad_obj).model_dump() if entidad_obj else None
    cliente_dict['municipio_obj'] = MunicipioRead.model_validate(municipio_obj).model_dump() if municipio_obj else None
    cliente_dict['localidad'] = LocalidadRead.model_validate(localidad_obj).model_dump() if localidad_obj else None
    cliente_dict['regimen_fiscal'] = RegimenFiscalRead.model_validate(regimen_obj).model_dump() if regimen_obj else None
    
    return {
        "success": True,
        "data": cliente_dict
    }

@router.post("/", response_model=dict, status_code=201)
async def crear_cliente(
    entrada: ClienteCreate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Crea un nuevo cliente. Aplica RLS y defaults de servidor.
    """
    ctx = await obtener_contexto(db)
    
    # ===== VALIDACIÓN DE UBICACIÓN GEOGRÁFICA =====
    if entrada.cve_loc is not None:
        # Verificar que la localidad existe
        localidad_query = select(Localidad).where(
            Localidad.cve_ent == entrada.cve_ent,
            Localidad.cve_mun == entrada.cve_mun,
            Localidad.cve_loc == entrada.cve_loc
        )
        localidad_result = await db.execute(localidad_query)
        localidad = localidad_result.scalar_one_or_none()
        
        if not localidad:
            raise HTTPException(
                status_code=400, 
                detail="La combinación entidad-municipio-localidad no existe"
            )
    
    elif entrada.cve_mun is not None:
        # Verificar que el municipio existe
        municipio_query = select(Municipio).where(
            Municipio.cve_ent == entrada.cve_ent,
            Municipio.cve_mun == entrada.cve_mun
        )
        municipio_result = await db.execute(municipio_query)
        municipio = municipio_result.scalar_one_or_none()
        
        if not municipio:
            raise HTTPException(
                status_code=400, 
                detail="La combinación entidad-municipio no existe"
            )
    
    elif entrada.cve_ent is not None:
        # Verificar que la entidad existe
        entidad_query = select(Entidad).where(Entidad.cve_ent == entrada.cve_ent)
        entidad_result = await db.execute(entidad_query)
        entidad = entidad_result.scalar_one_or_none()
        
        if not entidad:
            raise HTTPException(status_code=400, detail="La entidad no existe")
    
    nuevo = Cliente(
        nombre           = entrada.nombre,
        apellido         = entrada.apellido,
        razon_social     = entrada.razon_social,
        rfc              = entrada.rfc,
        email            = entrada.email,
        telefono         = entrada.telefono,
        domicilio        = entrada.domicilio,
        cp               = entrada.cp,
        cve_ent          = entrada.cve_ent,
        cve_mun          = entrada.cve_mun,
        cve_loc          = entrada.cve_loc,
        id_regimenfiscal = entrada.id_regimenfiscal,
        created_by       = ctx["user_id"],
        modified_by      = ctx["user_id"],
        id_empresa       = ctx["tenant_id"]
    )
    
    try:
        db.add(nuevo)
        await db.flush()
        await db.refresh(nuevo)
        await db.commit()
        return {"success": True, "data": ClienteRead.model_validate(nuevo)}
    
    except Exception as e:
        await db.rollback()
        
        # Manejo específico de errores de constraint
        if "uq_cliente_empresa_email" in str(e):
            raise HTTPException(
                status_code=409, 
                detail="Ya existe un cliente con ese email en la empresa."
            )
        elif "fk_cliente_entidad_municipio_localidad" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="La ubicación geográfica especificada no es válida."
            )
        elif "fk_cliente_regimenfiscal" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="El régimen fiscal especificado no existe."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

@router.put("/{id_cliente}", response_model=dict)
async def actualizar_cliente(
    id_cliente: UUID,
    entrada: ClienteUpdate,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Actualiza datos de un cliente en estado "activo".
    Maneja correctamente las relaciones geográficas.
    """
    estado_activo_id = await get_estado_id_por_clave("act", db)
    
    # Buscar el cliente existente
    query = select(Cliente).where(
        Cliente.id_cliente == id_cliente,
        Cliente.id_estado == estado_activo_id
    )
    result = await db.execute(query)
    cliente = result.scalar_one_or_none()
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Obtener contexto del usuario
    ctx = await obtener_contexto(db)
    
    # ===== VALIDACIONES ESPECIALES PARA UBICACIÓN GEOGRÁFICA =====
    # Solo validar si al menos uno de los campos geográficos se proporciona
    if any([entrada.cve_ent, entrada.cve_mun, entrada.cve_loc]):
        # Usar valores del cliente existente como defaults si no se proporcionan
        cve_ent_final = entrada.cve_ent if entrada.cve_ent is not None else cliente.cve_ent
        cve_mun_final = entrada.cve_mun if entrada.cve_mun is not None else cliente.cve_mun
        cve_loc_final = entrada.cve_loc if entrada.cve_loc is not None else cliente.cve_loc
        
        # Si se proporciona localidad, validar toda la cadena
        if cve_loc_final is not None:
            if cve_mun_final is None or cve_ent_final is None:
                raise HTTPException(
                    status_code=400, 
                    detail="Si se proporciona localidad, debe incluir municipio y entidad"
                )
            
            localidad_query = select(Localidad).where(
                Localidad.cve_ent == cve_ent_final,
                Localidad.cve_mun == cve_mun_final,
                Localidad.cve_loc == cve_loc_final
            )
            localidad_result = await db.execute(localidad_query)
            localidad = localidad_result.scalar_one_or_none()
            
            if not localidad:
                raise HTTPException(
                    status_code=400, 
                    detail="La combinación entidad-municipio-localidad no existe"
                )
        
        # Si se proporciona municipio, validar
        elif cve_mun_final is not None:
            if cve_ent_final is None:
                raise HTTPException(
                    status_code=400, 
                    detail="Si se proporciona municipio, debe incluir entidad"
                )
            
            municipio_query = select(Municipio).where(
                Municipio.cve_ent == cve_ent_final,
                Municipio.cve_mun == cve_mun_final
            )
            municipio_result = await db.execute(municipio_query)
            municipio = municipio_result.scalar_one_or_none()
            
            if not municipio:
                raise HTTPException(
                    status_code=400, 
                    detail="La combinación entidad-municipio no existe"
                )
        
        # Si solo se proporciona entidad, validar
        elif cve_ent_final is not None:
            entidad_query = select(Entidad).where(Entidad.cve_ent == cve_ent_final)
            entidad_result = await db.execute(entidad_query)
            entidad = entidad_result.scalar_one_or_none()
            
            if not entidad:
                raise HTTPException(status_code=400, detail="La entidad no existe")
    
    # ===== ACTUALIZAR SOLO LOS CAMPOS PROPORCIONADOS =====
    
    # Campos básicos
    if entrada.nombre is not None:
        cliente.nombre = entrada.nombre
    if entrada.apellido is not None:
        cliente.apellido = entrada.apellido
    if entrada.razon_social is not None:
        cliente.razon_social = entrada.razon_social
    if entrada.rfc is not None:
        cliente.rfc = entrada.rfc
    if entrada.email is not None:
        cliente.email = entrada.email
    if entrada.telefono is not None:
        cliente.telefono = entrada.telefono
    if entrada.domicilio is not None:
        cliente.domicilio = entrada.domicilio
    if entrada.cp is not None:
        cliente.cp = entrada.cp
    
    # Campos geográficos
    if entrada.cve_ent is not None:
        cliente.cve_ent = entrada.cve_ent
    if entrada.cve_mun is not None:
        cliente.cve_mun = entrada.cve_mun
    if entrada.cve_loc is not None:
        cliente.cve_loc = entrada.cve_loc
    
    # Régimen fiscal
    if entrada.id_regimenfiscal is not None:
        cliente.id_regimenfiscal = entrada.id_regimenfiscal
    
    # Campos de auditoría
    cliente.modified_by = ctx["user_id"]
    
    try:
        await db.flush()
        await db.refresh(cliente)
        await db.commit()
        
        return {
            "success": True, 
            "message": "Cliente actualizado correctamente",
            "data": ClienteRead.model_validate(cliente).model_dump()
        }
        
    except Exception as e:
        await db.rollback()
        
        # Manejo específico de errores de constraint
        if "uq_cliente_empresa_email" in str(e):
            raise HTTPException(
                status_code=409, 
                detail="Ya existe un cliente con ese email en la empresa."
            )
        elif "fk_cliente_entidad_municipio_localidad" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="La ubicación geográfica especificada no es válida."
            )
        elif "fk_cliente_regimenfiscal" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="El régimen fiscal especificado no existe."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Error interno del servidor: {str(e)}"
            )

@router.delete("/{id_cliente}", status_code=200)
async def eliminar_cliente(
    id_cliente: UUID,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Elimina físicamente un cliente. Se respetan políticas RLS.
    """
    result = await db.execute(
        select(Cliente).where(Cliente.id_cliente == id_cliente)
    )
    cliente = result.scalar_one_or_none()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await db.execute(delete(Cliente).where(Cliente.id_cliente == id_cliente))
    await db.commit()
    return {"success": True, "message": "Cliente eliminado permanentemente"}