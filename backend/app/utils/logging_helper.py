# app/utils/logging_helper.py
import logging
import os
import sys
from typing import Iterable


def setup_logging() -> None:
    """
    목표:
    - 코드(app.*)는 LOG_LEVEL로 컨트롤 (dev=DEBUG 유지 가능)
    - 서드파티 noisy 로그(urllib3, multipart, pdfminer, azure/google sdk 등)는 기본 WARNING 이상으로 올려서 조용히
    - 필요할 때만 ALLOW_THIRDPARTY_DEBUG=1 로 일부 노이즈 로거를 INFO까지 풀 수 있음
    """

    # 1) UTF-8 stdout/stderr (Windows/Functions 환경에서 깨짐 방지)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    # 2) 앱 전체 레벨
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level_str, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # 기존 핸들러 제거(중복 출력 방지)
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)

    def _set_level(names: Iterable[str], lvl: int) -> None:
        for n in names:
            logging.getLogger(n).setLevel(lvl)

    # 3) 기본: 서드파티는 조용히
    allow_thirdparty_debug = os.getenv("ALLOW_THIRDPARTY_DEBUG", "0") == "1"
    thirdparty_level = logging.INFO if allow_thirdparty_debug else logging.WARNING

    # --- HTTP/네트워크 (requests/httpx 내부에서 urllib3로 뿜는 로그 방지) ---
    _set_level(
        [
            "urllib3",
            "urllib3.connectionpool",
            "httpx",
            "httpcore",  # httpx 내부
            "requests",
        ],
        thirdparty_level,
    )

    # --- Azure SDK (Blob/Queue HTTP trace, pipeline logging policy 등) ---
    _set_level(
        [
            "azure",
            "azure.core",
            "azure.core.pipeline",
            "azure.core.pipeline.policies",
            "azure.core.pipeline.policies.http_logging_policy",
            "azure.storage",
            "azure.storage.blobs",
            "azure.storage.queue",
        ],
        thirdparty_level,
    )

    # --- FastAPI multipart 디버그 ---
    _set_level(
        [
            "python_multipart",
            "python_multipart.multipart",
        ],
        thirdparty_level,
    )

    # --- LangSmith 디버그 ---
    _set_level(
        [
            "langsmith",
            "langsmith.client",
        ],
        logging.WARNING if not allow_thirdparty_debug else logging.INFO,
    )

    # --- Google SDK (genai/aiplatform/speech 등) ---
    _set_level(
        [
            "google",
            "google.auth",
            "google.auth.transport",
            "google.api_core",
            "google.api_core.retry",
            "google.api_core.grpc_helpers",
            "google.cloud",
        ],
        thirdparty_level,
    )

    # --- PDF/이미지 처리: pdfminer 제거  ---
    _set_level(
        [
            "pdfminer",
            "pdfminer.psparser",
            "pdfminer.pdfinterp",
            "pdfminer.pdfpage",
            "pdfminer.converter",
            "pdfminer.pdfdocument",
            "pdfplumber",
            "pypdf",
            "pypdfium2",
            "PIL",
        ],
        thirdparty_level,
    )

    # --- DB(SQLAlchemy): SQL 쿼리/바인드 파라미터 로그 방지 ---
    # 필요할 때만 따로 올리기(평소엔 WARNING)
    _set_level(
        [
            "sqlalchemy",
            "sqlalchemy.engine",
            "sqlalchemy.pool",
        ],
        logging.WARNING if not allow_thirdparty_debug else logging.INFO,
    )

    # --- Uvicorn: access 로그는 기본 조용히 ---
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "logging initialized (LOG_LEVEL=%s, ALLOW_THIRDPARTY_DEBUG=%s)",
        log_level_str,
        allow_thirdparty_debug,
    )
