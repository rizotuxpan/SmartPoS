# cliente.py - GENERADO A PARTIR DE producto.py
# -------------------------------------------------------
# Endpoints REST para la tabla "cliente" adaptados de producto
# Incluye filtros, paginación y relaciones (régimen fiscal, localidad)
# -------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update, delete, insert, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_async_session
from auth import get_current_user_id
import cliente as models
from regimenfiscal import RegimenFiscal
from localidad import Localidad
from geografia import Entidad

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# ---------------------
# Schemas Pydantic
# ---------------------
class ClienteBase(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    domicilio: Optional[str] = None
    cp: Optional[str] = None
    municipio: Optional[str] = None
    clave: Optional[str] = None
    cve_ent: Optional[str] = None
    cve_mun: Optional[str] = None
    cve_loc: Optional[str] = None
    id_regimenfiscal: str = Field(..., max_length=3)

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(ClienteBase):
    nombre: Optional[str] = None
    id_estado: Optional[UUID] = None

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

# ---------------------
# GET /clientes
# ---------------------
@router.get("/", response_model=dict)
async def listar_clientes(
    skip: int = 0,
    limit: int = 50,
    nombre: Optional[str] = Query(None),
    apellido: Optional[str] = Query(None),
    razon_social: Optional[str] = Query(None),
    rfc: Optional[str] = Query(None),
    telefono: Optional[str] = Query(None),
    domicilio: Optional[str] = Query(None),
    entidad: Optional[str] = Query(None),
    municipio_nombre: Optional[str] = Query(None),
    localidad_nombre: Optional[str] = Query(None),
    regimen_fiscal_nombre: Optional[str] = Query(None),
    expandir: bool = False,
    session: AsyncSession = Depends(get_async_session),
):
    from sqlalchemy.orm import joinedload
    stmt = select(models.Cliente).offset(skip).limit(limit)

    # Relaciones que se pueden filtrar
    stmt = stmt.options(
        joinedload(models.Cliente.regimenfiscal),
        joinedload(models.Cliente.localidad),
        joinedload(models.Cliente.estado)
    )

    if nombre:
        stmt = stmt.where(func.lower(models.Cliente.nombre).ilike(f"%{{nombre.lower()}}%"))
    if apellido:
        stmt = stmt.where(func.lower(models.Cliente.apellido).ilike(f"%{{apellido.lower()}}%"))
    if razon_social:
        stmt = stmt.where(func.lower(models.Cliente.razon_social).ilike(f"%{{razon_social.lower()}}%"))
    if rfc:
        stmt = stmt.where(func.lower(models.Cliente.rfc).ilike(f"%{{rfc.lower()}}%"))
    if telefono:
        stmt = stmt.where(func.lower(models.Cliente.telefono).ilike(f"%{{telefono.lower()}}%"))
    if domicilio:
        stmt = stmt.where(func.lower(models.Cliente.domicilio).ilike(f"%{{domicilio.lower()}}%"))

    if entidad:
        stmt = stmt.join(models.Cliente.estado).where(func.lower(CatEstado.nombre).ilike(f"%{{entidad.lower()}}%"))
    if municipio_nombre:
        stmt = stmt.join(models.Cliente.localidad).where(func.lower(Localidad.nom_mun).ilike(f"%{{municipio_nombre.lower()}}%"))
    if localidad_nombre:
        stmt = stmt.join(models.Cliente.localidad).where(func.lower(Localidad.nom_loc).ilike(f"%{{localidad_nombre.lower()}}%"))
    if regimen_fiscal_nombre:
        stmt = stmt.join(models.Cliente.regimenfiscal).where(func.lower(RegimenFiscal.descripcion).ilike(f"%{{regimen_fiscal_nombre.lower()}}%"))

    result = await session.execute(stmt)
    clientes = result.scalars().unique().all()

    total_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total = await session.scalar(total_stmt)
    return {{ "total_count": total, "data": clientes }}


# ---------------------
# GET /clientes/{id}
# ---------------------
@router.get("/{id_cliente}", response_model=ClienteOut)
async def obtener_cliente(id_cliente: UUID, session: AsyncSession = Depends(get_async_session)):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente

# ---------------------
# POST /clientes
# ---------------------
@router.post("/", response_model=ClienteOut)
async def crear_cliente(
    payload: ClienteCreate,
    session: AsyncSession = Depends(get_async_session),
    user_id: UUID = Depends(get_current_user_id),
):
    nuevo = models.Cliente(**payload.dict(), created_by=user_id, modified_by=user_id)
    session.add(nuevo)
    await session.commit()
    await session.refresh(nuevo)
    return nuevo

# ---------------------
# PUT /clientes/{id}
# ---------------------
@router.put("/{id_cliente}", response_model=ClienteOut)
async def actualizar_cliente(
    id_cliente: UUID,
    payload: ClienteUpdate,
    session: AsyncSession = Depends(get_async_session),
    user_id: UUID = Depends(get_current_user_id),
):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(cliente, field, value)
    cliente.modified_by = user_id
    await session.commit()
    await session.refresh(cliente)
    return cliente

# ---------------------
# DELETE /clientes/{id}
# ---------------------
@router.delete("/{id_cliente}")
async def eliminar_cliente(id_cliente: UUID, session: AsyncSession = Depends(get_async_session)):
    cliente = await session.get(models.Cliente, id_cliente)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await session.delete(cliente)
    await session.commit()
    return { "ok": True }
