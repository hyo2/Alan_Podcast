"""
API 가격 계산 유틸리티 (환경변수 기반)

환경변수로 가격 정책을 관리하여 코드 수정 없이 가격 업데이트 가능
"""

import os
from typing import Dict, Tuple


def get_pricing() -> Dict[str, float]:
    """
    환경변수에서 가격 정책 로드 (기본값: 2025년 2월 기준)
    
    Returns:
        Dict[str, float]: 단위당 가격 (USD)
            - llm_input: per token
            - llm_output: per token
            - vision: per token
            - tts: per character
            - stt: per second
    """
    return {
        # Gemini 2.5 Flash (LLM)
        "llm_input": float(os.getenv("PRICING_LLM_INPUT", "0.075")) / 1_000_000,
        "llm_output": float(os.getenv("PRICING_LLM_OUTPUT", "0.30")) / 1_000_000,
        
        # Gemini Vision API
        "vision": float(os.getenv("PRICING_VISION", "0.125")) / 1_000_000,
        
        # Gemini TTS
        "tts": float(os.getenv("PRICING_TTS", "16.00")) / 1_000_000,
        
        # Google Cloud Speech-to-Text (Standard)
        "stt": float(os.getenv("PRICING_STT", "1.44")) / 3600,  # per hour → per second
    }


def get_exchange_rate() -> float:
    """환율 가져오기 (USD → KRW)"""
    return float(os.getenv("EXCHANGE_RATE_KRW", "1330"))


def calculate_llm_cost(input_tokens: int, output_tokens: int) -> float:
    """
    LLM 비용 계산
    
    Args:
        input_tokens: 입력 토큰 수
        output_tokens: 출력 토큰 수
    
    Returns:
        float: 비용 (USD)
    """
    pricing = get_pricing()
    return (input_tokens * pricing["llm_input"] + 
            output_tokens * pricing["llm_output"])


def calculate_vision_cost(tokens: int) -> float:
    """
    Vision API 비용 계산
    
    Args:
        tokens: 토큰 수
    
    Returns:
        float: 비용 (USD)
    """
    return tokens * get_pricing()["vision"]


def calculate_text_cost(tokens: int, input_ratio: float = 0.5) -> float:
    """
    Text API 비용 계산 (LLM 사용, input/output 비율 가정)
    
    키워드 추출 같은 텍스트 작업은 input/output 비율을 정확히 추적하기 어려우므로
    총 토큰 수와 비율 가정으로 계산
    
    Args:
        tokens: 총 토큰 수
        input_ratio: input 토큰 비율 (기본: 0.5 = 50%)
    
    Returns:
        float: 비용 (USD)
    
    Example:
        >>> calculate_text_cost(2000)  # 2000 tokens, 50% input/output
        >>> calculate_text_cost(2000, 0.7)  # 70% input, 30% output
    """
    input_tokens = int(tokens * input_ratio)
    output_tokens = tokens - input_tokens
    return calculate_llm_cost(input_tokens, output_tokens)


def calculate_tts_cost(characters: int) -> float:
    """
    TTS 비용 계산
    
    Args:
        characters: 문자 수
    
    Returns:
        float: 비용 (USD)
    """
    return characters * get_pricing()["tts"]


def calculate_stt_cost(seconds: float) -> float:
    """
    STT 비용 계산
    
    Args:
        seconds: 오디오 길이 (초)
    
    Returns:
        float: 비용 (USD)
    """
    return seconds * get_pricing()["stt"]


def format_cost(usd: float, include_krw: bool = True) -> str:
    """
    비용 포맷팅
    
    Args:
        usd: 비용 (USD)
        include_krw: KRW 환산 포함 여부
    
    Returns:
        str: 포맷된 비용 문자열
    
    Examples:
        >>> format_cost(0.0640)
        "$0.0640 (₩85)"
        >>> format_cost(0.0640, include_krw=False)
        "$0.0640"
    """
    if include_krw:
        krw = usd * get_exchange_rate()
        return f"${usd:.4f} (₩{krw:.0f})"
    else:
        return f"${usd:.4f}"


def calculate_total_cost(
    llm_input: int = 0,
    llm_output: int = 0,
    vision: int = 0,
    tts: int = 0,
    stt: float = 0.0
) -> Tuple[Dict[str, float], float]:
    """
    전체 비용 계산
    
    Args:
        llm_input: LLM 입력 토큰
        llm_output: LLM 출력 토큰
        vision: Vision 토큰
        tts: TTS 문자 수
        stt: STT 시간 (초)
    
    Returns:
        Tuple[Dict[str, float], float]: (항목별 비용, 총 비용)
    """
    costs = {
        "llm": calculate_llm_cost(llm_input, llm_output),
        "vision": calculate_vision_cost(vision),
        "tts": calculate_tts_cost(tts),
        "stt": calculate_stt_cost(stt)
    }
    
    total = sum(costs.values())
    
    return costs, total


if __name__ == "__main__":
    # 테스트
    print("=" * 60)
    print("API 가격 정책 테스트")
    print("=" * 60)
    
    pricing = get_pricing()
    print(f"\n📊 현재 가격 정책:")
    print(f"   LLM Input:  ${pricing['llm_input'] * 1_000_000:.3f} / 1M tokens")
    print(f"   LLM Output: ${pricing['llm_output'] * 1_000_000:.3f} / 1M tokens")
    print(f"   Vision:     ${pricing['vision'] * 1_000_000:.3f} / 1M tokens")
    print(f"   TTS:        ${pricing['tts'] * 1_000_000:.2f} / 1M chars")
    print(f"   STT:        ${pricing['stt'] * 3600:.2f} / hour")
    print(f"   환율:       ₩{get_exchange_rate():.0f} / USD")
    
    print(f"\n💰 예제 계산:")
    print(f"   LLM (16,500 input + 3,500 output): {format_cost(calculate_llm_cost(16500, 3500))}")
    print(f"   Vision (12,657 tokens): {format_cost(calculate_vision_cost(12657))}")
    print(f"   TTS (2,756 chars): {format_cost(calculate_tts_cost(2756))}")
    print(f"   STT (40.11 seconds): {format_cost(calculate_stt_cost(40.11))}")
    
    costs, total = calculate_total_cost(
        llm_input=16500,
        llm_output=3500,
        vision=12657,
        tts=2756,
        stt=40.11
    )
    
    print(f"\n💵 총 비용: {format_cost(total)}")
    print("=" * 60)