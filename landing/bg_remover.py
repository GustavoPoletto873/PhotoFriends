"""
Lightweight background removal using ONNX Runtime + U2-Net tiny (u2netp).
Replaces backgroundremover/rembg without requiring PyTorch.
Model: ~4.7MB  |  Runtime memory: ~150MB  |  Works on Render free tier.
"""
import io
import os
import urllib.request

import numpy as np
from PIL import Image

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'u2netp.onnx')
MODEL_URLS = [
    'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx',
    'https://github.com/nadermx/backgroundremover/raw/main/models/u2netp.onnx',
]

_session = None  # cached at module level — loaded once, reused for every request


def download_model():
    """Download u2netp.onnx if not present. Called during build or lazily."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(MODEL_PATH):
        print(f'[bg_remover] Modelo já existe: {MODEL_PATH}')
        return
    print(f'[bg_remover] Baixando u2netp.onnx (~4.7MB)...')
    last_err = None
    for url in MODEL_URLS:
        try:
            urllib.request.urlretrieve(url, MODEL_PATH)
            print(f'[bg_remover] Modelo salvo em {MODEL_PATH}')
            return
        except Exception as e:
            last_err = e
            print(f'[bg_remover] Falha ao baixar de {url}: {e}')
    raise RuntimeError(f'Não foi possível baixar o modelo: {last_err}')


def _get_session():
    global _session
    if _session is not None:
        return _session

    if not os.path.exists(MODEL_PATH):
        print('[bg_remover] Modelo ausente, tentando baixar agora...')
        download_model()

    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 2
    _session = ort.InferenceSession(
        MODEL_PATH,
        sess_options=opts,
        providers=['CPUExecutionProvider'],
    )
    return _session


def _preprocess(img: Image.Image, size: int = 320) -> np.ndarray:
    img = img.convert('RGB').resize((size, size), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    arr = arr / arr.max() if arr.max() > 0 else arr
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    return arr.transpose(2, 0, 1)[None]  # (1, 3, H, W)


def _postprocess(pred: np.ndarray, orig_size: tuple) -> Image.Image:
    mask = pred[0, 0]
    lo, hi = mask.min(), mask.max()
    mask = (mask - lo) / (hi - lo + 1e-8)
    mask_uint8 = (mask * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(mask_uint8).resize(orig_size, Image.LANCZOS)


def remove_background(img_bytes: bytes) -> bytes:
    """Remove background from image bytes. Returns PNG bytes with alpha."""
    session = _get_session()
    img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
    orig_size = img.size

    inp = _preprocess(img)
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: inp})

    mask = _postprocess(outputs[0], orig_size)

    result = img.copy()
    result.putalpha(mask)

    out = io.BytesIO()
    result.save(out, format='PNG')
    return out.getvalue()


