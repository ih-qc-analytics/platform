import asyncio
from sqlalchemy import text
from app.database import SessionLocal


async def main():
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT DISTINCT productType FROM product"))
        print("=== productType ===")
        for row in result.fetchall():
            print(repr(row[0]))


print("starting...")
asyncio.run(main())
print("done")