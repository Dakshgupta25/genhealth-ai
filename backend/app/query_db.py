import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.schemas.health_record import HealthRecordOut
from app.models.health_record import HealthRecord, ExtractedEntity

DATABASE_URL = "postgresql+asyncpg://genhealth:password@postgres:5432/genhealth"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        print("Connected to database via session.")
        
        # Query health records using Session
        res = await session.execute(select(HealthRecord).options(selectinload(HealthRecord.extracted_entities)))
        records = res.scalars().all()
        print(f"Found {len(records)} health records.")
        for r in records:
            try:
                dumped = HealthRecordOut.model_validate(r).model_dump()
                print(f"SUCCESS validation for record {r.id}: status={r.extraction_status}")
            except Exception as e:
                print(f"FAILED validation for record {r.id}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
