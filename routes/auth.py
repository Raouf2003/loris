import jwt
import bcrypt as _bcrypt
from fastapi import APIRouter
from starlette.responses import JSONResponse
from datetime import datetime, timedelta, timezone
from config import settings
from database import db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: dict):
    username = body.get("username")
    password = body.get("password")
    if not username or not password:
        return JSONResponse(status_code=400, content={"error": "Username and password required"})

    admin = await db.admins.find_one({"username": username})
    if not admin or not _bcrypt.checkpw(password.encode(), admin["password"].encode()):
        return JSONResponse(status_code=401, content={"error": "Invalid credentials"})

    token = jwt.encode(
        {
            "id": str(admin["_id"]),
            "username": admin["username"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"token": token, "username": admin["username"]}


@router.get("/admin")
async def get_admin():
    admin = await db.admins.find_one({"username": "admin"})
    if not admin:
        return {"username": "admin"}
    return {"_id": str(admin["_id"]), "username": admin["username"]}


@router.put("/admin")
async def update_admin(body: dict):
    admin = await db.admins.find_one({"username": "admin"})
    if not admin:
        return JSONResponse(status_code=404, content={"error": "Admin not found"})

    update = {}
    if "username" in body and body["username"]:
        update["username"] = body["username"]
    if "password" in body and body["password"]:
        update["password"] = _bcrypt.hashpw(
            body["password"].encode(), _bcrypt.gensalt()
        ).decode()

    if update:
        await db.admins.update_one({"_id": admin["_id"]}, {"$set": update})

    result = await db.admins.find_one({"_id": admin["_id"]})
    return {"_id": str(result["_id"]), "username": result["username"]}
