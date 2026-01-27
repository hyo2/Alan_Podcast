import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.repositories.postgres.prompt_template_repo import PostgresPromptTemplateRepo

logger = logging.getLogger(__name__)

class PromptTemplateService:
    """Prompt 템플릿 서비스 (Repo 호출 래퍼)"""

    @staticmethod
    def get_template(db: Session, style_id: str) -> Optional[Dict]:
        try:
            repo = PostgresPromptTemplateRepo(db)
            template = repo.get_active_template(style_id)
            if template:
                logger.info(f"PostgreSQL 템플릿 로드 성공: {style_id}")
                return {
                    "style_id": template["style_id"],
                    "style_name": template["style_name"],
                    "system_prompt": template["system_prompt"],
                    "user_prompt_template": template["user_prompt_template"],
                }

            logger.warning(f"PostgreSQL에서 템플릿을 찾을 수 없음: {style_id}")
            return None

        except Exception as e:
            logger.error(f"템플릿 조회 중 PostgreSQL 오류 발생: {e}")
            return None

    @staticmethod
    def get_default_template(db: Session) -> Dict:
        template = PromptTemplateService.get_template(db, "explain")
        if not template:
            return {
                "style_id": "explain",
                "style_name": "Basic Explanation (Fallback)",
                "system_prompt": "You are a teacher. Respond in Korean.",
                "user_prompt_template": "Create a dialogue in Korean:\n{combined_text}",
            }
        return template
