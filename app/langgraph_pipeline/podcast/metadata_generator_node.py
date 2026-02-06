"""
Metadata Generator Node (V2 - pdfplumber 전환)
===============================================

변경사항:
- PyMuPDF 완전 제거
- pdfplumber + OCR (pdf2image + PaddleOCR)로 통합
- improved_hybrid_filter.py V3와 완전 호환

입력:
- primary_file: 주강의자료 (1개, 필수)
- supplementary_files: 보조자료 (0~3개, 선택)

출력:
- metadata.json (이미지 설명 포함)

통합:
- DocumentConverterNode: PDF 변환 + TXT/URL 처리
- ImprovedHybridFilterPipeline: 이미지 필터링
- TextExtractor: 페이지별 텍스트 추출
- ImageDescriptionGenerator: 이미지 상세 설명

"""

import os
import json
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# OCR 로그 억제
os.environ['FLAGS_log_level'] = '3'
os.environ['PPOCR_SHOW_LOG'] = 'False'

# pdfplumber (필수)
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    print("❌ pdfplumber가 설치되지 않았습니다.")
    print("   pip install pdfplumber")
    PDFPLUMBER_AVAILABLE = False

# OCR 라이브러리 (선택)
try:
    from paddleocr import PaddleOCR
    from pdf2image import convert_from_path
    import numpy as np
    from PIL import Image
    from io import BytesIO
    
    OCR_AVAILABLE = True
    ocr_engine = PaddleOCR(lang='korean', use_textline_orientation=True)
    print("✅ OCR 엔진 초기화 완료 (PaddleOCR)")
except ImportError:
    OCR_AVAILABLE = False
    ocr_engine = None
    print("⚠️  OCR 라이브러리 미설치 (선택 사항)")
except Exception as e:
    print(f"⚠️  PaddleOCR 초기화 실패: {e}")
    OCR_AVAILABLE = False
    ocr_engine = None

# 기존 노드 임포트
from .document_converter_node import DocumentConverterNode, DocumentType
from .improved_hybrid_filter import (
    ImprovedHybridFilterPipeline,
    UniversalImageExtractor,
    ImageMetadata,
    model
)

from vertexai.generative_models import Part


class TextExtractor:
    """
    PDF에서 페이지별 텍스트 추출 + 마커 삽입
    V2: pdfplumber + OCR 통합
    """
    
    def __init__(self):
        """TextExtractor 초기화"""
        if not PDFPLUMBER_AVAILABLE:
            raise ImportError("pdfplumber가 필요합니다: pip install pdfplumber")
        
        self.ocr_enabled = OCR_AVAILABLE
        self.min_text_length = 100  # OCR 트리거 기준
    
    def _perform_ocr_on_page(self, pdf_path: str, page_num: int) -> str:
        """
        페이지에 OCR 수행 (pdf2image + PaddleOCR)
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0-indexed)
        
        Returns:
            OCR로 추출한 텍스트
        """
        if not self.ocr_enabled or ocr_engine is None:
            return ""
        
        try:
            # PDF 페이지 → 이미지 변환
            images = convert_from_path(
                pdf_path,
                first_page=page_num + 1,  # 1-indexed
                last_page=page_num + 1,
                dpi=150
            )
            
            if not images:
                return ""
            
            img = images[0]
            img_array = np.array(img)
            
            # OCR 실행
            result = ocr_engine.ocr(img_array, cls=True)
            
            if result and result[0]:
                lines = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0]
                        lines.append(text)
                return "\n".join(lines)
            
            return ""
        
        except Exception as e:
            print(f"      ⚠️  OCR 실패: {e}")
            return ""
    
    def extract_with_markers(
        self, 
        pdf_path: str, 
        prefix: str = "MAIN"
    ) -> Dict[str, Any]:
        """
        PDF에서 페이지별 텍스트 추출 + 마커 삽입
        pdfplumber 사용, 텍스트 부족 시 OCR 자동 수행
        
        Args:
            pdf_path: PDF 파일 경로
            prefix: 페이지 마커 접두사 (MAIN, SUPP1, SUPP2, SUPP3)
        
        Returns:
            {
                "full_text": "[MAIN-PAGE 1: 제목]\n내용...",
                "total_pages": 21
            }
        """
        pages_text = []
        total_pages = 0
        ocr_count = 0
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                print(f"   📄 텍스트 추출 중... (OCR {'활성화' if self.ocr_enabled else '비활성화'})")
                
                for page_num, page in enumerate(pdf.pages):
                    # pdfplumber로 텍스트 추출
                    text = page.extract_text() or ""
                    text_length = len(text.strip())
                    
                    # 텍스트 부족 → OCR 수행
                    if text_length < self.min_text_length and self.ocr_enabled:
                        print(f"      → 페이지 {page_num + 1}: 텍스트 부족 ({text_length}자) → OCR 수행")
                        ocr_text = self._perform_ocr_on_page(pdf_path, page_num)
                        
                        if ocr_text:
                            text = ocr_text
                            ocr_count += 1
                            print(f"         ✅ OCR 완료 ({len(ocr_text)}자 추출)")
                        else:
                            print(f"         ⚠️  OCR 실패, 원본 텍스트 사용")
                    
                    # 페이지 제목 추출
                    lines = text.split('\n')
                    title = lines[0][:50] if lines and lines[0].strip() else f"Page {page_num + 1}"
                    
                    # 마커 삽입
                    pages_text.append(f"[{prefix}-PAGE {page_num + 1}: {title}]")
                    pages_text.append(text)
                    pages_text.append("")
                
                if ocr_count > 0:
                    print(f"   ✅ OCR 처리 완료: {ocr_count}개 페이지")
        
        except Exception as e:
            print(f"   ❌ PDF 텍스트 추출 실패: {e}")
            return {"full_text": "", "total_pages": 0}
        
        return {
            "full_text": "\n".join(pages_text),
            "total_pages": total_pages
        }


class ImageDescriptionGenerator:
    """통과된 이미지에 대한 상세 설명 생성 (2-4문장)"""
    
    
    def __init__(self):
        """이미지 설명 생성기 초기화"""
        self.total_tokens = 0  # ✅ 누적 토큰 수
        self.description_count = 0  # 생성한 설명 개수
        
        # ✅ Gemini 모델 초기화
        from .improved_hybrid_filter import get_global_model
        self.model = get_global_model()
        
        if self.model is None:
            print("      ⚠️  Warning: Gemini 모델 초기화 실패 - 이미지 설명 생성 불가")
    def generate_description(
        self, 
        image_bytes: bytes, 
        adjacent_text: str,
        keywords: List[str],
        max_retries=3
    ) -> str:
        """
        Vision API로 이미지 상세 설명 생성
        재시도 로직 포함 (429 Rate Limit 대응)
        """
        import time
        
        for attempt in range(max_retries):
            try:
                mime_type = self._get_mime_type(image_bytes)
                image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
                
                keyword_context = ', '.join(keywords[:10]) if keywords else "일반 학습 내용"
                
                prompt = f"""
이 이미지를 2-4문장으로 설명하세요.

강의 주제: {keyword_context}
주변 텍스트: "{adjacent_text}"

설명에 포함할 내용:
1. 이미지가 나타내는 주제/개념 (1문장)
2. 주요 구성 요소 2-3개 (1-2문장)
3. 핵심 정보나 패턴 (1문장)

제외할 내용:
- 세부 요소 전체 나열
- 불필요한 추측이나 해석

출력: 명확하고 간결한 2-4문장만.
"""
                
                if not self.model:
                    return "이미지 설명 생성 실패: Model not initialized"
                
                response = self.model.generate_content([image_part, prompt])
                description = response.text.strip()
                
                # ✅ 토큰 사용량 추적 (usage_metadata 우선)
                tokens_added = 0
                try:
                    # Method 1: response.usage_metadata (가장 정확)
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        tokens_added = getattr(response.usage_metadata, 'total_token_count', 0)
                        if tokens_added > 0:
                            self.total_tokens += tokens_added
                            self.description_count += 1
                except Exception:
                    pass
                
                return description
                
            except Exception as e:
                error_msg = str(e)
                
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 3
                        print(f"      ⚠️  Rate Limit, {wait_time}초 대기 중...", end='', flush=True)
                        time.sleep(wait_time)
                        print(" 재시도")
                        continue
                    else:
                        return "이미지 설명 생성 실패: API rate limit exceeded"
                else:
                    return f"이미지 설명 생성 실패: {error_msg}"
        
        return "이미지 설명 생성 실패: Failed after all retries"
    
    def _get_mime_type(self, image_bytes: bytes) -> str:
        """이미지 바이너리에서 MIME 타입 감지"""
        if image_bytes.startswith(b'\xff\xd8'):
            return "image/jpeg"
        elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
            return "image/gif"
        elif image_bytes.startswith(b'RIFF') and image_bytes[8:12] == b'WEBP':
            return "image/webp"
        return "image/png"


class MetadataGenerator:
    """
    메타데이터 생성 노드
    
    주강의자료 + 보조자료 → metadata.json
    """
    
    def __init__(self):
        self.converter = None
        self.text_extractor = TextExtractor()
        self.image_filter = ImprovedHybridFilterPipeline(auto_extract_keywords=True)
        self.image_describer = ImageDescriptionGenerator()
    
    def _extract_page_title(self, slide_title: str, adjacent_text: str) -> str:
        """의미있는 페이지 제목 추출"""
        if slide_title and slide_title.strip() and slide_title.lower() != "no title":
            return slide_title.strip()[:50]
        
        if adjacent_text:
            lines = adjacent_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 3 and not line.startswith('☞'):
                    return line[:50]
        
        return "페이지 제목 없음"
    
    def generate(
        self,
        primary_file: str,
        supplementary_files: Optional[List[str]] = None,
        output_path: str = "output/metadata.json"
    ) -> str:
        """메타데이터 생성"""
        print(f"\n{'='*120}")
        print(f"🎯 메타데이터 생성 시작")
        print(f"{'='*120}")
        print(f"주강의자료: {primary_file}")
        if supplementary_files:
            print(f"보조자료: {len(supplementary_files)}개")
            for i, supp in enumerate(supplementary_files, 1):
                print(f"  {i}. {supp}")
        print(f"{'='*120}\n")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            self.converter = DocumentConverterNode(output_dir=temp_dir)
            
            print("📄 [1/3] 주강의자료 처리 중...")
            primary_metadata = self._process_primary_source(primary_file)
            
            print("\n📚 [2/3] 보조자료 처리 중...")
            supplementary_metadata = []
            if supplementary_files:
                for i, supp_file in enumerate(supplementary_files[:3], 1):
                    try:
                        supp_meta = self._process_supplementary_source(supp_file, i)
                        supplementary_metadata.append(supp_meta)
                        print(f"   ✅ 보조자료 {i} 처리 성공")
                    except Exception as e:
                        print(f"   ⚠️ 보조자료 {i} 처리 실패 (계속 진행): {e}")
            else:
                print("   ⚠️  보조자료 없음 (선택 사항)")
            
            print("\n🔧 [3/3] 메타데이터 통합 중...")
            
            # ✅ Vision 토큰 통계 수집
            vision_tokens = {}
            if hasattr(self.image_filter, 'vision_tokens'):
                vision_tokens = self.image_filter.vision_tokens.copy()
                print(f"   [DEBUG] image_filter.vision_tokens = {vision_tokens}")
            
            # ✅ 이미지 설명 생성 토큰 추가
            print(f"   [DEBUG] image_describer.total_tokens = {self.image_describer.total_tokens}")
            print(f"   [DEBUG] image_describer.description_count = {self.image_describer.description_count}")
            
            if self.image_describer.total_tokens > 0:
                vision_tokens['image_description'] = self.image_describer.total_tokens
                vision_tokens['description_count'] = self.image_describer.description_count
                vision_tokens['total'] = vision_tokens.get('total', 0) + self.image_describer.total_tokens
                print(f"   [DEBUG] vision_tokens after adding image_description = {vision_tokens}")
            
            # ✅ 비용 계산
            if vision_tokens.get('total', 0) > 0:
                from .pricing import calculate_vision_cost, format_cost
                vision_cost = calculate_vision_cost(vision_tokens['total'])
                vision_tokens['cost_usd'] = vision_cost
            
            metadata = {
                "metadata_version": "1.0",
                "created_at": datetime.now().isoformat(),
                "primary_source": primary_metadata,
                "supplementary_sources": supplementary_metadata
            }
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"\n{'='*120}")
            print(f"✅ 메타데이터 생성 완료!")
            print(f"{'='*120}")
            print(f"📁 출력 파일: {output_path}")
            print(f"📊 주강의자료 페이지: {primary_metadata['total_pages']}개")
            print(f"🖼️  필터링된 이미지: {len(primary_metadata['filtered_images'])}개")
            if supplementary_metadata:
                total_supp_pages = sum(s['total_pages'] for s in supplementary_metadata)
                print(f"📚 보조자료 페이지: {total_supp_pages}개")
            
            # ✅ Vision 토큰 통계 출력
            if vision_tokens:
                print(f"\n💰 Vision API 사용 통계:")
                if 'keyword_extraction' in vision_tokens:
                    print(f"   📝 키워드 추출: {vision_tokens['keyword_extraction']:,} tokens")
                if 'image_filtering' in vision_tokens:
                    print(f"   🔍 이미지 필터링: {vision_tokens['image_filtering']:,} tokens")
                if 'image_description' in vision_tokens:
                    print(f"   📸 이미지 설명 생성: {vision_tokens['image_description']:,} tokens ({vision_tokens['description_count']}개)")
                if 'total' in vision_tokens:
                    print(f"   📊 Total: {vision_tokens['total']:,} tokens")
                if 'cost_usd' in vision_tokens:
                    print(f"   💵 비용: {format_cost(vision_tokens['cost_usd'])}")
            
            print(f"{'='*120}\n")
            
            # ✅ vision_tokens와 함께 반환
            return {
                "metadata_path": str(output_path),
                "vision_tokens": vision_tokens
            }
    
    def _process_primary_source(self, file_path: str) -> Dict[str, Any]:
        """
        주강의자료 처리
        ✅ TXT/URL 지원 추가
        ✅ PPTX 직접 텍스트 추출 (PDF 변환 없이)
        """
        file_path_str = str(file_path)
        
        # 원본 파일 타입 감지
        if file_path_str.startswith(('http://', 'https://')):
            original_file_type = 'url'
            file_path_obj = None
            display_name = file_path_str[:50]
        else:
            file_path_obj = Path(file_path)
            original_file_type = file_path_obj.suffix.lower().replace('.', '')
            display_name = file_path_obj.name
        
        print(f"   📄 파일: {display_name} ({original_file_type})")
        
        # ✅ PPTX는 직접 텍스트 추출 (PDF 변환 시 한글 깨짐 방지)
        if original_file_type == 'pptx':
            print(f"   📝 PPTX 직접 텍스트 추출 중... (PDF 변환 건너뜀)")
            from pptx import Presentation
            
            prs = Presentation(file_path_str)
            pages_text = []
            total_pages = 0
            
            for slide_num, slide in enumerate(prs.slides, 1):
                total_pages += 1
                
                # 슬라이드 제목 추출
                title = "No Title"
                if slide.shapes.title and slide.shapes.title.text.strip():
                    title = slide.shapes.title.text.strip()[:50]
                
                # 페이지 마커
                pages_text.append(f"[MAIN-PAGE {slide_num}: {title}]")
                
                # 슬라이드 내용 추출
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        pages_text.append(shape.text.strip())
                
                pages_text.append("")  # 슬라이드 구분
            
            full_text = "\n".join(pages_text)
            print(f"   ✅ 텍스트 추출 완료: {len(full_text)}자, {total_pages}페이지")
            
            # 이미지는 PPTX 원본에서 추출
            print(f"   🖼️  이미지 처리 중...")
            print(f"      → PPTX 원본에서 직접 추출")
            self.image_filter.extract_keywords_from_document(file_path_str)
            keywords = self.image_filter.document_keywords
            all_images = self._extract_images_from_pptx(file_path_str)
            
        else:
            # 기존 방식: PDF 변환
            print(f"   🔄 파일 처리 중...")
            processed_path = self.converter.convert(file_path_str)
            
            # 2. 텍스트 추출
            print(f"   📝 텍스트 추출 중...")
            text_data = self.text_extractor.extract_with_markers(processed_path, prefix="MAIN")
            full_text = text_data['full_text']
            total_pages = text_data['total_pages']
            print(f"   ✅ 텍스트 추출 완료: {len(full_text)}자")
            
            # 3. 이미지 필터링
            print(f"   🖼️  이미지 처리 중...")
            
            # TXT/URL은 이미지 없음
            if original_file_type in ['txt', 'url']:
                print(f"      → TXT/URL은 이미지 없음, 건너뛰기")
                all_images = []
                keywords = []
            
            elif original_file_type in ['docx', 'pdf']:
                print(f"      → PDF에서 이미지 추출")
                self.image_filter.extract_keywords_from_document(processed_path)
                keywords = self.image_filter.document_keywords
                extractor = UniversalImageExtractor()
                all_images = extractor.extract(processed_path)
            
            else:
                print(f"   ⚠️  지원하지 않는 형식: {original_file_type}")
                all_images = []
                keywords = []
        
        # 4. 필터링 실행 (공통)
        filtered_images = []
        if all_images:
            print(f"   🔍 {len(all_images)}개 이미지 발견, 필터링 시작...")

            for img_meta in all_images:
                decision, reason = self.image_filter.step1_rule_check(img_meta)
                
                if decision == "INCLUDE":
                    img_meta.is_core_content = True
                    img_meta.filter_reason = reason
                    filtered_images.append(img_meta)
                    
                elif decision == "PENDING":
                    ai_result = self.image_filter.step2_gemini_check(img_meta)

                    # 튜플 반환 대응
                    if isinstance(ai_result, tuple):
                        ai_result = ai_result[0]

                    if ai_result.upper().startswith("KEEP"):
                        img_meta.is_core_content = True
                        img_meta.filter_reason = ai_result
                        filtered_images.append(img_meta)
            
            print(f"   ✅ 필터링 완료: {len(filtered_images)}개 선택")
        
        # 5. 이미지 설명 생성
        filtered_image_metadata = []
        
        if filtered_images:
            print(f"   📝 이미지 설명 생성 중... (0/{len(filtered_images)})", end='', flush=True)
            
            # ✅ 이전 토큰 수 저장 (각 이미지당 토큰 추적용)
            prev_tokens = self.image_describer.total_tokens
            
            for i, img_meta in enumerate(filtered_images, 1):
                description = self.image_describer.generate_description(
                    img_meta.image_bytes,
                    img_meta.adjacent_text,
                    keywords
                )
                
                # ✅ 이번 이미지 설명 생성에 사용된 토큰 계산
                current_tokens = self.image_describer.total_tokens - prev_tokens
                
                page_title = self._extract_page_title(
                    img_meta.slide_title,
                    img_meta.adjacent_text
                )
                
                filtered_image_metadata.append({
                    "image_id": img_meta.image_id.replace("S", "MAIN_P").replace("P", "MAIN_P"),
                    "page_number": img_meta.slide_number,
                    "page_title": page_title,
                    "description": description,
                    "filter_stage": "1차 (Rule)" if "Rule" in img_meta.filter_reason else "2차 (AI)",
                    "area_percentage": img_meta.area_percentage
                })
                
                # ✅ 진행 상황과 함께 토큰 정보 출력
                if current_tokens > 0:
                    print(f"\r   📝 이미지 설명 생성 중... ({i}/{len(filtered_images)}) - #{i}: {current_tokens:,} tokens", end='', flush=True)
                else:
                    print(f"\r   📝 이미지 설명 생성 중... ({i}/{len(filtered_images)})", end='', flush=True)
                
                # 다음 이미지를 위해 prev_tokens 업데이트
                prev_tokens = self.image_describer.total_tokens
            
            print()
            
            print(f"\n   {'='*80}")
            print(f"   📊 이미지 설명 생성 완료")
            print(f"      - 처리된 이미지: {len(filtered_images)}개")
            # ✅ 총 토큰 수 출력            
            if self.image_describer.total_tokens > 0:
                avg_tokens = self.image_describer.total_tokens / len(filtered_images) if len(filtered_images) > 0 else 0
                print(f"      - 총 토큰: {self.image_describer.total_tokens:,} tokens")
                print(f"      - 평균: {avg_tokens:.0f} tokens/image")
            else:
                print(f"      ⚠️  토큰 정보 없음 (usage_metadata 미지원 가능성)")
            print(f"   {'='*80}\n")

        # 6. 통계
        total_images = len(all_images)
        passed_images = len(filtered_images)
        
        return {
            "role": "main",
            "filename": display_name if original_file_type == 'url' else (file_path_obj.name if file_path_obj else display_name),
            "file_type": original_file_type,
            "total_pages": total_pages,
            "content": {
                "full_text": full_text
            },
            "filtered_images": filtered_image_metadata,
            "statistics": {
                "total_images_found": total_images,
                "images_passed": passed_images,
                "filter_rate": passed_images / total_images if total_images > 0 else 0
            }
        }
    
    def _process_supplementary_source(self, file_path: str, order: int) -> Dict[str, Any]:
        """
        보조자료 처리
        ✅ PPTX 직접 텍스트 추출 (PDF 변환 없이)
        """
        file_path_str = str(file_path)
        
        # URL과 파일 구분
        if file_path_str.startswith(('http://', 'https://')):
            file_type = 'url'
            display_name = 'Web Content'
            file_path_obj = None
        else:
            file_path_obj = Path(file_path)
            file_type = file_path_obj.suffix.lower().replace('.', '')
            display_name = file_path_obj.name
        
        print(f"   📚 보조자료 {order}: {display_name} ({file_type})")
        
        # ✅ PPTX는 직접 텍스트 추출 (PDF 변환 건너뜀)
        if file_type == 'pptx':
            print(f"      📝 PPTX 직접 텍스트 추출 중... (PDF 변환 건너뜀)")
            from pptx import Presentation
            
            prs = Presentation(file_path_str)
            pages_text = []
            total_pages = 0
            
            for slide_num, slide in enumerate(prs.slides, 1):
                total_pages += 1
                
                # 슬라이드 제목 추출
                title = "No Title"
                if slide.shapes.title and slide.shapes.title.text.strip():
                    title = slide.shapes.title.text.strip()[:50]
                
                # 페이지 마커
                pages_text.append(f"[SUPP{order}-PAGE {slide_num}: {title}]")
                
                # 슬라이드 내용 추출
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        pages_text.append(shape.text.strip())
                
                pages_text.append("")  # 슬라이드 구분
            
            full_text = "\n".join(pages_text)
            print(f"      ✅ 완료 ({total_pages}페이지)")
            
        else:
            # 기존 방식: PDF 변환
            print(f"      🔄 PDF 변환 중...")
            pdf_path = self.converter.convert(file_path_str)
            
            print(f"      📝 텍스트 추출 중...")
            text_data = self.text_extractor.extract_with_markers(pdf_path, prefix=f"SUPP{order}")
            
            full_text = text_data['full_text']
            total_pages = text_data['total_pages']
            
            print(f"      ✅ 완료 ({total_pages}페이지)")
        
        return {
            "order": order,
            "filename": display_name,
            "file_type": file_type,
            "total_pages": total_pages,
            "content": {
                "full_text": full_text
            }
        }
    
    def _extract_images_from_pptx(self, pptx_path: str) -> List[ImageMetadata]:
        """PPTX에서 이미지 메타데이터 추출"""
        extractor = UniversalImageExtractor()
        return extractor.extract(pptx_path)


# CLI 인터페이스
if __name__ == "__main__":
    import sys
    
    print("\n" + "="*120)
    print("🎯 Metadata Generator Node (V2 - pdfplumber)")
    print("="*120)
    
    if len(sys.argv) < 2:
        print("\n사용법:")
        print("  python metadata_generator_node.py <주강의자료> [보조1] [보조2] [보조3]")
        print("\n예시:")
        print("  python metadata_generator_node.py 중등국어1.pptx")
        print("  python metadata_generator_node.py notes.txt")
        print("  python metadata_generator_node.py https://example.com/article")
        print("\n✅ 지원 형식: PPTX, DOCX, PDF, TXT, URL")
        print("="*120 + "\n")
        sys.exit(1)
    
    primary_file = sys.argv[1]
    supplementary_files = sys.argv[2:5] if len(sys.argv) > 2 else None
    
    if not primary_file.startswith('http') and not os.path.exists(primary_file):
        print(f"\n❌ 주강의자료를 찾을 수 없습니다: {primary_file}")
        sys.exit(1)
    
    if supplementary_files:
        for supp in supplementary_files:
            if not supp.startswith('http') and not os.path.exists(supp):
                print(f"\n❌ 보조자료를 찾을 수 없습니다: {supp}")
                sys.exit(1)
    
    try:
        generator = MetadataGenerator()
        output_path = generator.generate(
            primary_file=primary_file,
            supplementary_files=supplementary_files,
            output_path="output/metadata.json"
        )
        
        print(f"✅ 성공!")
        print(f"📁 {output_path}")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)