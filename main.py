import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import bcrypt as _bcrypt
from contextlib import asynccontextmanager

from config import settings
from database import db, init_db
from auth_middleware import admin_required

from routes import auth, employees, attendance, face, reports, settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        existing = await db.admins.find_one({"username": "admin"})
        if not existing:
            await db.admins.insert_one({
                "username": "admin",
                "password": _bcrypt.hashpw(b"admin123", _bcrypt.gensalt()).decode(),
            })
        print("Server ready")
    except Exception as e:
        print(f"Startup error: {e}")
        raise
    yield


app = FastAPI(lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(admin_required)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(face.router)
app.include_router(reports.router)
app.include_router(settings_router.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.port))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
