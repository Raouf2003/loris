from fastapi import APIRouter
from starlette.responses import JSONResponse as JR
from bson import ObjectId, errors as bson_errors
from database import db
from face_service import detect_face_async, cosine_similarity_async
from config import settings
import pytz
from datetime import datetime, timedelta

TZ = pytz.timezone("Africa/Algiers")

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

def _now_tz():
    return datetime.now(TZ)

def _today():
    n = _now_tz()
    return f"{n.year}-{n.month:02d}-{n.day:02d}"

def _now_str():
    n = _now_tz()
    return f"{n.hour:02d}:{n.minute:02d}"

def _now_minutes():
    n = _now_tz()
    return n.hour * 60 + n.minute

async def _get_settings():
    s = await db.settings.find_one()
    if not s:
        s = {
            "morningShift": {"start": "08:00", "end": "12:00"},
            "afternoonShift": {"start": "13:00", "end": "17:00"},
        }
        await db.settings.insert_one(s)
    return s

def _to_min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m

def _current_period(s: dict) -> str | None:
    now = _now_minutes()
    ms = s.get("morningShift", {})
    as_ = s.get("afternoonShift", {})
    ms_start = _to_min(ms.get("start", "08:00"))
    ms_end = _to_min(ms.get("end", "12:00"))
    as_start = _to_min(as_.get("start", "13:00"))
    as_end = _to_min(as_.get("end", "17:00"))
    if ms_start <= now < ms_end:
        return "morning"
    if as_start <= now < as_end:
        return "afternoon"
    return None

def J(status: int, msg: str):
    return JR(status_code=status, content={"error": msg})

async def _identify(base64_image: str) -> dict:
    result = await detect_face_async(base64_image)
    if result is None:
        return {"error": "no_face"}
    emb = result["embedding"]
    employees = await db.employees.find({"hasFace": True}).to_list(None)
    if not employees:
        return {"error": "no_employees"}
    best = None
    best_s = -1.0
    for emp in employees:
        if not emp.get("embedding"):
            continue
        sim = await cosine_similarity_async(emb, emp["embedding"])
        if sim > best_s:
            best_s = sim
            best = emp
    if best_s < settings.face_threshold:
        return {"error": "not_recognized", "score": best_s}
    return {"employee": best, "score": best_s}

async def _get_attendance(employee_id: str, date: str):
    return await db.attendances.find_one({"employeeId": employee_id, "date": date})

@router.post("/checkin")
async def checkin(body: dict):
    image = body.get("image")
    if not image:
        return J(400, "Image required")

    ident = await _identify(image)
    if "error" in ident:
        if ident["error"] == "no_face":
            return J(400, "No face detected, try again")
        if ident["error"] == "no_employees":
            return J(400, "No registered employees")
        return J(400, "Face not recognized")

    emp = ident["employee"]
    s = await _get_settings()
    period = _current_period(s)
    if period is None:
        return J(400, "Outside working hours")

    today = _today()
    now_t = _now_str()
    att = await _get_attendance(str(emp["_id"]), today)

    if period == "morning":
        if att and att.get("checkInAM"):
            return J(400, "Already checked in (morning)")
        await db.attendances.update_one(
            {"employeeId": str(emp["_id"]), "date": today},
            {"$set": {"checkInAM": now_t}, "$setOnInsert": {"status": "present"}},
            upsert=True,
        )
    else:
        if att and att.get("checkInPM"):
            return J(400, "Already checked in (afternoon)")
        await db.attendances.update_one(
            {"employeeId": str(emp["_id"]), "date": today},
            {"$set": {"checkInPM": now_t}, "$setOnInsert": {"status": "present"}},
            upsert=True,
        )

    return {
        "message": f"Checked in ({period})",
        "employee": {"_id": str(emp["_id"]), "fullName": emp["fullName"], "employeeNumber": emp["employeeNumber"]},
        "checkInTime": now_t,
        "period": period,
    }

@router.post("/checkout")
async def checkout(body: dict):
    image = body.get("image")
    if not image:
        return J(400, "Image required")

    ident = await _identify(image)
    if "error" in ident:
        if ident["error"] == "no_face":
            return J(400, "No face detected, try again")
        if ident["error"] == "no_employees":
            return J(400, "No registered employees")
        return J(400, "Face not recognized")

    emp = ident["employee"]
    s = await _get_settings()
    period = _current_period(s)
    if period is None:
        return J(400, "Outside working hours")

    today = _today()
    now_t = _now_str()
    att = await _get_attendance(str(emp["_id"]), today)

    if not att:
        return J(400, "Not checked in")

    if period == "morning":
        if att.get("checkOutAM"):
            return J(400, "Already checked out (morning)")
        if not att.get("checkInAM"):
            return J(400, "Not checked in (morning)")
        await db.attendances.update_one(
            {"_id": att["_id"]},
            {"$set": {"checkOutAM": now_t}},
        )
    else:
        if att.get("checkOutPM"):
            return J(400, "Already checked out (afternoon)")
        if not att.get("checkInPM"):
            return J(400, "Not checked in (afternoon)")
        await db.attendances.update_one(
            {"_id": att["_id"]},
            {"$set": {"checkOutPM": now_t}},
        )

    return {
        "message": f"Checked out ({period})",
        "employee": {"_id": str(emp["_id"]), "fullName": emp["fullName"], "employeeNumber": emp["employeeNumber"]},
        "checkOutTime": now_t,
        "period": period,
    }

@router.get("/today")
async def today_attendance():
    date = _today()
    records = await db.attendances.find({"date": date}).to_list(None)
    result = []
    for r in records:
        emp = None
        try:
            emp = await db.employees.find_one({"_id": ObjectId(r["employeeId"])})
        except (bson_errors.InvalidId, TypeError):
            pass
        result.append({
            "_id": str(r["_id"]),
            "employeeId": {
                "_id": r["employeeId"],
                "fullName": emp["fullName"] if emp else "N/A",
                "employeeNumber": emp["employeeNumber"] if emp else "N/A"
            },
            "date": r["date"],
            "checkInAM": r.get("checkInAM"),
            "checkOutAM": r.get("checkOutAM"),
            "checkInPM": r.get("checkInPM"),
            "checkOutPM": r.get("checkOutPM"),
            "status": r.get("status", "absent"),
            "totalHours": r.get("totalHours", 0),
        })
    return result

@router.get("/working-now")
async def working_now():
    date = _today()
    query = {
        "date": date,
        "$or": [
            {"checkInAM": {"$exists": True, "$ne": None}, "checkOutAM": {"$exists": False}},
            {"checkInPM": {"$exists": True, "$ne": None}, "checkOutPM": {"$exists": False}},
        ],
    }

    records = await db.attendances.find(query).to_list(None)
    result = []
    for r in records:
        emp = None
        try:
            emp = await db.employees.find_one({"_id": ObjectId(r["employeeId"])})
        except (bson_errors.InvalidId, TypeError):
            pass
        result.append({
            "_id": str(r["_id"]),
            "employeeId": {
                "_id": r["employeeId"],
                "fullName": emp["fullName"] if emp else "N/A",
                "employeeNumber": emp["employeeNumber"] if emp else "N/A"
            },
            "checkInAM": r.get("checkInAM"),
            "checkInPM": r.get("checkInPM"),
        })
    return result
