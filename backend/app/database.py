import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, func

# 1. Conexión dinámica a PostgreSQL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "epicplay_user")
DB_PASS = os.getenv("DB_PASSWORD", "epicplay_password")
DB_NAME = os.getenv("DB_NAME", "epicplay_db")

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
)

# 2. Crear engine de SQLAlchemy para PostgreSQL
engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class FotografiaRecord(Base):
    __tablename__ = "fotografias"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), index=True)
    es_nitida = Column(Boolean, default=True)
    varianza_laplaciana = Column(Float)
    estado = Column(String(50))  # 'procesada' o 'descartada'
    tiempo_ejecucion_ms = Column(Integer)  # Nombre exacto coincidente con PostgreSQL
    fecha_procesamiento = Column(DateTime, default=datetime.utcnow)

    ruta_instagram = Column(String, nullable=True)
    ruta_galeria_web = Column(String, nullable=True)
    ruta_impresion = Column(String, nullable=True)
    ruta_credencial = Column(String, nullable=True)
    ruta_ipad = Column(String, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ListaExportacionRecord(Base):
    __tablename__ = "lista_exportacion"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    formatos = Column(String(255), nullable=False)
    fecha_agregado = Column(DateTime, server_default=func.now())