import jwt
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from config import settings

async def admin_required(request: Request, call_next):
    path = request.url.path.rstrip("/")
    if path in ("/api/auth/login", "/api/attendance/checkin", "/api/attendance/checkout", "/api/attendance/working-now", "/api/face/verify"):
        return await call_next(request)

    if request.method == "GET" and path == "/api/settings":
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "No token provided"})

    token = auth.split(" ")[1]
    try:
        decoded = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        request.state.admin = decoded
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

    return await call_next(request)
