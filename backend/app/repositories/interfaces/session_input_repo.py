# backend/app/repositories/interfaces/session_input_repo.py
from __future__ import annotations
from typing import Protocol, Dict, List, Optional

class SessionInputRepo(Protocol):
    def create_input(  # add_input → create_input
        self,
        session_id: str,
        input_key: str,
        role: str,
        title: str | None = None,
        file_type: str | None = None,
        file_size: int | None = None,
        is_link: bool = False,
        link_url: str | None = None,
    ) -> Dict: ...

    def list_inputs(self, session_id: str) -> List[Dict]: ...
    def get_main_input(self, session_id: str) -> Optional[Dict]: ...
    def delete_inputs_by_session(self, session_id: str) -> int: ...