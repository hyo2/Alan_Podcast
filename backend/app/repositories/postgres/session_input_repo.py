# backend/app/repositories/postgres/session_input_repo.py
from __future__ import annotations
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

class PostgresSessionInputRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_input(  # add_input → create_input
        self,
        session_id: str,
        input_key: str,
        role: str,
        title: str | None = None,
        file_type: str | None = None,
        file_size: int | None = None,
        is_link: bool = False,
        link_url: str | None = None,
    ) -> Dict:
        q = text("""
            INSERT INTO session_inputs (
                session_id, title, input_key, file_type, file_size, is_link, link_url, role
            )
            VALUES (
                :session_id, :title, :input_key, :file_type, :file_size, :is_link, :link_url, :role
            )
            RETURNING
                input_id, session_id, title, input_key, file_type, file_size, created_at, is_link, link_url, role
        """)
        row = self.db.execute(q, {
            "session_id": session_id,
            "title": title,
            "input_key": input_key,
            "file_type": file_type,
            "file_size": file_size,
            "is_link": is_link,
            "link_url": link_url,
            "role": role,
        }).mappings().one()
        self.db.commit()
        return dict(row)

    def list_inputs(self, session_id: str) -> List[Dict]:
        q = text("""
            SELECT
                input_id, session_id, title, input_key, file_type, file_size, created_at, is_link, link_url, role
            FROM session_inputs
            WHERE session_id = :session_id
            ORDER BY created_at ASC, input_id ASC
        """)
        rows = self.db.execute(q, {"session_id": session_id}).mappings().all()
        return [dict(r) for r in rows]

    def get_main_input(self, session_id: str) -> Optional[Dict]:
        q = text("""
            SELECT
                input_id, session_id, title, input_key, file_type, file_size, created_at, is_link, link_url, role
            FROM session_inputs
            WHERE session_id = :session_id AND role = 'main'
            LIMIT 1
        """)
        row = self.db.execute(q, {"session_id": session_id}).mappings().one_or_none()
        return dict(row) if row else None

    def delete_inputs_by_session(self, session_id: str) -> int:
        q = text("""
            DELETE FROM session_inputs
            WHERE session_id = :session_id
        """)
        res = self.db.execute(q, {"session_id": session_id})
        self.db.commit()
        return res.rowcount or 0