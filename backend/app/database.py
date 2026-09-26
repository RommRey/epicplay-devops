import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# 1. Conexión dinámica a PostgreSQL
# Si corre dentro de Docker usa DB_HOST=postgres, si corre local usa localhost
DB_HOST = os.getenv("DB_HOST", "localhost")
SQLALCHEMY_DATABASE_URL = f"postgresql://epicplay_user:epicplay_password@{DB_HOST}:5432/epicplay_db"

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