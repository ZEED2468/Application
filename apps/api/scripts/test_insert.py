import asyncio
import uuid
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models.job import Job
from app.core.enums import JobSourceName, JobStatus

async def test_insert():
    async with AsyncSessionLocal() as session:
        # Get a user to bind the job to
        from app.models.user import User
        user = (await session.execute(select(User))).scalars().first()
        if not user:
            print("No user found to run test insert.")
            return
            
        print(f"Testing insert for user {user.email}...")
        test_job = Job(
            user_id=user.id,
            source=JobSourceName.greenhouse,
            source_job_id=f"test-custom-track-{uuid.uuid4()}",
            dedupe_key=f"test-dedupe-{uuid.uuid4()}"[:32],
            company="Test Custom Track Co",
            title="Data Scientist",
            track="data science",  # Custom track string
            status=JobStatus.discovered
        )
        try:
            session.add(test_job)
            await session.commit()
            print("Insert succeeded! Database allows custom track strings.")
            # Clean up
            await session.delete(test_job)
            await session.commit()
            print("Clean up succeeded.")
        except Exception as e:
            print(f"Insert failed with error: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(test_insert())
