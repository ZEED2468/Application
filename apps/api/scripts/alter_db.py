import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal

async def alter_columns():
    print("Altering job table track columns to VARCHAR(50)...")
    async with AsyncSessionLocal() as session:
        # Alter column type to VARCHAR(50) to allow custom tracks
        await session.execute(text("ALTER TABLE job ALTER COLUMN track TYPE VARCHAR(50);"))
        await session.execute(text("ALTER TABLE job ALTER COLUMN track_override TYPE VARCHAR(50);"))
        await session.commit()
    print("Column types altered successfully!")

if __name__ == "__main__":
    asyncio.run(alter_columns())
