# backend/app/repositories/memory/state.py

from typing import Dict, List, Optional
from app.models.channel import Channel
from app.models.session import Session


# 저장소
channels: Dict[str, Channel] = {}
sessions: Dict[str, Session] = {}


# ========== Channel Functions ==========

def create_channel() -> Channel:
    """채널 생성"""
    channel = Channel()
    channels[channel.channel_id] = channel
    return channel


def get_channel(channel_id: str) -> Channel | None:
    """채널 조회"""
    return channels.get(channel_id)


def delete_channel(channel_id: str) -> bool:
    """채널 삭제"""
    if channel_id in channels:
        del channels[channel_id]
        return True
    return False


def list_channels() -> List[Channel]:
    """채널 목록 조회"""
    return list(channels.values())


# ========== Session Functions ==========

def create_session(
    channel_id: str,
    options: dict | None = None,
    storage_prefix: str | None = None,
    audio_key: str | None = None,
    script_key: str | None = None,
    status: str = "pending",
    current_step: str | None = None,
    error_message: str | None = None,
    title: str | None = None,
) -> Session:
    """세션 생성"""
    session = Session(
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
    sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    """세션 조회"""
    return sessions.get(session_id)


def list_sessions_by_channel(channel_id: str) -> List[Session]:
    """채널별 세션 목록 조회"""
    return [s for s in sessions.values() if s.channel_id == channel_id]


def update_session(session_id: str, **fields) -> Session | None:
    """세션 필드 업데이트"""
    sess = sessions.get(session_id)
    if not sess:
        return None
    
    for key, value in fields.items():
        if hasattr(sess, key) and value is not None:
            setattr(sess, key, value)
    
    return sess


def delete_session(session_id: str) -> bool:
    """세션 삭제"""
    if session_id in sessions:
        del sessions[session_id]
        return True
    return False


def delete_sessions_by_channel(channel_id: str) -> int:
    """채널별 세션 전체 삭제"""
    to_delete = [sid for sid, s in sessions.items() if s.channel_id == channel_id]
    for sid in to_delete:
        del sessions[sid]
    return len(to_delete)