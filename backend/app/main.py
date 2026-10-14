import os
import shutil
import logging
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pythonjsonlogger import jsonlogger
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import init_db, get_db, FotografiaRecord, ListaExportacionRecord
from app.pipeline import procesar_fotografia
from fastapi.security import OAuth2PasswordRequestForm
from app.security import (
    hash_password, verify_password, create_access_token, 
    get_current_user, require_role
)


# 1. Configurar Logger Estructurado en JSON
logger = logging.getLogger("epicplay")
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# 2. Instanciar FastAPI
app = FastAPI(title="EpicPlay API")

# 3. Instrumentar con Prometheus
Instrumentator().instrument(app).expose(app)

# 4. Middleware para registrar cada Petición HTTP en JSON
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info("Peticion recibida", extra={
        "method": request.method,
        "url": str(request.url.path),
        "client_ip": request.client.host if request.client else "unknown"
    })
    response = await call_next(request)
    logger.info("Respuesta enviada", extra={
        "method": request.method,
        "url": str(request.url.path),
        "status_code": response.status_code
    })
    return response

# Inicializar las tablas de la base de datos al arrancar el backend
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- ENDPOINTS PARA LISTA DE EXPORTACIÓN (FASE 3) ---
from pydantic import BaseModel
from typing import List

class ItemLista(BaseModel):
    nombre_archivo: str
    formatos: List[str]

@app.get("/api/lista")
def obtener_lista(db: Session = Depends(get_db)):
    try:
        registros = db.query(ListaExportacionRecord).order_by(ListaExportacionRecord.id.desc()).all()
        lista = [
            {
                "id": r.id,
                "nombre_archivo": r.nombre_archivo,
                "formatos": r.formatos.split(",") if r.formatos else [],
                "fecha_agregado": str(r.fecha_agregado)
            }
            for r in registros
        ]
        return {"ok": True, "items": lista}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/api/lista/agregar")
def agregar_a_lista(item: ItemLista, db: Session = Depends(get_db)):
    try:
        formatos_str = ",".join(item.formatos)
        nuevo_item = ListaExportacionRecord(
            nombre_archivo=item.nombre_archivo,
            formatos=formatos_str
        )
        db.add(nuevo_item)
        db.commit()
        db.refresh(nuevo_item)
        return {"ok": True, "mensaje": "Foto agregada a la lista", "id": nuevo_item.id}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.delete("/api/lista/eliminar/{item_id}")
def eliminar_de_lista(item_id: int, db: Session = Depends(get_db)):
    try:
        item = db.query(ListaExportacionRecord).filter(ListaExportacionRecord.id == item_id).first()
        if not item:
            return {"ok": False, "error": "Elemento no encontrado"}
        
        db.delete(item)
        db.commit()
        return {"ok": True, "mensaje": f"Item {item_id} eliminado de la lista"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    # Base de datos simulada de usuarios con contraseñas encriptadas y roles
USERS_DB = {
    "admin_epicplay": {
        "username": "admin_epicplay",
        "password_hash": hash_password("AdminPass123!"),
        "role": "admin"
    },
    "fotografo_user": {
        "username": "fotografo_user",
        "password_hash": hash_password("UserPass123!"),
        "role": "user"
    }
}

@app.post("/api/auth/login", tags=["Autenticación"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    
    access_token = create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer", "role": user["role"]}

# Ruta protegida con JWT y Rol de Usuario
@app.get("/api/auth/perfil", tags=["Autenticación"])
async def obtener_perfil(current_user: dict = Depends(get_current_user)):
    return {"mensaje": "Acceso concedido", "usuario": current_user}

# Ejemplo de RBAC: Solo Administradores pueden eliminar
@app.delete("/api/lista/eliminar_admin/{item_id}", tags=["Lista Protegida"])
async def eliminar_como_admin(item_id: int, current_user: dict = Depends(require_role("admin"))):
    return {"ok": True, "mensaje": f"Elemento {item_id} eliminado por el admin {current_user['username']}"}