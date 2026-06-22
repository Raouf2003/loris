from fastapi import APIRouter
from starlette.responses import JSONResponse as JR
from bson import ObjectId
from datetime import datetime, timezone
from database import db


def J(status: int, msg: str):
    return JR(status_code=status, content={"error": msg})


router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("")
@router.get("/")
async def list_employees():
    employees = await db.employees.find().sort("createdAt", -1).to_list(None)
    result = []
    for e in employees:
        doc = dict(e)
        doc["_id"] = str(doc.pop("_id"))
        doc.pop("embedding", None)
        result.append(doc)
    return result


@router.get("/{eid}")
async def get_employee(eid: str):
    emp = await db.employees.find_one({"_id": ObjectId(eid)})
    if not emp:
        return J(404, "Employee not found")
    doc = dict(emp)
    doc["_id"] = str(doc.pop("_id"))
    return doc


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_employee(body: dict):
    full_name = body.get("fullName")
    employee_number = body.get("employeeNumber")
    if not full_name or not employee_number:
        return J(400, "fullName and employeeNumber required")

    existing = await db.employees.find_one({"employeeNumber": employee_number})
    if existing:
        return JR(status_code=409, content={"error": "Employee number already exists"})

    result = await db.employees.insert_one({
        "fullName": full_name,
        "employeeNumber": employee_number,
        "embedding": [],
        "hasFace": False,
        "createdAt": datetime.now(timezone.utc),
    })
    emp = await db.employees.find_one({"_id": result.inserted_id})
    doc = dict(emp)
    doc["_id"] = str(doc.pop("_id"))
    return doc


@router.put("/{eid}")
async def update_employee(eid: str, body: dict):
    update = {}
    if "fullName" in body:
        update["fullName"] = body["fullName"]
    if "employeeNumber" in body:
        existing = await db.employees.find_one({
            "employeeNumber": body["employeeNumber"],
            "_id": {"$ne": ObjectId(eid)},
        })
        if existing:
            return JR(status_code=409, content={"error": "Employee number already exists"})
        update["employeeNumber"] = body["employeeNumber"]
    if not update:
        return J(400, "Nothing to update")

    result = await db.employees.find_one_and_update(
        {"_id": ObjectId(eid)},
        {"$set": update},
        return_document=True,
    )
    if not result:
        return J(404, "Employee not found")
    doc = dict(result)
    doc["_id"] = str(doc.pop("_id"))
    return doc


@router.delete("/{eid}")
async def delete_employee(eid: str):
    result = await db.employees.find_one_and_delete({"_id": ObjectId(eid)})
    if not result:
        return J(404, "Employee not found")
    await db.attendances.delete_many({"employeeId": eid})
    return {"message": "Employee deleted"}
