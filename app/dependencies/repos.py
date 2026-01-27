# app/dependencies/repos.py
import os
from typing import Any, Dict, List, Optional

from fastapi import Depends

def _backend() -> str:
    return os.getenv("REPO_BACKEND", "memory").lower().strip()


# -----------------------------
# DB 세션 의존성 (postgres 모드)
# -----------------------------
def get_db():
    from app.db.db_session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# Memory Repo Wrappers
# -----------------------------
class MemoryChannelRepo:
    def __init__(self):
        from app.repositories.memory import state as st
        self.st = st

    def create_channel(self) -> Dict[str, Any]:  # 파라미터 제거
        ch = self.st.create_channel()
        return {"channel_id": ch.channel_id, "created_at": ch.created_at}

    def get_channel(self, channel_id: str) -> Optional[Dict[str, Any]]:
        ch = self.st.get_channel(channel_id)
        if not ch:
            return None
        return {"channel_id": ch.channel_id, "created_at": ch.created_at}

    def list_channels(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        # Memory는 limit/offset 무시 (전체 반환)
        rows = []
        for ch in self.st.list_channels():
            rows.append({"channel_id": ch.channel_id, "created_at": ch.created_at})
        return rows

    def delete_channel(self, channel_id: str) -> bool:
        return self.st.delete_channel(channel_id)

    def delete_sessions_by_channel(self, channel_id: str) -> int:
        return self.st.delete_sessions_by_channel(channel_id)


class MemorySessionRepo:
    def __init__(self):
        from app.repositories.memory import state as st
        self.st = st

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
    ) -> Dict[str, Any]:
        sess = self.st.create_session(
            channel_id=channel_id,
            options=options,
            storage_prefix=storage_prefix,
            audio_key=audio_key,
            script_key=script_key,
            status=status,
            current_step=current_step,
            error_message=error_message,
            title=title,
        )
        return {
            "session_id": sess.session_id,
            "channel_id": sess.channel_id,
            "created_at": sess.created_at,
            "options": sess.options,
            "storage_prefix": sess.storage_prefix,
            "audio_key": sess.audio_key,
            "script_key": sess.script_key,
            "status": sess.status,
            "current_step": sess.current_step,
            "error_message": sess.error_message,
            "title": sess.title,
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        sess = self.st.get_session(session_id)
        if not sess:
            return None
        return {
            "session_id": sess.session_id,
            "channel_id": sess.channel_id,
            "created_at": sess.created_at,
            "options": sess.options,
            "storage_prefix": sess.storage_prefix,
            "audio_key": sess.audio_key,
            "script_key": sess.script_key,
            "status": sess.status,
            "current_step": sess.current_step,
            "error_message": sess.error_message,
            "title": sess.title,
        }

    def list_sessions_by_channel(self, channel_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        rows = []
        for s in self.st.list_sessions_by_channel(channel_id):
            rows.append({
                "session_id": s.session_id,
                "channel_id": s.channel_id,
                "created_at": s.created_at,
                "options": s.options,
                "storage_prefix": s.storage_prefix,
                "audio_key": s.audio_key,
                "script_key": s.script_key,
                "status": s.status,
                "current_step": s.current_step,
                "error_message": s.error_message,
                "title": s.title,
            })
        return rows

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
    ) -> Optional[Dict[str, Any]]:
        sess = self.st.update_session(
            session_id,
            status=status,
            current_step=current_step,
            error_message=error_message,
            storage_prefix=storage_prefix,
            audio_key=audio_key,
            script_key=script_key,
            options=options,
            title=title,
        )
        if not sess:
            return None
        return {
            "session_id": sess.session_id,
            "channel_id": sess.channel_id,
            "created_at": sess.created_at,
            "options": sess.options,
            "storage_prefix": sess.storage_prefix,
            "audio_key": sess.audio_key,
            "script_key": sess.script_key,
            "status": sess.status,
            "current_step": sess.current_step,
            "error_message": sess.error_message,
            "title": sess.title,
        }

    def delete_session(self, session_id: str) -> bool:
        return self.st.delete_session(session_id)

    def delete_sessions_by_channel(self, channel_id: str) -> int:
        return self.st.delete_sessions_by_channel(channel_id)


class MemorySessionInputRepo:
    def __init__(self):
        self._rows = []

    def create_input(
        self,
        session_id: str,
        input_key: str,
        role: str,
        title: str | None = None,
        file_type: str | None = None,
        file_size: int | None = None,
        is_link: bool = False,
        link_url: str | None = None,
    ) -> dict:
        row = {
            "input_id": len(self._rows) + 1,
            "session_id": session_id,
            "title": title,
            "input_key": input_key,
            "file_type": file_type,
            "file_size": file_size,
            "is_link": is_link,
            "link_url": link_url,
            "role": role,
        }
        self._rows.append(row)
        return row

    def list_inputs(self, session_id: str) -> List[Dict]:
        return [r for r in self._rows if r["session_id"] == session_id]

    def get_main_input(self, session_id: str) -> Optional[Dict]:
        for r in self._rows:
            if r["session_id"] == session_id and r["role"] == "main":
                return r
        return None

    def delete_inputs_by_session(self, session_id: str) -> int:
        before = len(self._rows)
        self._rows = [r for r in self._rows if r["session_id"] != session_id]
        return before - len(self._rows)


# -----------------------------
# Factory Dependencies
# -----------------------------
def get_channel_repo():
    backend = _backend()
    if backend == "postgres":
        from app.repositories.postgres.channel_repo import PostgresChannelRepo
        db = next(get_db())
        try:
            yield PostgresChannelRepo(db)
        finally:
            db.close()
    else:
        yield MemoryChannelRepo()


def get_session_repo():
    backend = _backend()
    if backend == "postgres":
        from app.repositories.postgres.session_repo import PostgresSessionRepo
        db = next(get_db())
        try:
            yield PostgresSessionRepo(db)
        finally:
            db.close()
    else:
        yield MemorySessionRepo()


def get_session_input_repo():
    backend = _backend()
    if backend == "postgres":
        from app.repositories.postgres.session_input_repo import PostgresSessionInputRepo
        db = next(get_db())
        try:
            yield PostgresSessionInputRepo(db)
        finally:
            db.close()
    else:
        yield MemorySessionInputRepo()