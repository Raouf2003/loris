from fastapi import APIRouter
from starlette.responses import JSONResponse as JR
from database import db

def J(status: int, msg: str):
    return JR(status_code=status, content={"error": msg})

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
@router.get("/")
async def get_settings():
    s = await db.settings.find_one()
    if not s:
        s = {
            "morningShift": {"start": "08:00", "end": "12:00"},
            "afternoonShift": {"start": "13:00", "end": "17:00"},
        }
        await db.settings.insert_one(s)
    s["_id"] = str(s.pop("_id"))
    return s

@router.put("")
@router.put("/")
async def update_settings(body: dict):
    s = await db.settings.find_one()
    if not s:
        s = {}
        await db.settings.insert_one(s)

    update = {}
    if "morningShift" in body:
        ms = body["morningShift"]
        merged = s.get("morningShift", {"start": "08:00", "end": "12:00"})
        if isinstance(ms, dict):
            if "start" in ms: merged["start"] = ms["start"]
            if "end" in ms: merged["end"] = ms["end"]
        update["morningShift"] = merged
    if "afternoonShift" in body:
        a = body["afternoonShift"]
        merged = s.get("afternoonShift", {"start": "13:00", "end": "17:00"})
        if isinstance(a, dict):
            if "start" in a: merged["start"] = a["start"]
            if "end" in a: merged["end"] = a["end"]
        update["afternoonShift"] = merged

    if update:
        await db.settings.update_one({}, {"$set": update})

    result = await db.settings.find_one()
    result["_id"] = str(result.pop("_id"))
    return result
