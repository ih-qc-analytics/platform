import asyncio
from sqlalchemy import text
from app.database import SessionLocal

async def main():
    async with SessionLocal() as session:
        result = await session.execute(text(
            "SELECT DISTINCT id, name, shortName FROM exam_cat ORDER BY name"
        ))
        for row in result.fetchall():
            print(row)

asyncio.run(main())