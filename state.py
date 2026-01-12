# backend/state.py

from typing import Dict, List
from models.channel import Channel
from models.session import Session


# 저장소 추가
channels: Dict[str, Channel] = {}
sessions: Dict[str, Session] = {}


# 채널 생성
def create_channel() -> Channel:
    channel = Channel()
    channels[channel.channel_id] = channel
    return channel

# 채널 조회
def get_channel(channel_id: str) -> Channel | None:
    return channels.get(channel_id)

# 채널 삭제
def delete_channel(channel_id: str) -> bool:
    if channel_id in channels:
        del channels[channel_id]
        return True
    return False

# 채널 목록 조회
def list_channels() -> List[Channel]:
    return list(channels.values())



# 세션 생성 (수정)
def create_session(channel_id: str) -> Session:
    # 생성 시 channel_id를 필수로 인자에 넣습니다.
    session = Session(channel_id=channel_id)
    sessions[session.session_id] = session
    return session

# 세션 목록 조회 (필터링 기능 추가)
def list_sessions(channel_id: str = None) -> List[Session]:
    """
    channel_id가 주어지면 해당 채널의 세션만 반환 (필터링)
    없으면 전체 반환 (또는 요구사항에 따라 처리)
    """
    if channel_id:
        return [s for s in sessions.values() if getattr(s, 'channel_id', None) == channel_id]
    return list(sessions.values())