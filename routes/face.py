from fastapi import APIRouter
from starlette.responses import JSONResponse as JR
from bson import ObjectId
from database import db
from face_service import detect_face_async, average_embeddings, cosine_similarity_async
from config import settings

def J(status: int, msg: str):
    return JR(status_code=status, content={"error": msg})

router = APIRouter(prefix="/api/face", tags=["face"])

@router.post("/register")
async def register_face(body: dict):
    employee_id = body.get("employeeId")
    images = body.get("images", [])
    if not employee_id:
        return J(400, "employeeId required")
    if not images or not isinstance(images, list):
        return J(400, "At least 1 image required")

    emp = await db.employees.find_one({"_id": ObjectId(employee_id)})
    if not emp:
        return J(404, "Employee not found")

    embeddings = []
    debug_scores = []

    for img in images:
        result = await detect_face_async(img)
        if result is None:
            debug_scores.append(0)
            continue
        debug_scores.append(result["score"])
        embeddings.append(result["embedding"])

    if not embeddings:
        return JR(status_code=400, content={"error": "No face detected in any image", "debug": {"scores": debug_scores}})

    if len(embeddings) < 3:
        return JR(
            status_code=400,
            content={
                "error": f"Only {len(embeddings)}/5 images had detectable faces. Please retake.",
                "debug": {"scores": debug_scores},
            },
        )

    avg = average_embeddings(embeddings)
    await db.employees.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"embedding": avg, "hasFace": True}}
    )

    return {
        "success": True,
        "message": f"Face registered with {len(embeddings)} images",
        "employee": {"id": employee_id, "fullName": emp["fullName"], "hasFace": True},
    }

@router.post("/verify")
async def verify_face(body: dict):
    image = body.get("image")
    if not image:
        return J(400, "Image required")

    result = await detect_face_async(image)
    if result is None:
        return {"matched": False, "error": "No face detected"}

    emb = result["embedding"]
    employees = await db.employees.find({"hasFace": True}).to_list(None)
    if not employees:
        return {"matched": False, "error": "No registered employees"}

    best_match = None
    best_score = -1.0
    for emp in employees:
        if not emp.get("embedding"):
            continue
        sim = await cosine_similarity_async(emb, emp["embedding"])
        if sim > best_score:
            best_score = sim
            best_match = emp

    if best_score < settings.face_threshold:
        return {"matched": False, "score": best_score, "error": "Face not recognized"}

    return {
        "matched": True,
        "employee": {"id": str(best_match["_id"]), "fullName": best_match["fullName"], "employeeNumber": best_match["employeeNumber"]},
        "score": best_score,
    }
