import os
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageCms, ImageEnhance, ImageOps, ImageFilter
import torch
from ultralytics import YOLO

# Parche de compatibilidad PyTorch 2.6+
_torch_load = torch.load
def _safe_torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _torch_load(*args, **kwargs)

torch.load = _safe_torch_load

# Cargar modelos de Ultralytics
modelo_pose = YOLO("yolov8n-pose.pt")
modelo_objetos = YOLO("yolov8n.pt")

# Rutas fijas de Marcas de Agua
RUTA_LOGO_NORMAL = r"C:\Users\Romm\Pictures\EP_Logo_circle_HD .png"
RUTA_LOGO_TRANSPARENTE = r"C:\Users\Romm\Pictures\Epic_Play_Watermark_Transparent_HQ.png"

def calcular_varianza_laplaciana(imagen_cv, box_sujeto=None):
    """
    Calcula la nitidez enfocándose en el sujeto principal para evitar 
    falsos positivos causados por redes o follaje en el fondo.
    """
    h_img, w_img, _ = imagen_cv.shape
    if box_sujeto is not None:
        x1, y1, x2, y2 = map(int, box_sujeto)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img, x2), min(h_img, y2)
        recorte_sujeto = imagen_cv[y1:y2, x1:x2]
        if recorte_sujeto.size > 0:
            gris = cv2.cvtColor(recorte_sujeto, cv2.COLOR_BGR2GRAY)
            return cv2.Laplacian(gris, cv2.CV_64F).var()

    gris_completo = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gris_completo, cv2.CV_64F).var()

def aplicar_enfoque_post_escalado(img_pil):
    """Aplica una máscara de enfoque sutil tras el rescale a 1080px."""
    return img_pil.filter(ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=3))

def aplicar_curva_luz_y_filtros(img_pil):
    """Filtro neutro y equilibrado (Contraste +10%, Saturación 1.0x)."""
    enhancer_contrast = ImageEnhance.Contrast(img_pil)
    img_contrast = enhancer_contrast.enhance(1.10)

    enhancer_color = ImageEnhance.Color(img_contrast)
    img_saturated = enhancer_color.enhance(1.00)

    lut = []
    for i in range(256):
        x = i / 255.0
        y = 2 * (x ** 2) if x < 0.5 else 1 - 2 * ((1 - x) ** 2)
        y_final = (y * 0.20) + (x * 0.80)
        lut.append(int(np.clip(y_final * 255.0, 0, 255)))

    return img_saturated.point(lut * 3)

def obtener_sujeto_principal(imagen_cv):
    res_pose = modelo_pose(imagen_cv, verbose=False)[0]
    res_obj = modelo_objetos(imagen_cv, verbose=False)[0]
    h_img, w_img, _ = imagen_cv.shape

    balon_box = None
    for box in res_obj.boxes:
        if int(box.cls[0]) == 32:  # 32 = sports ball
            balon_box = box.xyxy[0].cpu().numpy()
            break

    candidatos = []
    if res_pose.keypoints is not None and len(res_pose.keypoints) > 0:
        boxes = res_pose.boxes.xyxy.cpu().numpy()
        for box in boxes:
            x1, y1, x2, y2 = box
            area = (x2 - x1) * (y2 - y1)
            score_accion = area

            if balon_box is not None:
                cx_b = (balon_box[0] + balon_box[2]) / 2
                cy_b = (balon_box[1] + balon_box[3]) / 2
                cx_p = (x1 + x2) / 2
                cy_p = (y1 + y2) / 2
                dist = np.sqrt((cx_p - cx_b)**2 + (cy_p - cy_b)**2)
                score_accion += (1.0 / (dist + 1e-5)) * 100000

            candidatos.append({'box': [x1, y1, x2, y2], 'score': score_accion})

    if not candidatos:
        return [w_img * 0.1, h_img * 0.1, w_img * 0.9, h_img * 0.9]

    candidatos.sort(key=lambda x: x['score'], reverse=True)
    box_principal = candidatos[0]['box']

    if len(candidatos) > 1 and candidatos[1]['score'] > candidatos[0]['score'] * 0.6:
        box2 = candidatos[1]['box']
        if abs((box_principal[0] + box_principal[2])/2 - (box2[0] + box2[2])/2) < w_img * 0.4:
            box_principal = [
                min(box_principal[0], box2[0]), min(box_principal[1], box2[1]),
                max(box_principal[2], box2[2]), max(box_principal[3], box2[3])
            ]

    return box_principal

def aplicar_marcas_de_agua(img_base, ancho_target, alto_target):
    img_rgba = img_base.convert("RGBA")

    # 1. Logo Transparente - Esquina Superior Izquierda (Margen 30px, Opacidad 30%)
    if os.path.exists(RUTA_LOGO_TRANSPARENTE):
        wm_trans = Image.open(RUTA_LOGO_TRANSPARENTE).convert("RGBA").resize((270, 270), Image.Resampling.LANCZOS)
        r, g, b, alpha = wm_trans.split()
        alpha = alpha.point(lambda p: int(p * 0.30))
        wm_trans.putalpha(alpha)
        img_rgba.alpha_composite(wm_trans, dest=(30, 30))

    # 2. Logo Normal - Centrado Inferior (-5% margen)
    if os.path.exists(RUTA_LOGO_NORMAL):
        wm_norm = Image.open(RUTA_LOGO_NORMAL).convert("RGBA").resize((90, 90), Image.Resampling.LANCZOS)
        pos_x = int((ancho_target - 90) / 2)
        pos_y = int(alto_target - 90 - (alto_target * 0.05))
        img_rgba.alpha_composite(wm_norm, dest=(pos_x, pos_y))

    return img_rgba.convert("RGB")

def procesar_fotografia(ruta_origen, ruta_destino, ruta_watermark=None, umbral_blur=75.0):
    tiempo_inicio = time.time()
    
    # 1. Corregir orientación EXIF nativa
    img_pil_raw = Image.open(ruta_origen)
    img_pil = ImageOps.exif_transpose(img_pil_raw)
    w_orig, h_orig = img_pil.size
    
    imagen_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    if imagen_cv is None:
        raise ValueError("No se pudo cargar la imagen de origen.")

    # 2. Obtener Sujeto Principal
    box_sujeto = obtener_sujeto_principal(imagen_cv)

    # 3. Evaluar Blur enfocado en el Sujeto (Descartes estrictos con umbral 75.0)
    varianza = calcular_varianza_laplaciana(imagen_cv, box_sujeto)
    if varianza < umbral_blur:
        return {
            "nombre": os.path.basename(ruta_origen),
            "es_nitida": False,
            "varianza": round(varianza, 2),
            "estado": "descartada",
            "tiempo_ms": int((time.time() - tiempo_inicio) * 1000)
        }

    # 4. Proporción Objetivo (1:1 o 4:5)
    ratio_orig = w_orig / float(h_orig)
    if 0.95 <= ratio_orig <= 1.05:
        aspecto_target = 1.0
        ancho_target, alto_target = 1080, 1080
    else:
        aspecto_target = 4.0 / 5.0  # 0.8
        ancho_target, alto_target = 1080, 1350

    # 5. Encuadre Matemáticamente Rígido (Cero deformación)
    x1, y1, x2, y2 = box_sujeto
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0

    ancho_sujeto = (x2 - x1) * 1.35
    alto_sujeto = (y2 - y1) * 1.35

    if ancho_sujeto / alto_sujeto > aspecto_target:
        ancho_crop = ancho_sujeto
        alto_crop = ancho_crop / aspecto_target
    else:
        alto_crop = alto_sujeto
        ancho_crop = alto_crop * aspecto_target

    # Limitar el tamaño de la caja si excede las dimensiones de la imagen original
    if ancho_crop > w_orig:
        ancho_crop = w_orig
        alto_crop = ancho_crop / aspecto_target
    if alto_crop > h_orig:
        alto_crop = h_orig
        ancho_crop = alto_crop * aspecto_target

    crop_x1 = cx - (ancho_crop / 2.0)
    crop_y1 = cy - (alto_crop / 2.0)

    # Ajustar centro si se sale de los bordes
    if crop_x1 < 0:
        crop_x1 = 0
    elif crop_x1 + ancho_crop > w_orig:
        crop_x1 = w_orig - ancho_crop

    if crop_y1 < 0:
        crop_y1 = 0
    elif crop_y1 + alto_crop > h_orig:
        crop_y1 = h_orig - alto_crop

    crop_x2 = crop_x1 + ancho_crop
    crop_y2 = crop_y1 + alto_crop

    img_recortada = img_pil.crop((int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)))

    # 6. Escalado + Enfoque Post-Escalado
    img_resized = img_recortada.resize((ancho_target, alto_target), Image.Resampling.LANCZOS)
    img_enfocada = aplicar_enfoque_post_escalado(img_resized)

    # 7. Filtros de Color y Marcas de Agua
    img_color = aplicar_curva_luz_y_filtros(img_enfocada)
    img_final = aplicar_marcas_de_agua(img_color, ancho_target, alto_target)

    # 8. Guardado con Path Nactivo
    ruta_salida = Path(ruta_destino).resolve()
    srgb_profile = ImageCms.createProfile("sRGB")
    
    img_final.save(
        str(ruta_salida), 
        format="PNG", 
        icc_profile=ImageCms.ImageCmsProfile(srgb_profile).tobytes()
    )

    return {
        "nombre": os.path.basename(ruta_origen),
        "es_nitida": True,
        "varianza": round(varianza, 2),
        "estado": "procesada",
        "tiempo_ms": int((time.time() - tiempo_inicio) * 1000)
    }