# regimenfiscal.py
# -----------------------------
# Modelo SQLAlchemy para catálogo de régimen fiscal del SAT
# CORREGIDO para coincidir con la estructura real de la tabla
# -----------------------------

from sqlalchemy import Column, String, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from db import Base

class RegimenFiscal(Base):
    __tablename__ = "regimenfiscal"

    id_regimenfiscal = Column(String(3), primary_key=True)
    nombre = Column(String(120), nullable=False)  # CORRECTO: era 'descripcion'
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
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)