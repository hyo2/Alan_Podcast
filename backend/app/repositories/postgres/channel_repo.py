# backend/app/repositories/postgres/channel_repo.py
from __future__ import annotations
import uuid
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import text

class PostgresChannelRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_channel(self) -> Dict:  # 파라미터 제거
        channel_id = f"ch_{uuid.uuid4()}"  # 내부 생성
        q = text("""
            INSERT INTO public.channels (channel_id)
            VALUES (:channel_id)
            RETURNING channel_id, created_at
        """)
        row = self.db.execute(q, {"channel_id": channel_id}).mappings().one()
        self.db.commit()
        return dict(row)

    def get_channel(self, channel_id: str) -> Optional[Dict]:
        q = text("""
            SELECT channel_id, created_at
            FROM public.channels
            WHERE channel_id = :channel_id
        """)
        row = self.db.execute(q, {"channel_id": channel_id}).mappings().one_or_none()
        return dict(row) if row else None

    def delete_channel(self, channel_id: str) -> bool:
        q = text("""
            DELETE FROM public.channels
            WHERE channel_id = :channel_id
        """)
        res = self.db.execute(q, {"channel_id": channel_id})
        self.db.commit()
        return res.rowcount > 0

    def list_channels(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        q = text("""
            SELECT channel_id, created_at
            FROM channels
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        rows = self.db.execute(q, {"limit": limit, "offset": offset}).mappings().all()
        return [dict(r) for r in rows]

    def delete_sessions_by_channel(self, channel_id: str) -> int:
        # FK CASCADE로 자동 삭제되지만, 명시적으로 구현
        q = text("""
            DELETE FROM sessions
            WHERE channel_id = :channel_id
        """)
        res = self.db.execute(q, {"channel_id": channel_id})
        self.db.commit()
        return res.rowcount or 0