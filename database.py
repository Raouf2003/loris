from motor.motor_asyncio import AsyncIOMotorClient
from config import settings

client = AsyncIOMotorClient(settings.mongodb_uri)
db = client.kiosk


async def init_db():
    await db.admins.create_index("username", unique=True)
    await db.employees.create_index("employeeNumber", unique=True)
    await db.attendances.create_index(
        [("employeeId", 1), ("date", 1)], unique=True
    )
