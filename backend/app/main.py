from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import shutil
import os
import time
from app.pipeline import procesar_fotografia

app = FastAPI(title="EpicPlay API - DevOps Phase 2")

# Permitir peticiones desde el frontend (Vue / Vuetify)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directorios de trabajo
OS_TMP = "./uploads/raw"
OS_OUT = "./uploads/processed"
os.makedirs(OS_TMP, exist_ok=True)
os.makedirs(OS_OUT, exist_ok=True)

# Configuración de conexión a PostgreSQL
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "epicplay_user",
    "password": "epicplay_password",
    "dbname": "epicplay_db"
}

def get_db():
    return psycopg2.connect(**DB_CONFIG)

@app.post("/api/procesar-foto")
async def procesar_foto_endpoint(file: UploadFile = File(...)):
    inicio_time = time.time()
    
    ruta_raw = os.path.join(OS_TMP, file.filename)
    nombre_out = f"proc_{os.path.splitext(file.filename)[0]}.png"
    ruta_out = os.path.join(OS_OUT, nombre_out)

    # Guardar archivo subido localmente
    with open(ruta_raw, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ejecutar pipeline
    res = procesar_fotografia(ruta_raw, ruta_out, ruta_watermark=None)
    tiempo_total_ms = int((time.time() - inicio_time) * 1000)

    # Guardar trazabilidad en PostgreSQL
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        INSERT INTO fotografias 
        (nombre_archivo, ruta_original, ruta_procesada, es_nitida, varianza_laplaciana, formato_recorte, ancho_px, alto_px, estado, tiempo_procesamiento_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    
    cursor.execute(query, (
        file.filename,
        ruta_raw,
        ruta_out if res["estado"] == "procesada" else None,
        res["es_nitida"],
        res["varianza"],
        res.get("formato", "4:5"),
        res.get("ancho_px", 0),
        res.get("alto_px", 0),
        res["estado"],
        tiempo_total_ms
    ))
    
    foto_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "id": foto_id,
        "filename": file.filename,
        "resultado": res,
        "tiempo_procesamiento_ms": tiempo_total_ms
    }

@app.get("/api/fotografias")
def listar_fotografias():
    """Endpoint para que el frontend consulte el historial cargado."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre_archivo, es_nitida, varianza_laplaciana, estado, tiempo_procesamiento_ms, creado_en FROM fotografias ORDER BY id DESC;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return [
        {
            "id": r[0],
            "nombre": r[1],
            "es_nitida": r[2],
            "varianza": r[3],
            "estado": r[4],
            "tiempo_ms": r[5],
            "fecha": r[6]
        } for r in rows
    ]