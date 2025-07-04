# cliente.py
# -------------------------------------------------------
# Endpoints REST para la tabla "cliente" con relaciones
# Entidad → Municipio → Localidad (vía claves INEGI)     
# -------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, ForeignKey, select, func, text, DateTime, and_
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, get_async_db
from utils.estado import get_estado_id_por_clave
from utils.contexto import obtener_contexto
from entidad import Entidad
from municipio import Municipio, Localidad, LocalidadRead

# ---------------------------
# Modelos ORM
# ---------------------------
class Cliente(Base):
    __tablename__ = "cliente"

    id_cliente  = Column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    id_empresa  = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("current_setting('app.current_tenant'::text)::uuid"))
    id_estado   = Column(PG_UUID(as_uuid=True), nullable=False, server_default=text("f_default_estatus_activo()"))

    nombre       = Column(String(120), nullable=False)
    apellido     = Column(String(120))
    razon_social = Column(String(255))
    rfc          = Column(String)
    email        = Column(String)
    telefono     = Column(String(30))
    domicilio    = Column(Text)
    colonia      = Column(String(100))
    cp           = Column(String(20))
    municipio    = Column(String(100))  # Texto descriptivo, no FK
    guid         = Column(String(36))
    clave        = Column(String(50))

    # Claves INEGI
    cve_ent = Column(String(2))
    cve_mun = Column(String(4))
    cve_loc = Column(String(5))

    created_by  = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

# ---------------------------
# Schemas Pydantic (versión slim para evitar cargas perezosas)
# ---------------------------
class EntidadSlim(BaseModel):
    cvegeo: str
    nomgeo: str
    
    model_config = {"from_attributes": True}

class MunicipioSlim(BaseModel):
    cvegeo: str
    nomgeo: str

    model_config = {"from_attributes": True}

class ClienteBase(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    domicilio: Optional[str] = None
    colonia: Optional[str] = None
    cp: Optional[str] = None
    municipio: Optional[str] = None
    guid: Optional[str] = None
    clave: Optional[str] = None
    cve_ent: Optional[str] = None
    cve_mun: Optional[str] = None
    cve_loc: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(ClienteBase):
    pass

class ClienteRead(ClienteBase):
    id_cliente: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    entidad: Optional[EntidadSlim] = None
    municipio_obj: Optional[MunicipioSlim] = None
    localidad: Optional[LocalidadRead] = None

    model_config = {"from_attributes": True}

# ---------------------------
# Router y utilidades
# ---------------------------
router = APIRouter(prefix="/clientes", tags=["Clientes"])

async def _cargar_relaciones(cli: Cliente, db: AsyncSession):
    # Entidad
    if cli.cve_ent:
        ent = await db.scalar(select(Entidad).where(Entidad.cvegeo == cli.cve_ent))
        if ent:
            cli.entidad = ent  # convertido a EntidadSlim automáticamente

    # Municipio
    if cli.cve_ent and cli.cve_mun:
        muni = await db.scalar(select(Municipio).where(and_(Municipio.cve_ent == cli.cve_ent, Municipio.cve_mun == cli.cve_mun)))
        if muni:
            cli.municipio_obj = muni  # convertido a MunicipioSlim

    # Localidad
    if cli.cve_ent and cli.cve_mun and cli.cve_loc:
        loc = await db.scalar(select(Localidad).where(and_(Localidad.cve_ent == cli.cve_ent, Localidad.cve_mun == cli.cve_mun, Localidad.cve_loc == cli.cve_loc)))
        cli.localidad = loc

# ---------------------------
# Endpoints
# ---------------------------
@router.get("/", response_model=dict)
async def listar_clientes(nombre: Optional[str] = Query(None), skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_db)):
    estado_activo = await get_estado_id_por_clave("act", db)
    stmt = select(Cliente).where(Cliente.id_estado == estado_activo)
    if nombre:
        stmt = stmt.where(Cliente.nombre.ilike(f"%{nombre}%"))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    for cli in items:
        await _cargar_relaciones(cli, db)

    return {"success": True, "total_count": total, "data": [ClienteRead.model_validate(c) for c in items]}

@router.get("/{id_cliente}", response_model=ClienteRead)
async def obtener_cliente(id_cliente: UUID, db: AsyncSession = Depends(get_async_db)):
    estado_activo = await get_estado_id_por_clave("act", db)
    cli = await db.scalar(select(Cliente).where(Cliente.id_cliente == id_cliente, Cliente.id_estado == estado_activo))
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await _cargar_relaciones(cli, db)
    return ClienteRead.model_validate(cli)

@router.post("/", response_model=dict, status_code=201)
async def crear_cliente(datos: ClienteCreate, db: AsyncSession = Depends(get_async_db)):
    ctx = await obtener_contexto(db)
    nuevo = Cliente(**datos.dict(exclude_unset=True), created_by=ctx['user_id'], modified_by=ctx['user_id'], id_empresa=ctx['tenant_id'])
    db.add(nuevo)
    await db.flush()
    await _cargar_relaciones(nuevo, db)
    await db.commit()
    return {"success": True, "data": ClienteRead.model_validate(nuevo)}

@router.put("/{id_cliente}", response_model=dict)
async def actualizar_cliente(id_cliente: UUID, cambios: ClienteUpdate, db: AsyncSession = Depends(get_async_db)):
    estado_activo = await get_estado_id_por_clave("act", db)
    cli = await db.scalar(select(Cliente).where(Cliente.id_cliente == id_cliente, Cliente.id_estado == estado_activo))
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    for k, v in cambios.dict(exclude_unset=True).items():
        setattr(cli, k, v)
    cli.modified_by = (await obtener_contexto(db))['user_id']

    await db.flush()
    await _cargar_relaciones(cli, db)
    await db.commit()
    return {"success": True, "data": ClienteRead.model_validate(cli)}

@router.delete("/{id_cliente}", status_code=200)
async def borrar_cliente(id_cliente: UUID, db: AsyncSession = Depends(get_async_db)):
    estado_activo = await get_estado_id_por_clave("act", db)
    cli = await db.scalar(select(Cliente).where(Cliente.id_cliente == id_cliente, Cliente.id_estado == estado_activo))
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await db.delete(cli)
    await db.commit()
    return {"success": True, "message": "Cliente eliminado permanentemente"}
