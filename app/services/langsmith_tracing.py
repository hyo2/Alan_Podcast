# app/services/langsmith_tracing.py
import json
import logging

logger = logging.getLogger(__name__)

def _get_root_run_id(storage, storage_prefix):
    try:
        progress_key = f"{storage_prefix}pipeline/progress.json"
        progress_data = storage.download_json(progress_key)
        return progress_data.get("langsmith_root_run_id")
    except Exception:
        return None

def _sanitize_for_langsmith(obj, *, max_str=4000, max_list=50, _depth=0, _max_depth=6):
    if _depth > _max_depth:
        return "<max_depth_reached>"

    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str] + "…<truncated>"

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[str(k)] = _sanitize_for_langsmith(v, max_str=max_str, max_list=max_list, _depth=_depth + 1)
        return out

    if isinstance(obj, (list, tuple)):
        lst = list(obj)
        if len(lst) > max_list:
            lst = lst[:max_list] + ["…<truncated_list>"]
        return [_sanitize_for_langsmith(x, max_str=max_str, max_list=max_list, _depth=_depth + 1) for x in lst]

    try:
        s = repr(obj)
    except Exception:
        s = f"<unreprable:{type(obj).__name__}>"
    return s if len(s) <= max_str else s[:max_str] + "…<truncated_repr>"

def _trace_safe_state(state: dict) -> dict:
    if not isinstance(state, dict):
        return {"_state": _sanitize_for_langsmith(state)}
    drop_keys = {"checkpoint_callback"}
    cleaned = {k: v for k, v in state.items() if k not in drop_keys}
    return _sanitize_for_langsmith(cleaned)

def _safe_jsonable(obj):
    try:
        json.dumps(obj)
        return obj
    except Exception:
        if isinstance(obj, dict):
            return {str(k): _safe_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_safe_jsonable(x) for x in obj]
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        if hasattr(obj, "__dict__"):
            try:
                return {k: _safe_jsonable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
            except Exception:
                pass
        if isinstance(obj, (bytes, bytearray)):
            return f"<{type(obj).__name__} len={len(obj)}>"
        if isinstance(obj, (set, tuple)):
            return [_safe_jsonable(x) for x in obj]
        return str(obj)

def _trace_with_parent(name: str, parent_run_id: str, func, state_input: dict):
    # LangSmith 준비(create_run 등)가 실패하면: tracing 없이 func를 "한 번만" 실행
    # func 실행 중 예외가 나면: run 업데이트 후 예외를 그대로 propagate (재실행 금지)
    import datetime as _dt

    # 1) Tracing 준비 단계 (여기서 실패하면 fallback)
    try:
        from langsmith import Client  # type: ignore
        client = Client()
        safe_in = _safe_jsonable(state_input)

        child = client.create_run(
            name=name,
            run_type="chain",
            parent_run_id=parent_run_id,
            inputs={"state": safe_in},
            extra={"azure_function": True},
        )
        child_id = child.get("id") or child.get("run_id") or child.get("uuid")
        if not child_id:
            raise RuntimeError("LangSmith create_run returned no id")
    except Exception as e:
        logger.warning(f"[LangSmith] trace 준비 실패({name}): {e}")
        return func(state_input)  # ✅ fallback (단 1회)

    # 2) func 실행 + run 업데이트 (여기서 예외 나면 절대 재실행하지 않음)
    try:
        result = func(state_input)
    except Exception as e:
        try:
            client.update_run(child_id, error=str(e), end_time=_dt.datetime.utcnow())
        except Exception as ue:
            logger.warning(f"[LangSmith] update_run(error) 실패({name}): {ue}")
        raise

    try:
        safe_out = _safe_jsonable(result)
        client.update_run(child_id, outputs={"state": safe_out}, end_time=_dt.datetime.utcnow())
    except Exception as e:
        logger.warning(f"[LangSmith] update_run(outputs) 실패({name}): {e}")
    return result
