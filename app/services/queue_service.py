# app/services/queue_service.py
from __future__ import annotations

import json
import os
import re
import base64
from functools import lru_cache
from typing import Any, Dict, Optional

from azure.storage.queue import QueueClient

def _normalize_queue_name(name: str) -> str:
    """
    Azure Queue name rules (핵심만):
      - lowercase letters, numbers, and dash(-)
      - must start with letter or number
      - length 3~63
    """
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    if len(name) < 3:
        name = (name + "-jobs")[:3] if len(name) > 0 else "jobs"
        # 위가 너무 짧게 될 수 있어 안전하게 보정
        if len(name) < 3:
            name = "job"
    if len(name) > 63:
        name = name[:63].rstrip("-")
    # 시작 문자가 dash면 앞에 'q' 붙임
    if name.startswith("-"):
        name = "q" + name[1:]
    return name


def _get_conn_str() -> str:
    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if not conn_str:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is not set")
    return conn_str


def _get_queue_name() -> str:
    qn = os.getenv("AZURE_STORAGE_QUEUE_NAME", "ai-audiobook-jobs")
    return _normalize_queue_name(qn)


@lru_cache(maxsize=1)
def get_queue_client() -> QueueClient:
    """
    QueueClient는 재사용하는 게 좋음 (연결/설정 캐시).
    """
    conn_str = _get_conn_str()
    queue_name = _get_queue_name()

    qc = QueueClient.from_connection_string(
        conn_str=conn_str,
        queue_name=queue_name,
        message_encode_policy=None,  # ← 자동 Base64 인코딩 비활성화
        message_decode_policy=None,  # ← 자동 Base64 디코딩 비활성화
    )

    # 큐는 없으면 생성 가능 (권한 있으면). 이미 있으면 에러 없이 넘어가게 처리.
    try:
        qc.create_queue()
    except Exception:
        # 이미 존재하거나 권한/정책 상 create 불가일 수 있음.
        # 그 경우 send_message 시점에 다시 에러로 드러나므로 여기서는 무시.
        pass

    return qc


def enqueue_session_job(
    *,
    session_id: str,
    channel_id: str,
    options: Optional[Dict[str, Any]] = None,
    kind: str = "generate",
) -> Dict[str, Any]:
    """
    세션 처리 작업을 Azure Storage Queue에 넣는다.
    kind: 메시지 타입 (추후 확장 대비)
    """
    if not session_id:
        raise ValueError("session_id is required")
    if not channel_id:
        raise ValueError("channel_id is required")

    payload = {
        "kind": kind,
        "session_id": session_id,
        "channel_id": channel_id,
        "options": options or {},
    }

    qc = get_queue_client()

    # JSON 문자열로 변환 후 Base64 인코딩 (.NET Functions와 호환)
    json_str = json.dumps(payload, ensure_ascii=False)
    base64_str = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
    
    res = qc.send_message(base64_str)

    # azure SDK 응답 객체에서 유용한 정보만 dict로 정리
    return {
        "queue_name": qc.queue_name,
        "message_id": getattr(res, "id", None),
        "pop_receipt": getattr(res, "pop_receipt", None),
        "inserted_on": getattr(res, "inserted_on", None),
    }


def enqueue_pipeline_step(
    *,
    session_id: str,
    channel_id: str,
    step: str,  # "extract_ocr", "extract_finalize", "script", "audio", "finalize"
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    파이프라인 단계별 작업을 Azure Storage Queue에 넣는다.
    
    ✅ Extract 2단계 분할:
    - extract_ocr: OCR 수행
    - extract_finalize: 텍스트 병합 + 메타데이터
    """
    if not session_id:
        raise ValueError("session_id is required")
    if not channel_id:
        raise ValueError("channel_id is required")
    
    # ✅ 허용된 step 목록 (extract 분할)
    valid_steps = ["extract_ocr", "extract_finalize", "script", "audio", "finalize"]
    if step not in valid_steps:
        raise ValueError(f"Invalid step: {step}. Must be one of {valid_steps}")

    payload = {
        "kind": "pipeline_step",  # ← 새로운 kind
        "session_id": session_id,
        "channel_id": channel_id,
        "step": step,
        "options": options or {},
    }

    qc = get_queue_client()

    # JSON 문자열로 변환 후 Base64 인코딩
    json_str = json.dumps(payload, ensure_ascii=False)
    base64_str = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
    
    res = qc.send_message(base64_str)

    return {
        "queue_name": qc.queue_name,
        "message_id": getattr(res, "id", None),
        "pop_receipt": getattr(res, "pop_receipt", None),
        "inserted_on": getattr(res, "inserted_on", None),
    }