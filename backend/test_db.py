import os
import asyncio
from dotenv import load_dotenv
from urllib.parse import urlparse, quote_plus, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

load_dotenv()

async def test_connection():
    raw_url = os.getenv("SOURCE_DB_URL")
    print(f"--- Testing Connection to: {raw_url.split('@')[-1]} ---")

    # 1. Manually encode to check for mangling
    parsed = urlparse(raw_url)
    safe_pass = quote_plus(parsed.password) if parsed.password else ""
    
    # 2. Build the Async URL
    netloc = f"{parsed.username}:{safe_pass}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    
    async_url = urlunparse(("mysql+aiomysql", netloc, parsed.path, "", "", ""))

    try:
        engine = create_async_engine(async_url)
        async with engine.connect() as conn:
            # This is the simplest query possible to verify access
            result = await conn.execute(text("SELECT 1"))
            print("✅ SUCCESS: Connection established and credentials verified!")
    except Exception as e:
        print("❌ FAILURE: Could not connect.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())