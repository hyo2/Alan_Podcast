# app/utils/binary_helper.py
from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 패키징된 바이너리 위치(배포물에 포함)
_BIN_DIR = Path(__file__).resolve().parents[1] / "bin" / "linux-x64"  # app/bin/linux-x64

# 런타임에서 실행 가능한 위치 (Azure Functions Linux에서 보통 /tmp는 쓰기+chmod 가능)
_TMP_DIR = Path("/tmp/bin")


def _copy_to_tmp_and_chmod(src: Path, name: str) -> Path:
    """
    wwwroot는 읽기전용/권한 제한으로 chmod가 안 될 수 있으므로
    /tmp로 복사한 뒤 실행권한 부여해서 사용한다.
    """
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    dst = _TMP_DIR / name

    # 매번 복사(버전 교체/배포 반영 확실) — 필요하면 "없을 때만 복사"로 바꿔도 됨
    shutil.copy2(src, dst)

    mode = dst.stat().st_mode
    dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dst


def _smoke_test(exe_path: str, label: str) -> None:
    """
    -version 정도로 실행 가능 여부만 확인(로그만 남김)
    """
    try:
        r = subprocess.run(
            [exe_path, "-version"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if r.returncode == 0:
            logger.info("✅ %s executable test: SUCCESS (%s)", label, exe_path)
        else:
            logger.warning("⚠ %s executable test failed (%s): %s", label, exe_path, r.stderr[:300])
    except Exception as e:
        logger.warning("⚠ %s executable test error (%s): %s", label, exe_path, e)


def prepare_ffmpeg_binaries() -> tuple[str, str]:
    """
    Azure/Linux: 번들된 ffmpeg/ffprobe를 /tmp로 복사+chmod 후 경로 반환
    Local(비Linux): 시스템 PATH의 ffmpeg/ffprobe 사용
    """
    if platform.system() != "Linux":
        # 로컬 개발(Windows/macOS)에서는 시스템 ffmpeg/ffprobe를 쓰는게 일반적
        return "ffmpeg", "ffprobe"

    ffmpeg_src = _BIN_DIR / "ffmpeg"
    ffprobe_src = _BIN_DIR / "ffprobe"

    if not ffmpeg_src.exists():
        raise FileNotFoundError(f"ffmpeg not found in package: {ffmpeg_src}")
    if not ffprobe_src.exists():
        raise FileNotFoundError(f"ffprobe not found in package: {ffprobe_src}")

    ffmpeg_tmp = _copy_to_tmp_and_chmod(ffmpeg_src, "ffmpeg")
    ffprobe_tmp = _copy_to_tmp_and_chmod(ffprobe_src, "ffprobe")

    ffmpeg_path = str(ffmpeg_tmp)
    ffprobe_path = str(ffprobe_tmp)

    logger.info("✅ FFmpeg binaries ready in /tmp: ffmpeg=%s, ffprobe=%s", ffmpeg_path, ffprobe_path)

    # 선택: 바로 실행 테스트(문제 디버깅에 도움)
    _smoke_test(ffmpeg_path, "ffmpeg")
    _smoke_test(ffprobe_path, "ffprobe")

    return ffmpeg_path, ffprobe_path


# ---- 하위 호환용 API (기존 코드가 import 하고 있을 수 있음) ----
def get_ffmpeg_path() -> str:
    ffmpeg_path, _ = prepare_ffmpeg_binaries()
    return ffmpeg_path


def get_ffprobe_path() -> str:
    _, ffprobe_path = prepare_ffmpeg_binaries()
    return ffprobe_path