# regimenfiscal.py
# -----------------------------
# Modelo SQLAlchemy para catálogo de régimen fiscal del SAT
# -----------------------------

from sqlalchemy import Column, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class RegimenFiscal(Base):
    __tablename__ = "regimenfiscal"

    id_regimenfiscal = Column(String(3), primary_key=True)
    descripcion = Column(String(255), nullable=False)
