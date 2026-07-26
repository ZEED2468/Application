import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal

async def add_column():
    print("Adding column experience_level to job table...")
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("ALTER TABLE job ADD COLUMN experience_level VARCHAR(50);"))
            await session.commit()
            print("Column experience_level added successfully!")
        except Exception as e:
            print(f"Failed or column already exists: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(add_column())
