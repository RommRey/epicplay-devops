import os
import shutil
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import init_db, get_db, FotografiaRecord
from app.pipeline import procesar_fotografia

app = FastAPI(title="EpicPlay Engine")

# Inicializar las tablas de la base de datos al arrancar el backend
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "API de EpicPlay lista"}

@app.post("/api/procesar-foto")
async def procesar_foto_endpoint(
    files: List[UploadFile] = File(...),
    formatos: Optional[str] = Form("instagram,galeria_web,impresion,credencial,ipad"),
    db: Session = Depends(get_db)
):
    formatos_lista = [f.strip() for f in formatos.split(",") if f.strip()]
    temp_dir = os.path.abspath("uploads/temp")
    base_dir_salida = os.path.abspath("uploads/processed")
    os.makedirs(temp_dir, exist_ok=True)

    resultados_lista = []

    for file in files:
        # Guardar archivo subido temporalmente en disco
        ruta_temp = os.path.join(temp_dir, file.filename)
        with open(ruta_temp, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        nombre_base = os.path.splitext(file.filename)[0]

        # Procesar con el pipeline
        resultado = procesar_fotografia(ruta_temp, base_dir_salida, formatos=formatos_lista)

        # Registrar en Base de Datos
        registro = FotografiaRecord(
            nombre_archivo=resultado["nombre"],
            es_nitida=resultado["es_nitida"],
            varianza_laplaciana=resultado["varianza"],
            estado=resultado["estado"],
            tiempo_ejecucion_ms=resultado["tiempo_ms"],
            ruta_instagram=os.path.join(base_dir_salida, "instagram", f"{nombre_base}_ig.png") if "instagram" in formatos_lista and resultado["es_nitida"] else None,
            ruta_galeria_web=os.path.join(base_dir_salida, "galeria_web", f"{nombre_base}_web.jpg") if "galeria_web" in formatos_lista and resultado["es_nitida"] else None,
            ruta_impresion=os.path.join(base_dir_salida, "impresion_4x6", f"{nombre_base}_print.jpg") if "impresion" in formatos_lista and resultado["es_nitida"] else None,
            ruta_credencial=os.path.join(base_dir_salida, "credencial", f"{nombre_base}_credencial.jpg") if "credencial" in formatos_lista and resultado["es_nitida"] else None,
            ruta_ipad=os.path.join(base_dir_salida, "ipad", f"{nombre_base}_ipad.jpg") if "ipad" in formatos_lista and resultado["es_nitida"] else None
        )

        db.add(registro)
        db.commit()
        db.refresh(registro)

        # Limpiar archivo temporal
        if os.path.exists(ruta_temp):
            try:
                os.remove(ruta_temp)
            except Exception:
                pass

        resultados_lista.append({"id": registro.id, "detalles": resultado})

    return {"procesados": len(resultados_lista), "resultados": resultados_lista}

@app.get("/api/fotografias")
def obtener_historial_fotografias(db: Session = Depends(get_db)):
    registros = db.query(FotografiaRecord).order_by(FotografiaRecord.id.desc()).all()
    
    # Formateo explícito mapeando tiempo_ejecucion_ms a tiempo_ms para la interfaz gráfica
    resultado = []
    for r in registros:
        resultado.append({
            "id": r.id,
            "nombre_archivo": r.nombre_archivo,
            "estado": r.estado,
            "varianza_laplaciana": r.varianza_laplaciana,
            "tiempo_ms": r.tiempo_ejecucion_ms  # <-- CORREGIDO AQUÍ
        })
    return resultado

@app.delete("/api/fotografias/{foto_id}")
def eliminar_fotografia(foto_id: int, db: Session = Depends(get_db)):
    registro = db.query(FotografiaRecord).filter(FotografiaRecord.id == foto_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")

    rutas = [
        registro.ruta_instagram,
        registro.ruta_galeria_web,
        registro.ruta_impresion,
        registro.ruta_credencial,
        registro.ruta_ipad
    ]
    for r in rutas:
        if r and os.path.exists(r):
            try:
                os.remove(r)
            except Exception:
                pass

    db.delete(registro)
    db.commit()
    return {"message": f"Fotografía ID {foto_id} eliminada correctamente"}

@app.delete("/api/fotografias")
def limpiar_todo_el_historial(db: Session = Depends(get_db)):
    db.query(FotografiaRecord).delete()
    db.commit()

    folder_processed = os.path.abspath("uploads/processed")
    if os.path.exists(folder_processed):
        for item in os.listdir(folder_processed):
            sub_path = os.path.join(folder_processed, item)
            if os.path.isdir(sub_path):
                for f in os.listdir(sub_path):
                    file_p = os.path.join(sub_path, f)
                    if os.path.isfile(file_p):
                        try:
                            os.remove(file_p)
                        except Exception:
                            pass

    return {"message": "Historial y archivos procesados eliminados correctamente"}