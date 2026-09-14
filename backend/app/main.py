from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import shutil
from pathlib import Path
from app.pipeline import procesar_fotografia

app = FastAPI(title="EpicPlay - Pipeline & Data Engine")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "dbname": "epicplay_db",
    "user": "epicplay_user",
    "password": "epicplay_password",
    "host": "localhost",
    "port": "5432"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

# Inicializar Base de Datos con Esquema Completo
# Inicializar Base de Datos con Esquema Actualizado
def init_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Eliminar versión previa para actualizar columnas de la Fase 2.1
        cursor.execute("DROP TABLE IF EXISTS fotografias;")
        cursor.execute("""
            CREATE TABLE fotografias (
                id SERIAL PRIMARY KEY,
                nombre_archivo VARCHAR(255) NOT NULL,
                varianza_laplaciana FLOAT NOT NULL,
                es_nitida BOOLEAN NOT NULL,
                estado VARCHAR(50) NOT NULL,
                tiempo_ejecucion_ms INT NOT NULL,
                fecha_procesamiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Base de datos sincronizada con el nuevo esquema de la Fase 2.1.")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
init_db()

@app.post("/api/procesar-foto")
async def procesar_foto_endpoint(file: UploadFile = File(...)):
    ruta_base = Path(__file__).resolve().parent.parent
    dir_raw = ruta_base / "uploads" / "raw"
    dir_proc = ruta_base / "uploads" / "processed"

    dir_raw.mkdir(parents=True, exist_ok=True)
    dir_proc.mkdir(parents=True, exist_ok=True)

    ruta_raw = dir_raw / file.filename
    ruta_proc = dir_proc / f"proc_{file.filename}"

    with open(ruta_raw, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ejecutar Pipeline
    res = procesar_fotografia(str(ruta_raw), str(ruta_proc))

    # Registrar resultado en PostgreSQL mediante SQL directo
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fotografias 
            (nombre_archivo, varianza_laplaciana, es_nitida, estado, tiempo_ejecucion_ms)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (res["nombre"], res["varianza"], res["es_nitida"], res["estado"], res["tiempo_ms"]))
        
        foto_id = cursor.fetchone()["id"]
        conn.commit()
        cursor.close()
        conn.close()
        res["id"] = foto_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")

    return res

# Endpoint de Consultas SQL avanzadas para la UI y la Fase 2.1
@app.get("/api/fotografias")
def listar_fotografias(estado: str = Query(None), orden: str = Query("desc")):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM fotografias"
    params = []
    
    if estado:
        query += " WHERE estado = %s"
        params.append(estado)
        
    query += f" ORDER BY fecha_procesamiento {orden.upper()};"
    
    cursor.execute(query, params)
    fotos = cursor.fetchall()
    cursor.close()
    conn.close()
    return fotos

# Endpoint de Métricas Globales para el Panel (Dashboard)
@app.get("/api/metricas")
def obtener_metricas():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_fotos,
            COUNT(*) FILTER (WHERE estado = 'procesada') as procesadas,
            COUNT(*) FILTER (WHERE estado = 'descartada') as descartadas,
            COALESCE(AVG(tiempo_ejecucion_ms), 0) as tiempo_promedio_ms,
            COALESCE(AVG(varianza_laplaciana), 0) as varianza_promedio
        FROM fotografias;
    """)
    
    metricas = cursor.fetchone()
    cursor.close()
    conn.close()
    return metricas