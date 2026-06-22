import asyncio
import cv2
import numpy as np
from insightface.app import FaceAnalysis
import base64

app = FaceAnalysis(name="buffalo_l", root="./insightface_models", providers=["CPUExecutionProvider"])
app.prepare(ctx_id=-1, det_size=(640, 640))

def _decode_image(image_data: str) -> np.ndarray:
    raw = base64.b64decode(image_data)
    arr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def detect_face(image_data: str) -> dict | None:
    img = _decode_image(image_data)
    if img is None:
        return None
    faces = app.get(img)
    if not faces:
        return None
    face = max(faces, key=lambda f: f.det_score)
    if face.det_score < 0.7:
        return None
    h, w = img.shape[:2]
    x1, y1, x2, y2 = face.bbox.astype(int)
    face_w = x2 - x1
    face_h = y2 - y1
    if face_w < 80 or face_h < 80:
        return None
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w, x2)
    y2 = min(h, y2)
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "score": float(face.det_score),
        "embedding": face.embedding.tolist(),
    }

def get_embedding(image_data: str) -> list[float] | None:
    result = detect_face(image_data)
    if result is None:
        return None
    return result["embedding"]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    a_norm = a_arr / np.linalg.norm(a_arr)
    b_norm = b_arr / np.linalg.norm(b_arr)
    return float(np.dot(a_norm, b_norm))

def average_embeddings(embeddings: list[list[float]]) -> list[float]:
    if not embeddings:
        return []
    avg = np.mean(embeddings, axis=0)
    return (avg / np.linalg.norm(avg)).tolist()

# ── Async wrappers (offload CPU work to thread pool) ────────────

async def detect_face_async(image_data: str) -> dict | None:
    return await asyncio.to_thread(detect_face, image_data)

async def get_embedding_async(image_data: str) -> list[float] | None:
    return await asyncio.to_thread(get_embedding, image_data)

async def cosine_similarity_async(a: list[float], b: list[float]) -> float:
    return await asyncio.to_thread(cosine_similarity, a, b)
