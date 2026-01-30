# backend/app/db/db_session.py
import os
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv("DATABASE_URL")

# ✅ DATABASE_URL이 있으면 항상 DB 세션 팩토리를 만든다.
# (REPO_BACKEND=memory 여도 prompt_template 등 "설정성 데이터"는 DB에서 읽을 수 있게)
if DATABASE_URL:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )

    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
    )
else:
    SessionLocal = None


def get_db() -> Session:
    """
    FastAPI Depends로 사용:
      def endpoint(db: Session = Depends(get_db))
    """
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set; database is not configured.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
