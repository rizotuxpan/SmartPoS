from sqlalchemy import Column, String, ForeignKey, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from db import Base


class Entidad(Base):
    __tablename__ = "entidad"

    cve_ent = Column("cve_ent", String(2), primary_key=True)
    nomgeo  = Column("nomgeo", String(100), nullable=False)

    # Relación con municipios
    municipios = relationship("Municipio", back_populates="entidad")


class Municipio(Base):
    __tablename__ = "municipio"

    cve_ent = Column("cve_ent", String(2), ForeignKey("entidad.cve_ent"), primary_key=True)
    cve_mun = Column("cve_mun", String(4), primary_key=True)
    nomgeo  = Column("nomgeo", String(100), nullable=False)

    # Relaciones
    entidad     = relationship("Entidad", back_populates="municipios")
    localidades = relationship("Localidad", back_populates="municipio")


class Localidad(Base):
    __tablename__ = "localidad"

    cve_ent = Column("cve_ent", String(2), primary_key=True)
    cve_mun = Column("cve_mun", String(4), primary_key=True)
    cve_loc = Column("cve_loc", String(5), primary_key=True)
    nomgeo  = Column("nomgeo", String(100), nullable=False)

    # Relación con municipio
    municipio = relationship("Municipio", back_populates="localidades")

    # Restricción de clave foránea compuesta
    __table_args__ = (
        ForeignKeyConstraint(
            ["cve_ent", "cve_mun"],
            ["municipio.cve_ent", "municipio.cve_mun"]
        ),
    )
