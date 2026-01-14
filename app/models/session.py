# backend/app/models/session.py
# session.py 모델에 붙임.


from dataclasses import dataclass, field
from datetime import datetime
import uuid


def generate_session_id() -> str:
    return f"se_{uuid.uuid4()}"


@dataclass
class Session:
    channel_id: str  # 필수로 설정
    session_id: str = field(default_factory=generate_session_id)
    created_at: datetime = field(default_factory=datetime.utcnow)