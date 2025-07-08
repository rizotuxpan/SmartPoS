# eml.py
# ---------------------------
# Módulo de endpoints REST para gestión de Entidad-Municipio-Localidad
# Usa FastAPI, SQLAlchemy Async y Pydantic para validación.
# ---------------------------

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_async_db
from geografia import Entidad, Municipio, Localidad

# -------------------------
# Schemas Pydantic
# -------------------------
class EntidadRead(BaseModel):
    cve_ent: str
    nomgeo: str

    model_config = {"from_attributes": True}


class EntidadNomgeoRead(BaseModel):
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


# ---------------------------
# Router y Endpoints
# ---------------------------
router = APIRouter()

@router.get("/", summary="Ping")
async def root():
    """Endpoint raíz - no devuelve nada."""
    return {}

@router.get("/entidad", response_model=dict, summary="Listar todas las entidades")
async def listar_entidades(db: AsyncSession = Depends(get_async_db)):
    stmt = select(Entidad)
    result = await db.execute(stmt)
    entidades = result.scalars().all()
    return {"success": True, "data": [EntidadRead.model_validate(e) for e in entidades]}

@router.get("/entidad/{cve_ent}", response_model=EntidadNomgeoRead, summary="Obtener nombre de una entidad")
async def obtener_nomgeo_entidad(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    db: AsyncSession = Depends(get_async_db)
):
    stmt = select(Entidad).where(Entidad.cve_ent == cve_ent)
    entidad = (await db.execute(stmt)).scalar_one_or_none()
    if not entidad:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")
    return EntidadNomgeoRead.model_validate(entidad)

@router.get("/entidad/{cve_ent}/municipio", response_model=dict, summary="Listar municipios de una entidad")
async def listar_municipios_por_entidad(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    db: AsyncSession = Depends(get_async_db)
):
    # Verificar existencia de entidad
    exist = (await db.execute(select(Entidad).where(Entidad.cve_ent == cve_ent))).scalar_one_or_none()
    if not exist:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    stmt = select(Municipio).where(Municipio.cve_ent == cve_ent)
    municipios = (await db.execute(stmt)).scalars().all()
    return {"success": True, "data": [MunicipioRead.model_validate(m) for m in municipios]}

@router.get("/entidad/{cve_ent}/municipio/{cve_mun}", response_model=MunicipioRead, summary="Obtener datos de un municipio")
async def obtener_municipio_especifico(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    cve_mun: str = Path(..., min_length=1, max_length=4, description="Clave del municipio"),
    db: AsyncSession = Depends(get_async_db)
):
    stmt = select(Municipio).where(
        Municipio.cve_ent == cve_ent,
        Municipio.cve_mun == cve_mun
    )
    municipio = (await db.execute(stmt)).scalar_one_or_none()
    if not municipio:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")
    return MunicipioRead.model_validate(municipio)

@router.get("/entidad/{cve_ent}/municipio/{cve_mun}/localidad", response_model=dict, summary="Listar localidades de un municipio")
async def listar_localidades_por_municipio(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    cve_mun: str = Path(..., min_length=1, max_length=4, description="Clave del municipio"),
    db: AsyncSession = Depends(get_async_db)
):
    # Verificar existencia de municipio
    exist = (await db.execute(select(Municipio).where(
        Municipio.cve_ent == cve_ent,
        Municipio.cve_mun == cve_mun
    ))).scalar_one_or_none()
    if not exist:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")

    stmt = select(Localidad).where(
        Localidad.cve_ent == cve_ent,
        Localidad.cve_mun == cve_mun
    )
    localidades = (await db.execute(stmt)).scalars().all()
    return {"success": True, "data": [LocalidadRead.model_validate(l) for l in localidades]}

# ---------------------------
# Endpoints de búsqueda
# ---------------------------
@router.get("/entidad/buscar", response_model=dict, summary="Buscar entidades por nombre")
async def buscar_entidades(
    q: str = Query(..., min_length=1, description="Texto a buscar en el nombre de la entidad"),
    db: AsyncSession = Depends(get_async_db)
):
    stmt = select(Entidad).where(Entidad.nomgeo.ilike(f"%{q}%"))
    entidades = (await db.execute(stmt)).scalars().all()
    return {"success": True, "data": [EntidadRead.model_validate(e) for e in entidades]}

@router.get("/entidad/{cve_ent}/municipio/buscar", response_model=dict, summary="Buscar municipios por nombre")
async def buscar_municipios_por_entidad(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    q: str = Query(..., min_length=1, description="Texto a buscar en el nombre del municipio"),
    db: AsyncSession = Depends(get_async_db)
):
    # Verificar existencia de entidad
    exist = (await db.execute(select(Entidad).where(Entidad.cve_ent == cve_ent))).scalar_one_or_none()
    if not exist:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    stmt = select(Municipio).where(
        Municipio.cve_ent == cve_ent,
        Municipio.nomgeo.ilike(f"%{q}%")
    )
    municipios = (await db.execute(stmt)).scalars().all()
    return {"success": True, "data": [MunicipioRead.model_validate(m) for m in municipios]}

@router.get("/entidad/{cve_ent}/municipio/{cve_mun}/localidad/buscar", response_model=dict, summary="Buscar localidades por nombre")
async def buscar_localidades_por_municipio(
    cve_ent: str = Path(..., min_length=2, max_length=2, description="Clave de la entidad"),
    cve_mun: str = Path(..., min_length=1, max_length=4, description="Clave del municipio"),
    q: str = Query(..., min_length=1, description="Texto a buscar en el nombre de la localidad"),
    db: AsyncSession = Depends(get_async_db)
):
    # Verificar existencia de municipio
    exist = (await db.execute(select(Municipio).where(
        Municipio.cve_ent == cve_ent,
        Municipio.cve_mun == cve_mun
    ))).scalar_one_or_none()
    if not exist:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")

    stmt = select(Localidad).where(
        Localidad.cve_ent == cve_ent,
        Localidad.cve_mun == cve_mun,
        Localidad.nomgeo.ilike(f"%{q}%")
    )
    localidades = (await db.execute(stmt)).scalars().all()
    return {"success": True, "data": [LocalidadRead.model_validate(l) for l in localidades]}
