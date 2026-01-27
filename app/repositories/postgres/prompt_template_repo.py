# backend/app/repositories/postgres/prompt_template_repo.py
from __future__ import annotations
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

class PostgresPromptTemplateRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_active_template(self, style_id: str) -> Optional[Dict]:
        q = text("""
            SELECT
                style_id, style_name, system_prompt, user_prompt_template, description,
                is_active, created_at, updated_at
            FROM prompt_templates
            WHERE style_id = :style_id
              AND is_active = true
            LIMIT 1
        """)
        row = self.db.execute(q, {"style_id": style_id}).mappings().one_or_none()
        return dict(row) if row else None
