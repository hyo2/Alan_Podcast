# backend/app/models/channel.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import List
import uuid


def generate_channel_id() -> str:
    """
    ch_ prefix + UUID v4 생성
    예: ch_a1b2c3d4-e5f6-7890-abcd-ef1234567890
    """
    return f"ch_{uuid.uuid4()}"


@dataclass
class Channel:
    channel_id: str = field(default_factory=generate_channel_id)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sessions: List[str] = field(default_factory=list)
