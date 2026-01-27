# backend/app/repositories/postgres/session_repo.py
from __future__ import annotations
import uuid
import json
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import text

class PostgresSessionRepo:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        channel_id: str,
        options: dict | None = None,
        storage_prefix: str | None = None,
        audio_key: str | None = None,
        script_key: str | None = None,
        status: str = "pending",
        current_step: str | None = None,
        error_message: str | None = None,
        title: str | None = None, 
    ) -> Dict:
        session_id = f"sess_{uuid.uuid4()}"  # 내부 생성
        q = text("""
            INSERT INTO sessions (
                session_id, channel_id, options, storage_prefix, audio_key, script_key,
                status, current_step, error_message, title
            )
            VALUES (
                :session_id, :channel_id, :options, :storage_prefix, :audio_key, :script_key,
                :status, :current_step, :error_message, :title
            )
            RETURNING
                session_id, channel_id, created_at, options,
                storage_prefix, audio_key, script_key,
                status, current_step, error_message, title
        """)
        row = self.db.execute(q, {
            "session_id": session_id,
            "channel_id": channel_id,
            "options": json.dumps(options) if options else None,
            "storage_prefix": storage_prefix,
            "audio_key": audio_key,
            "script_key": script_key,
            "status": status,
            "current_step": current_step,
            "error_message": error_message,
            "title": title,  
        }).mappings().one()
        self.db.commit()
        
        result = dict(row)
        # options를 dict로 파싱
        if result.get("options") and isinstance(result["options"], str):
            result["options"] = json.loads(result["options"])
        return result

    def get_session(self, session_id: str) -> Optional[Dict]:
        q = text("""
            SELECT
                session_id, channel_id, created_at, options,
                storage_prefix, audio_key, script_key,
                status, current_step, error_message, title
            FROM sessions
            WHERE session_id = :session_id
        """)
        row = self.db.execute(q, {"session_id": session_id}).mappings().one_or_none()
        if not row:
            return None
        
        result = dict(row)
        # options를 dict로 파싱
        if result.get("options") and isinstance(result["options"], str):
            result["options"] = json.loads(result["options"])
        return result

    def list_sessions_by_channel(self, channel_id: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        q = text("""
            SELECT
                session_id, channel_id, created_at, options,
                storage_prefix, audio_key, script_key,
                status, current_step, error_message, title
            FROM sessions
            WHERE channel_id = :channel_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        rows = self.db.execute(q, {"channel_id": channel_id, "limit": limit, "offset": offset}).mappings().all()
        
        results = []
        for row in rows:
            result = dict(row)
            if result.get("options") and isinstance(result["options"], str):
                result["options"] = json.loads(result["options"])
            results.append(result)
        return results

    def update_session_fields(
        self,
        session_id: str,
        *,
        status: str | None = None,
        current_step: str | None = None,
        error_message: str | None = None,
        storage_prefix: str | None = None,
        audio_key: str | None = None,
        script_key: str | None = None,
        title: str | None = None,
        options: dict | None = None,
    ) -> Optional[Dict]:
        q = text("""
            UPDATE sessions
            SET
                status = COALESCE(:status, status),
                current_step = COALESCE(:current_step, current_step),
                error_message = COALESCE(:error_message, error_message),
                storage_prefix = COALESCE(:storage_prefix, storage_prefix),
                audio_key = COALESCE(:audio_key, audio_key),
                script_key = COALESCE(:script_key, script_key),
                options = COALESCE(:options, options),
                title = COALESCE(:title, title)
            WHERE session_id = :session_id
            RETURNING
                session_id, channel_id, created_at, options,
                storage_prefix, audio_key, script_key,
                status, current_step, error_message, title
        """)
        row = self.db.execute(q, {
            "session_id": session_id,
            "status": status,
            "current_step": current_step,
            "error_message": error_message,
            "storage_prefix": storage_prefix,
            "audio_key": audio_key,
            "script_key": script_key,
            "options": json.dumps(options) if options else None,
            "title": title,
        }).mappings().one_or_none()
        self.db.commit()
        
        if not row:
            return None
        
        result = dict(row)
        if result.get("options") and isinstance(result["options"], str):
            result["options"] = json.loads(result["options"])
        return result

    def delete_session(self, session_id: str) -> bool:
        q = text("""
            DELETE FROM sessions
            WHERE session_id = :session_id
        """)
        res = self.db.execute(q, {"session_id": session_id})
        self.db.commit()
        return res.rowcount > 0

    def delete_sessions_by_channel(self, channel_id: str) -> int:
        q = text("""
            DELETE FROM sessions
            WHERE channel_id = :channel_id
        """)
        res = self.db.execute(q, {"channel_id": channel_id})
        self.db.commit()
        return res.rowcount or 0