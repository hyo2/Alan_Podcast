# backend/app/models/session.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4()}"


@dataclass
class Session:
    channel_id: str  # 필수 (기본값 없음)
    session_id: str = field(default_factory=generate_session_id)
    created_at: datetime = field(default_factory=datetime.utcnow)
    storage_prefix: Optional[str] = None
    audio_key: Optional[str] = None
    script_key: Optional[str] = None
    status: str = "pending"
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    options: Optional[dict] = None
    title: Optional[str] = None
    total_duration_sec: Optional[int] = None
    script_text: Optional[str] = None