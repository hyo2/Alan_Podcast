# backend/app/repositories/interfaces/prompt_template_repo.py
from __future__ import annotations
from typing import Protocol, Optional, Dict

class PromptTemplateRepo(Protocol):
    def get_active_template(self, style_id: str) -> Optional[Dict]: ...
