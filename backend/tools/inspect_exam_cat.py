import asyncio
from sqlalchemy import text
from app.database import SessionLocal


async def main():
    async with SessionLocal() as session:
        result = await session.execute(
            text("""
            SELECT COUNT(*) FROM lead_address WHERE isFavorite = 1
        """)
        )
        print("addresses with isFavorite=1:", result.fetchone()[0])

        result = await session.execute(
            text("""
            SELECT COUNT(*) FROM lead_address
        """)
        )
        print("total addresses:", result.fetchone()[0])


print("starting...")
asyncio.run(main())
print("done")
