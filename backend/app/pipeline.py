import os
import time
import cv2
import numpy as np
from PIL import Image, ImageCms, ImageEnhance, ImageDraw, ImageFont, ImageOps
from pillow_heif import register_heif_opener
import rawpy
import torch
from ultralytics import YOLO

register_heif_opener()

_torch_load = torch.load
def _safe_torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _torch_load(*args, **kwargs)
torch.load = _safe_torch_load

modelo_pose = YOLO("yolov8n-pose.pt")
modelo_objetos = YOLO("yolov8n.pt")

RUTA_LOGO_NORMAL = r"C:\Users\Romm\Pictures\EP_Logo_circle_HD .png"
RUTA_LOGO_TRANSPARENTE = r"C:\Users\Romm\Pictures\Epic_Play_Watermark_Transparent_HQ.png"

def calcular_varianza_laplaciana(imagen_cv):
    gris = cv2.cvtColor(imagen_cv, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gris, cv2.CV_64F).var()

def aplicar_revelado_rapido(img_pil):
    enhancer_contrast = ImageEnhance.Contrast(img_pil)
    img_contrast = enhancer_contrast.enhance(1.12)

    enhancer_color = ImageEnhance.Color(img_contrast)
    return enhancer_color.enhance(1.15)

def cargar_imagen_universal(ruta_archivo):
    ext = os.path.splitext(ruta_archivo)[1].lower()
    if ext in ['.cr3', '.cr2', '.nef', '.arw', '.dng']:
        with rawpy.imread(ruta_archivo) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True, 
                half_size=False, 
                no_auto_bright=True,
                output_bps=8,
                user_flip=None
            )
            img_pil = Image.fromarray(rgb)
            return ImageOps.exif_transpose(img_pil)
    else:
        img_pil = Image.open(ruta_archivo)
        return ImageOps.exif_transpose(img_pil).convert("RGB")

def obtener_sujeto_principal(imagen_cv):
    res_pose = modelo_pose(imagen_cv, verbose=False)[0]
    res_obj = modelo_objetos(imagen_cv, verbose=False)[0]

    h_img, w_img, _ = imagen_cv.shape
    balon_box = None
    for box in res_obj.boxes:
        if int(box.cls[0]) == 32:
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
                cx_b, cy_b = (balon_box[0] + balon_box[2]) / 2, (balon_box[1] + balon_box[3]) / 2
                cx_p, cy_p = (x1 + x2) / 2, (y1 + y2) / 2
                distancia = np.sqrt((cx_p - cx_b)**2 + (cy_p - cy_b)**2)
                score_accion += (1.0 / (distancia + 1e-5)) * 100000
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

def recortar_proporcional_exacto(img_pil, cx, cy, x1, y1, x2, y2, aspecto_target):
    w_orig, h_orig = img_pil.size

    w_box = (x2 - x1) * 1.40
    h_box = (y2 - y1) * 1.40

    if w_box / h_box > aspecto_target:
        ancho_crop = w_box
        alto_crop = ancho_crop / aspecto_target
    else:
        alto_crop = h_box
        ancho_crop = alto_crop * aspecto_target

    if alto_crop > h_orig:
        alto_crop = h_orig
        ancho_crop = alto_crop * aspecto_target

    if ancho_crop > w_orig:
        ancho_crop = w_orig
        alto_crop = ancho_crop / aspecto_target

    crop_x1 = max(0, min(w_orig - ancho_crop, cx - ancho_crop / 2))
    crop_y1 = max(0, min(h_orig - alto_crop, cy - alto_crop / 2))
    crop_x2 = crop_x1 + ancho_crop
    crop_y2 = crop_y1 + alto_crop

    return img_pil.crop((int(crop_x1), int(crop_y1), int(crop_x2), int(crop_y2)))

def aplicar_marcas_de_agua_estandar(img_base):
    w, h = img_base.size
    img_rgba = img_base.convert("RGBA")

    if os.path.exists(RUTA_LOGO_TRANSPARENTE):
        size_trans = int(w * 0.25)
        wm_trans = Image.open(RUTA_LOGO_TRANSPARENTE).convert("RGBA")
        wm_trans = wm_trans.resize((size_trans, size_trans), Image.Resampling.LANCZOS)
        r, g, b, alpha = wm_trans.split()
        alpha = alpha.point(lambda p: int(p * 0.30))
        wm_trans.putalpha(alpha)
        pos_margin = int(w * 0.03)
        img_rgba.alpha_composite(wm_trans, dest=(pos_margin, pos_margin))

    if os.path.exists(RUTA_LOGO_NORMAL):
        size_norm = int(w * 0.083)
        wm_norm = Image.open(RUTA_LOGO_NORMAL).convert("RGBA")
        wm_norm = wm_norm.resize((size_norm, size_norm), Image.Resampling.LANCZOS)
        pos_x_norm = int((w - size_norm) / 2)
        pos_y_norm = int(h - size_norm - (h * 0.05))
        img_rgba.alpha_composite(wm_norm, dest=(pos_x_norm, pos_y_norm))

    return img_rgba.convert("RGB")

def aplicar_marca_agua_galeria_web(img_base):
    w, h = img_base.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cell_w, cell_h = int(w * 0.35), int(h * 0.18)
    tile = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)

    try:
        font = ImageFont.truetype("arial.ttf", int(cell_h * 0.22))
    except:
        font = ImageFont.load_default()

    draw.text((10, 10), "@myepicplay", fill=(255, 255, 255, 75), font=font)

    if os.path.exists(RUTA_LOGO_NORMAL):
        logo_sm = Image.open(RUTA_LOGO_NORMAL).convert("RGBA")
        l_size = int(cell_h * 0.35)
        logo_sm = logo_sm.resize((l_size, l_size), Image.Resampling.LANCZOS)
        r, g, b, a = logo_sm.split()
        a = a.point(lambda p: int(p * 0.40))
        logo_sm.putalpha(a)
        tile.paste(logo_sm, (10, int(cell_h * 0.45)), logo_sm)

    tile_rotated = tile.rotate(35, expand=True, resample=Image.Resampling.BICUBIC)
    tw, th = tile_rotated.size

    for x in range(-w, w * 2, tw):
        for y in range(-h, h * 2, th):
            overlay.paste(tile_rotated, (x, y), tile_rotated)

    img_rgba = img_base.convert("RGBA")
    img_con_patron = Image.alpha_composite(img_rgba, overlay).convert("RGB")
    return aplicar_marcas_de_agua_estandar(img_con_patron)

def procesar_fotografia(ruta_origen, base_dir_salida, umbral_blur=25.0, formatos=None):
    tiempo_inicio = time.time()
    
    # Normalizar la lista de formatos seleccionados desde el frontend
    if formatos is None or len(formatos) == 0:
        formatos_activos = ['instagram', 'galeria_web', 'impresion_4x6', 'credencial', 'ipad']
    else:
        formatos_activos = [f.lower() for f in formatos]

    img_raw = cargar_imagen_universal(ruta_origen)
    imagen_cv = cv2.cvtColor(np.array(img_raw), cv2.COLOR_RGB2BGR)

    varianza = calcular_varianza_laplaciana(imagen_cv)
    if varianza < umbral_blur:
        return {
            "nombre": os.path.basename(ruta_origen),
            "es_nitida": False,
            "varianza": round(varianza, 2),
            "estado": "descartada",
            "tiempo_ms": int((time.time() - tiempo_inicio) * 1000)
        }

    img_master = aplicar_revelado_rapido(img_raw)

    x1, y1, x2, y2 = obtener_sujeto_principal(imagen_cv)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2

    srgb_profile = ImageCms.createProfile("sRGB")
    nombre_base = os.path.splitext(os.path.basename(ruta_origen))[0]

    # Variable base para Instagram/Web si se requiere
    img_ig = None

    # A. Instagram (4:5 -> 1080x1350)
    if 'instagram' in formatos_activos or 'galeria_web' in formatos_activos or 'web' in formatos_activos:
        aspecto_ig = 4.0 / 5.0
        img_ig = recortar_proporcional_exacto(img_master, cx, cy, x1, y1, x2, y2, aspecto_ig)

        if 'instagram' in formatos_activos:
            img_ig_res = img_ig.resize((1080, 1350), Image.Resampling.LANCZOS)
            img_ig_wm = aplicar_marcas_de_agua_estandar(img_ig_res)
            ruta_ig = os.path.join(base_dir_salida, "instagram", f"{nombre_base}_ig.png")
            os.makedirs(os.path.dirname(ruta_ig), exist_ok=True)
            img_ig_wm.save(ruta_ig, "PNG", icc_profile=ImageCms.ImageCmsProfile(srgb_profile).tobytes())

    # B. Galería Web (800x1000 + Marca de Agua de Protección)
    if 'galeria_web' in formatos_activos or 'web' in formatos_activos:
        if img_ig is None:
            aspecto_ig = 4.0 / 5.0
            img_ig = recortar_proporcional_exacto(img_master, cx, cy, x1, y1, x2, y2, aspecto_ig)
        img_web = img_ig.resize((800, 1000), Image.Resampling.LANCZOS)
        img_web_protected = aplicar_marca_agua_galeria_web(img_web)
        ruta_web = os.path.join(base_dir_salida, "galeria_web", f"{nombre_base}_web.jpg")
        os.makedirs(os.path.dirname(ruta_web), exist_ok=True)
        img_web_protected.save(ruta_web, "JPEG", quality=50)

    # C. Impresión (2:3 -> 1200x1800 para 4x6 pulg)
    if 'impresion_4x6' in formatos_activos or 'impresion' in formatos_activos or '4x6' in formatos_activos:
        aspecto_print = 2.0 / 3.0
        img_print = recortar_proporcional_exacto(img_master, cx, cy, x1, y1, x2, y2, aspecto_print)
        img_print = img_print.resize((1200, 1800), Image.Resampling.LANCZOS)
        img_print_wm = aplicar_marcas_de_agua_estandar(img_print)
        ruta_print = os.path.join(base_dir_salida, "impresion_4x6", f"{nombre_base}_print.jpg")
        os.makedirs(os.path.dirname(ruta_print), exist_ok=True)
        img_print_wm.save(ruta_print, "JPEG", quality=95)

    # D. Credencial (2.1 x 3.4 -> 630x1020px)
    if 'credencial' in formatos_activos or 'sticker' in formatos_activos:
        aspecto_cred = 2.1 / 3.4
        img_cred = recortar_proporcional_exacto(img_master, cx, cy, x1, y1, x2, y2, aspecto_cred)
        img_cred = img_cred.resize((630, 1020), Image.Resampling.LANCZOS)
        img_cred_wm = aplicar_marcas_de_agua_estandar(img_cred)
        ruta_cred = os.path.join(base_dir_salida, "credencial", f"{nombre_base}_credencial.jpg")
        os.makedirs(os.path.dirname(ruta_cred), exist_ok=True)
        img_cred_wm.save(ruta_cred, "JPEG", quality=90)

    # E. iPad (3:4 -> 900x1200px)
    if 'ipad' in formatos_activos or 'tablet' in formatos_activos:
        aspecto_ipad = 3.0 / 4.0
        img_ipad = recortar_proporcional_exacto(img_master, cx, cy, x1, y1, x2, y2, aspecto_ipad)
        img_ipad = img_ipad.resize((900, 1200), Image.Resampling.LANCZOS)
        img_ipad_wm = aplicar_marcas_de_agua_estandar(img_ipad)
        ruta_ipad = os.path.join(base_dir_salida, "ipad", f"{nombre_base}_ipad.jpg")
        os.makedirs(os.path.dirname(ruta_ipad), exist_ok=True)
        img_ipad_wm.save(ruta_ipad, "JPEG", quality=85)

    return {
        "nombre": os.path.basename(ruta_origen),
        "es_nitida": True,
        "varianza": round(varianza, 2),
        "estado": "procesada",
        "tiempo_ms": int((time.time() - tiempo_inicio) * 1000)
    }