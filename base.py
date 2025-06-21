from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from typing import TypeVar, Generic, Type, Optional, List
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import Column, String, DateTime, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Base declarativa para modelos
class Base(DeclarativeBase):
    pass

# Modelo base reutilizable para catálogos simples
class BaseEntity(Base):
    __abstract__ = True

    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    nombre: str = Column(String(80), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(PG_UUID(as_uuid=True), nullable=False)
    modified_by = Column(PG_UUID(as_uuid=True), nullable=False)
    id_empresa = Column(PG_UUID(as_uuid=True), nullable=False)
    id_estado = Column(PG_UUID(as_uuid=True), nullable=False)

# Tipos genéricos
ModelType = TypeVar("ModelType", bound=BaseEntity)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
ReadSchemaType = TypeVar("ReadSchemaType", bound=BaseModel)

# Base Pydantic
class BaseSchema(BaseModel):
    nombre: str
    model_config = {"from_attributes": True}

# Generador de router genérico
class BaseRouter(Generic[ModelType, CreateSchemaType, UpdateSchemaType, ReadSchemaType]):
    def __init__(self, model: Type[ModelType], create_schema: Type[CreateSchemaType], update_schema: Type[UpdateSchemaType], read_schema: Type[ReadSchemaType], estado_borrado_id: UUID):
        self.model = model
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.read_schema = read_schema
        self.estado_borrado_id = estado_borrado_id
        self.router = APIRouter()
        self._register_routes()

    def _register_routes(self):

        @self.router.get("/", response_model=dict)
        async def listar(
            nombre: Optional[str] = Query(None),
            skip: int = 0,
            limit: int = 100,
            db: AsyncSession = Depends(self.get_db)
        ):
            stmt = select(self.model).where(self.model.id_estado != self.estado_borrado_id)
            if nombre:
                stmt = stmt.where(self.model.nombre.ilike(f"%{nombre}%"))
            total_stmt = select(func.count()).select_from(stmt.subquery())
            total = await db.scalar(total_stmt)
            result = await db.execute(stmt.offset(skip).limit(limit))
            data = result.scalars().all()
            return {
                "success": True,
                "total_count": total,
                "data": [self.read_schema.model_validate(m) for m in data]
            }

        @self.router.get("/{id}", response_model=self.read_schema)
        async def obtener(id: UUID, db: AsyncSession = Depends(self.get_db)):
            result = await db.execute(select(self.model).where(self.model.id == id))
            obj = result.scalar_one_or_none()
            if not obj or obj.id_estado == self.estado_borrado_id:
                raise HTTPException(status_code=404, detail="No encontrado")
            return self.read_schema.model_validate(obj)

        @self.router.post("/", response_model=dict, status_code=201)
        async def crear(
            entrada: self.create_schema,
            db: AsyncSession = Depends(self.get_db),
            x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
            x_user_id: UUID = Header(..., alias="X-User-ID")
        ):
            nuevo = self.model(
                id=uuid4(),
                nombre=entrada.nombre,
                created_by=x_user_id,
                modified_by=x_user_id,
                id_empresa=x_tenant_id,
                id_estado=UUID("00000000-0000-0000-0000-000000000001")
            )
            db.add(nuevo)
            await db.commit()
            await db.refresh(nuevo)
            return {"success": True, "data": self.read_schema.model_validate(nuevo)}

        @self.router.put("/{id}", response_model=dict)
        async def actualizar(
            id: UUID,
            entrada: self.update_schema,
            db: AsyncSession = Depends(self.get_db),
            x_user_id: UUID = Header(..., alias="X-User-ID")
        ):
            result = await db.execute(select(self.model).where(self.model.id == id))
            obj = result.scalar_one_or_none()
            if not obj or obj.id_estado == self.estado_borrado_id:
                raise HTTPException(status_code=404, detail="No encontrado")
            obj.nombre = entrada.nombre
            obj.modified_by = x_user_id
            await db.commit()
            await db.refresh(obj)
            return {"success": True, "data": self.read_schema.model_validate(obj)}

        @self.router.delete("/{id}", status_code=200)
        async def eliminar(
            id: UUID,
            db: AsyncSession = Depends(self.get_db),
            x_user_id: UUID = Header(..., alias="X-User-ID")
        ):
            result = await db.execute(select(self.model).where(self.model.id == id))
            obj = result.scalar_one_or_none()
            if not obj or obj.id_estado == self.estado_borrado_id:
                raise HTTPException(status_code=404, detail="No encontrado")
            obj.id_estado = self.estado_borrado_id
            obj.modified_by = x_user_id
            await db.commit()
            return {"success": True, "message": "Eliminado correctamente"}

    # Simulación de dependencia de DB (reemplazar en integración real)
    async def get_db(self):
        raise NotImplementedError("Implementa esta dependencia de DB en tu aplicación")

    def get_router(self):
        return self.router
