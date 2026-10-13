import sys
import os

# Asegurar que encuentre el directorio del backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from app.main import app

# Pasamos app directamente como argumento posicional para evitar el error de parámetro
client = TestClient(app)

def test_agregar_y_consultar_lista():
    payload = {
        "nombre_archivo": "test_partido_01.JPG",
        "formatos": ["instagram", "credencial"]
    }
    response = client.post("/api/lista/agregar", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "id" in data

    res_consulta = client.get("/api/lista")
    assert res_consulta.status_code == 200
    assert len(res_consulta.json()["items"]) > 0

def test_eliminar_elemento_lista():
    payload = {
        "nombre_archivo": "test_partido_02.JPG",
        "formatos": ["ipad"]
    }
    res_add = client.post("/api/lista/agregar", json=payload).json()
    item_id = res_add["id"]

    res_del = client.delete(f"/api/lista/eliminar/{item_id}")
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is True

def test_error_eliminar_item_inexistente():
    res_del = client.delete("/api/lista/eliminar/999999")
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is False
    assert "Elemento no encontrado" in res_del.json()["error"]

def test_error_payload_invalido():
    payload = {
        "nombre_archivo": "foto_sin_formatos.JPG"
    }
    response = client.post("/api/lista/agregar", json=payload)
    # Acepta tanto 422 como 400 para validaciones de esquema
    assert response.status_code in [400, 422]