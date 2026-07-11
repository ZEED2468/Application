import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal, engine

async def drop_check_constraints():
    print("Connecting to database to check constraints...")
    
    # Query check constraints on the 'job' table
    query = text("""
        SELECT tc.constraint_name, tc.table_name, cc.check_clause
        FROM information_schema.table_constraints tc
        JOIN information_schema.check_constraints cc ON tc.constraint_name = cc.constraint_name
        WHERE tc.table_name = 'job';
    """)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(query)
        constraints = result.all()
        
        print(f"Found {len(constraints)} check constraints on table 'job':")
        for con_name, table, clause in constraints:
            print(f" - {con_name}: {clause}")
            
            # If the check clause references track or track_override, drop it
            if "track" in clause.lower():
                print(f"Dropping constraint {con_name}...")
                drop_query = text(f'ALTER TABLE job DROP CONSTRAINT "{con_name}";')
                await session.execute(drop_query)
                print(f"Dropped {con_name} successfully.")
        
        await session.commit()
    print("Done checking and dropping constraints.")

if __name__ == "__main__":
    asyncio.run(drop_check_constraints())
