# backend/app/repositories/interfaces/session_repo.py
from __future__ import annotations
from typing import Protocol, Optional, Dict, List

class SessionRepo(Protocol):
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
    ) -> Dict: ...  # session_id 파라미터 제거

    def get_session(self, session_id: str) -> Optional[Dict]: ...
    
    def list_sessions_by_channel(
        self, 
        channel_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict]: ...
    
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
    ) -> Optional[Dict]: ...

    def delete_session(self, session_id: str) -> bool: ...
    def delete_sessions_by_channel(self, channel_id: str) -> int: ... 