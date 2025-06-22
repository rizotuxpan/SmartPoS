from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import Column, String, select, func, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, selectinload

from db import Base, get_async_db

# ----------------------
# Modelos ORM SQLAlchemy
# ----------------------
class Entidad(Base):
    __tablename__ = "entidad"

    cvegeo = Column(String(2), primary_key=True)
    cve_ent = Column(String(2), nullable=False, unique=True)
    nomgeo = Column(String(100), nullable=False, unique=True)

    # Relación con municipio
    municipios = relationship("Municipio", back_populates="entidad")

class Municipio(Base):
    __tablename__ = "municipio"

    cvegeo = Column(String(10), primary_key=True)
    cve_ent = Column(String(2), ForeignKey('entidad.cvegeo'), nullable=False)
    cve_mun = Column(String(4), nullable=False)
    nomgeo = Column(String(100), nullable=False)

    entidad = relationship()

# -------------------------
# Schemas Pydantic lectura
# -------------------------
class MunicipioRead(BaseModel):
    cvegeo: str
    cve_ent: str
    cve_mun: str
    nomgeo: str

    model_config = {"from_attributes": True}

class EntidadRead(BaseModel):
    cvegeo: str
    cve_ent: str
    nomgeo: str
    municipios: List[MunicipioRead]  # Incluye municipios relacionados

    model_config = {"from_attributes": True}

# ---------------------------
# Router y endpoints GET
# ---------------------------
router = APIRouter(prefix="/entidad", tags=["Entidad"])

@router.get("/", response_model=dict)
async def listar_entidades(
    nomgeo: Optional[str] = Query(None, description="Filtro por nombre (ilike)"),
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, gt=0, description="Límite de registros a devolver"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Lista todas las entidades con paginación y filtro opcional por nomgeo.
    """
    stmt = select(Entidad)
    if nomgeo:
        stmt = stmt.where(Entidad.nomgeo.ilike(f"%{nomgeo}%"))

    total = await db.scalar(
        select(func.count()).select_from(stmt.subquery())
    )

    result = await db.execute(stmt.offset(skip).limit(limit))
    data = result.scalars().all()

    return {
        "success": True,
        "total_count": total,
        "data": [EntidadRead.model_validate(e) for e in data]
    }

@router.get("/{cvegeo}", response_model=EntidadRead)
async def obtener_entidad(
    cvegeo: str = Path(..., min_length=2, max_length=2, description="Clave geográfica de la entidad"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una entidad por su clave primaria cvegeo e incluye municipios relacionados.
    """
    # Carga entidad y municipios con un solo query via selectinload
    stmt = (
        select(Entidad)
        .options(selectinload(Entidad.municipios))
        .where(Entidad.cvegeo == cvegeo)
    )
    result = await db.execute(stmt)
    entidad = result.scalar_one_or_none()

    if not entidad:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    return EntidadRead.model_validate(entidad)

@router.get("/nombre/{nomgeo}", response_model=EntidadRead)
async def obtener_entidad_por_nombre(
    nomgeo: str = Path(..., description="Nombre geográfico exacto de la entidad"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Obtiene una entidad por su nombre (nomgeo) e incluye municipios relacionados.
    """
    stmt = (
        select(Entidad)
        .options(selectinload(Entidad.municipios))
        .where(Entidad.nomgeo == nomgeo)
    )
    result = await db.execute(stmt)
    entidad = result.scalar_one_or_none()

    if not entidad:
        raise HTTPException(status_code=404, detail="Entidad no encontrada")

    return EntidadRead.model_validate(entidad)
