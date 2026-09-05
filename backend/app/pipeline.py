import cv2
import numpy as np
from PIL import Image, ImageCms, ImageEnhance
from ultralytics import YOLO
import os

# Carga del modelo local nano de YOLOv8
# La primera vez descargará automáticamente el archivo yolov8n.pt (3.2MB)
import torch
import os

# Parche de compatibilidad para PyTorch 2.6+ con YOLOv8
_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _torch_load(*args, **kwargs)

torch.load = _patched_torch_load

from ultralytics import YOLO

# Cargar el modelo YOLOv8n
model = YOLO("yolov8n.pt")

def calcular_nitidez(ruta_imagen):
    """Calcula la varianza Laplaciana para determinar si la foto está borrosa."""
    img = cv2.imread(ruta_imagen, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return cv2.Laplacian(img, cv2.CV_64F).var()

def procesar_fotografia(ruta_origen, ruta_destino, ruta_watermark=None, umbral_blur=100.0, relacion_aspecto="4:5"):
    """
    Ejecuta el pipeline completo de 9 pasos de EpicPlay.
    """
    # 1. Filtro de Nitidez (OpenCV)
    var_laplaciana = calcular_nitidez(ruta_origen)
    if var_laplaciana < umbral_blur:
        return {
            "estado": "descartada",
            "razon": "borrosa",
            "varianza": round(var_laplaciana, 2),
            "es_nitida": False
        }

    # 2. Detección de Jugadores y Balón (YOLOv8n local)
    results = model(ruta_origen, verbose=False)
    boxes = results[0].boxes.xyxy.cpu().numpy()
    
    img_pil = Image.open(ruta_origen).convert("RGB")
    ancho_orig, alto_orig = img_pil.size

    # Calcular centro de masa de la acción
    if len(boxes) > 0:
        cx = int(np.mean((boxes[:, 0] + boxes[:, 2]) / 2))
        cy = int(np.mean((boxes[:, 1] + boxes[:, 3]) / 2))
    else:
        cx, cy = ancho_orig // 2, alto_orig // 2

    # 3. Recorte Inteligente (4:5 o 1:1)
    ratio_target = 4 / 5 if relacion_aspecto == "4:5" else 1.0
    
    if (ancho_orig / alto_orig) > ratio_target:
        crop_h = alto_orig
        crop_w = int(crop_h * ratio_target)
    else:
        crop_w = ancho_orig
        crop_h = int(crop_w / ratio_target)

    left = max(0, min(cx - crop_w // 2, ancho_orig - crop_w))
    top = max(0, min(cy - crop_h // 2, alto_orig - crop_h))
    img_cropped = img_pil.crop((left, top, left + crop_w, top + crop_h))

    # 4. Resize Estandarizado a 1080px de ancho
    nuevo_ancho = 1080
    nuevo_alto = int(crop_h * (nuevo_ancho / crop_w))
    img_resized = img_cropped.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)

    # 5. Ajuste de Color (Macros equivalentes)
    enhancer_contrast = ImageEnhance.Contrast(img_resized)
    img_color = enhancer_contrast.enhance(1.15)  # +15% contraste
    
    enhancer_color = ImageEnhance.Color(img_color)
    img_color = enhancer_color.enhance(1.10)     # +10% saturación

    # 6. Estampado de Marca de Agua / Logo
    if ruta_watermark and os.path.exists(ruta_watermark):
        watermark = Image.open(ruta_watermark).convert("RGBA")
        wm_w = int(nuevo_ancho * 0.18)  # 18% del ancho de la imagen
        wm_h = int(watermark.height * (wm_w / watermark.width))
        watermark = watermark.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
        
        # Posición fija: Esquina inferior derecha con 30px de margen
        pos_x = nuevo_ancho - wm_w - 30
        pos_y = nuevo_alto - wm_h - 30
        img_color.paste(watermark, (pos_x, pos_y), watermark)

    # 7. Exportación Final PNG con espacio de color sRGB
    srgb_profile = ImageCms.createProfile('sRGB')
    img_color.save(
        ruta_destino,
        format='PNG',
        optimize=True,
        icc_profile=srgb_profile.tobytes()
    )

    return {
        "estado": "procesada",
        "es_nitida": True,
        "varianza": round(var_laplaciana, 2),
        "ancho_px": nuevo_ancho,
        "alto_px": nuevo_alto,
        "formato": relacion_aspecto
    }