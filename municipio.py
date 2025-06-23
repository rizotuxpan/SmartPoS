from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, String, ForeignKey, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, selectinload

from db import Base, get_async_db
from entidad import Municipio, MunicipioRead

# ----------------------
# Modelo ORM SQLAlchemy
# ----------------------
class Localidad(Base):
    __tablename__ = "localidad"

    # Clave primaria compuesta
    cve_ent = Column(String(2), primary_key=True)
    cve_mun = Column(String(4), primary_key=True)
    cve_loc = Column(String(5), primary_key=True)

    nomgeo  = Column(String(100), nullable=False)
    ambito  = Column(String(10), nullable=False)
    ent_mun = Column(String(10), ForeignKey('municipio.cvegeo'), nullable=False)

    municipio = relationship("Municipio", back_populates="localidades")

# Agregar relación de Localidad en la clase Municipio importada
Municipio.localidades = relationship(
    "Localidad",
    back_populates="municipio",
    lazy="selectin"
)

# -------------------------
# Schemas Pydantic lectura
# -------------------------
class LocalidadRead(BaseModel):
    cve_ent: str
    cve_mun: str
    cve_loc: str
    nomgeo: str
    ambito: str
    ent_mun: str

    model_config = {"from_attributes": True}

# ---------------------------
# Router y endpoint GET
# ---------------------------
router = APIRouter(prefix="/municipios", tags=["Municipios"])

@router.get("/{cvegeo}", response_model=dict)
async def listar_localidades_por_municipio(
    cvegeo: str = Path(..., description="Clave geográfica del municipio"),
    db: AsyncSession = Depends(get_async_db)
):
    stmt = (
        select(Municipio)
        .options(selectinload(Municipio.localidades))
        .where(Municipio.cvegeo == cvegeo)
    )
    municipio = (await db.execute(stmt)).scalar_one_or_none()
    if not municipio:
        raise HTTPException(status_code=404, detail="Municipio no encontrado")

    localidades = municipio.localidades
    return {
        "success": True,
        "total_count": len(localidades),
        "data": [LocalidadRead.model_validate(loc) for loc in localidades]
    }
