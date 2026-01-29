# backend/scripts/migrate_channels.py
# [BE] A3-3: 기존 세션 데이터 마이그레이션 스크립트

import argparse
import copy
from app.state import sessions, channels
from app.models.channel import Channel

def run_migration(dry_run: bool = False, rollback: bool = False):
    # 1. 기존 데이터 백업
    backup_sessions = copy.deepcopy(sessions)
    backup_channels = copy.deepcopy(channels)

    if rollback:
        print("[Rollback] 마이그레이션 이전 상태로 복구 작업을 시작합니다...")
        for session_id, session in sessions.items():
            if hasattr(session, 'channel_id'):
                delattr(session, 'channel_id')
        print("[Rollback] 완료: 모든 세션에서 channel_id를 제거했습니다.")
        return

    print(f"[Migration] {'(Dry-run)' if dry_run else ''} 작업을 시작합니다...")

    # 2. 기본 채널 생성 (ch_default)
    default_channel_id = "ch_default"
    if default_channel_id not in channels:
        if not dry_run:
            new_channel = Channel(channel_id=default_channel_id)
            channels[default_channel_id] = new_channel
        print(f"-> 기본 채널 생성 예정: {default_channel_id}")

    # 3. channel_id가 없는 세션을 찾아 기본 채널 할당
    updated_count = 0
    for session_id, session in sessions.items():
        if not hasattr(session, 'channel_id') or session.channel_id is None:
            if not dry_run:
                session.channel_id = default_channel_id
            updated_count += 1
            print(f"-> 세션 업데이트 대상: {session_id} -> {default_channel_id}")

    # 4. 결과 로깅
    print(f"\n[결과 요약]")
    print(f"- 업데이트 대상 세션: {updated_count}개")
    if dry_run:
        print("- 실제 데이터는 변경되지 않았습니다 (Dry-run 모드).")
    else:
        print("- 마이그레이션이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    # 커맨드라인 인자 처리 (argparse)
    parser = argparse.ArgumentParser(description="Session Data Migration Script")
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 테스트만 진행")
    parser.add_argument("--rollback", action="store_true", help="마이그레이션 이전 상태로 롤백")
    
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run, rollback=args.rollback)