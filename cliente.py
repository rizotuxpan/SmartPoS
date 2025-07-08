# cliente.py
# ---------------------------
# Endpoints REST para gestión de clientes, adaptado desde producto.py funcional
# Incluye relaciones y filtros avanzados
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from db import get_async_db
from auth import get_current_user_id
import cliente as models
from regimenfiscal import RegimenFiscal
from geografia import Entidad, Municipio, Localidad

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# -----------------------------------
# Esquemas Pydantic
# -----------------------------------

class ClienteBase(BaseModel):
    nombre: str
    apellido: Optional[str]
    razon_social: Optional[str]
    rfc: Optional[str]
    email: Optional[EmailStr]
    telefono: Optional[str]
    domicilio: Optional[str]
    cp: Optional[str]
    municipio: Optional[str]
    clave: Optional[str]
    cve_ent: Optional[str]
    cve_mun: Optional[str]
    cve_loc: Optional[str]
    id_regimenfiscal: str

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(ClienteBase):
    pass

class ClienteOut(ClienteBase):
    id_cliente: UUID
    id_empresa: UUID
    id_estado: UUID
    created_by: UUID
    modified_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# -----------------------------------
# Listar clientes con filtros
# -----------------------------------
@router.get("/", response_model=dict)
async def listar_clientes(
    skip: int = 0,
    limit: int = 50,
    nombre: Optional[str] = Query(None),
    apellido: Optional[str] = Query(None),
    razon_social: Optional[str] = Query(None),
    rfc: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    telefono: Optional[str] = Query(None),
    domicilio: Optional[str] = Query(None),
    entidad: Optional[str] = Query(None),
    municipio: Optional[str] = Query(None),
    localidad: Optional[str] = Query(None),
    regimen_fiscal: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    stmt = (
        select(models.Cliente)
        .options(
            joinedload(models.Cliente.regimenfiscal),
            joinedload(models.Cliente.estado),
            joinedload(models.Cliente.localidad),
        )
        .order_by(models.Cliente.nombre)
        .offset(skip)
        .limit(limit)
    )

    if nombre:
        stmt = stmt.where(func.unaccent(func.lower(models.Cliente.nombre)).ilike(func.unaccent(f"%{nombre.lower()}%")))
    if apellido:
        stmt = stmt.where(func.unaccent(func.lower(models.Cliente.apellido)).ilike(func.unaccent(f"%{apellido.lower()}%")))
    if razon_social:
        stmt = stmt.where(func.unaccent(func.lower(models.Cliente.razon_social)).ilike(func.unaccent(f"%{razon_social.lower()}%")))
    if rfc:
        stmt = stmt.where(func.lower(models.Cliente.rfc).ilike(f"%{rfc.lower()}%"))
    if email:
        stmt = stmt.where(func.lower(models.Cliente.email).ilike(f"%{email.lower()}%"))
    if telefono:
        stmt = stmt.where(func.lower(models.Cliente.telefono).ilike(f"%{telefono.lower()}%"))
    if domicilio:
        stmt = stmt.where(func.lower(models.Cliente.domicilio).ilike(f"%{domicilio.lower()}%"))
    if entidad:
        stmt = stmt.join(models.Cliente.estado).where(func.unaccent(func.lower(Entidad.nomgeo)).ilike(func.unaccent(f"%{entidad.lower()}%")))
    if municipio:
        stmt = stmt.join(models.Cliente.localidad).where(func.unaccent(func.lower(Localidad.nom_mun)).ilike(func.unaccent(f"%{municipio.lower()}%")))
    if localidad:
        stmt = stmt.join(models.Cliente.localidad).where(func.unaccent(func.lower(Localidad.nom_loc)).ilike(func.unaccent(f"%{localidad.lower()}%")))
    if regimen_fiscal:
        stmt = stmt.join(models.Cliente.regimenfiscal).where(func.unaccent(func.lower(RegimenFiscal.descripcion)).ilike(func.unaccent(f"%{regimen_fiscal.lower()}%")))

    total_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total = await session.scalar(total_stmt)

    result = await session.execute(stmt)
    data = result.scalars().unique().all()

    return {"total_count": total, "data": data}

# -----------------------------------
# Obtener cliente por ID
# -----------------------------------
@router.get("/{id_cliente}", response_model=ClienteOut)
async def obtener_cliente(id_cliente: UUID, session: AsyncSession = Depends(get_async_db)):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

# -----------------------------------
# Crear cliente
# -----------------------------------
@router.post("/", response_model=ClienteOut)
async def crear_cliente(
    datos: ClienteCreate,
    session: AsyncSession = Depends(get_async_db),
    user_id: UUID = Depends(get_current_user_id),
):
    nuevo = models.Cliente(**datos.dict(), created_by=user_id, modified_by=user_id)
    session.add(nuevo)
    await session.commit()
    await session.refresh(nuevo)
    return nuevo

# -----------------------------------
# Actualizar cliente
# -----------------------------------
@router.put("/{id_cliente}", response_model=ClienteOut)
async def actualizar_cliente(
    id_cliente: UUID,
    datos: ClienteUpdate,
    session: AsyncSession = Depends(get_async_db),
    user_id: UUID = Depends(get_current_user_id),
):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    for campo, valor in datos.dict(exclude_unset=True).items():
        setattr(cliente, campo, valor)
    cliente.modified_by = user_id
    await session.commit()
    await session.refresh(cliente)
    return cliente

# -----------------------------------
# Eliminar cliente
# -----------------------------------
@router.delete("/{id_cliente}")
async def eliminar_cliente(id_cliente: UUID, session: AsyncSession = Depends(get_async_db)):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await session.delete(cliente)
    await session.commit()
    return {"ok": True}
