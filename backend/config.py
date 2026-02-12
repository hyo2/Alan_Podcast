"""
환경별 설정 관리
- 환경변수 로딩
- 필수 변수 검증
- 타입 변환 및 기본값 설정
"""

import os
from typing import Optional
from pathlib import Path


class Settings:
    """
    애플리케이션 설정 클래스
    
    환경 감지 우선순위:
      1. ENVIRONMENT 환경변수
      2. APP_ENV 환경변수
      3. 기본값: development
    """
    
    def __init__(self):
        # 환경 감지
        self.environment = self._get_environment()
        
        # 환경별 .env 파일 로드 (os.environ 채우기)
        self._load_env_file()
        
        # 내부 서비스 토큰 환경변수 로드
        self.internal_service_token = self._get_required("INTERNAL_SERVICE_TOKEN")
        
        # 서버 설정
        self.port = int(os.getenv("PORT", "4001"))
        
        # 로깅 설정
        self.log_level = os.getenv("LOG_LEVEL", self._get_default_log_level())
        
        # 인증 설정 추가
        self.auth_mode = os.getenv("AUTH_MODE", "mock").lower().strip()
        self.alan_auth_base_url = os.getenv("ALAN_AUTH_BASE_URL", "").strip()
        self.access_policy = os.getenv("ACCESS_POLICY", "pro_only").lower().strip()
        self.pro_role_allowlist = self._parse_pro_roles()

        # CORS 설정
        self.cors_origins = os.getenv("CORS_ORIGINS", "")

        # 백엔드 모드 선택
        self.repo_backend = os.getenv("REPO_BACKEND", "memory").lower().strip()      # memory | postgres
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local").lower().strip()  # local | azure

        # DB 설정 (postgres 모드면 필수)
        self.database_url = os.getenv("DATABASE_URL", "")
        if self.repo_backend == "postgres":
            self.database_url = self._get_required("DATABASE_URL")

        # Azure Storage 설정 (azure 모드면 필수)
        self.azure_storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        self.azure_storage_container = os.getenv("AZURE_STORAGE_CONTAINER", "")
        if self.storage_backend == "azure":
            self.azure_storage_connection_string = self._get_required("AZURE_STORAGE_CONNECTION_STRING")
            self.azure_storage_container = self._get_required("AZURE_STORAGE_CONTAINER")
        
        # 설정 로드 완료 로그
        print(f"     환경 설정 로드 완료: {self.environment}")
        print(f"   - 포트: {self.port}")
        print(f"   - 로그 레벨: {self.log_level}")
        print(f"   - AUTH_MODE: {self.auth_mode}")
        print(f"   - ACCESS_POLICY: {self.access_policy}")
        print(f"   - REPO_BACKEND: {self.repo_backend}")
        print(f"   - STORAGE_BACKEND: {self.storage_backend}")
    
    def _get_environment(self) -> str:
        """
        현재 실행 환경을 판별
        
        Returns:
            development | staging | production
        """
        env = (
            os.getenv("ENVIRONMENT")
            or os.getenv("APP_ENV")
            or "development"
        ).lower()
        
        # 별칭 정규화
        alias = {
            "dev": "development",
            "local": "development",
            "prod": "production",
            "stage": "staging",
        }
        return alias.get(env, env)
    
    def _load_env_file(self) -> None:
        """
        환경별 .env 파일 로드
        
        우선순위:
          1. .env.{environment} (예: .env.production)
          2. .env (공통)
        
        Note: Azure Functions에서는 .env 파일이 배포되지 않으므로
              모든 환경변수가 App Settings에서 주입됩니다.
        """
        try:
            backend_dir = Path(__file__).parent
            env_file = backend_dir / f".env.{self.environment}"
            
            # 환경별 파일이 있으면 로드
            if env_file.exists():
                print(f"환경 파일 로드: {env_file}")
                self._load_dotenv(env_file)
            else:
                # 없으면 기본 .env 파일 사용
                default_env = backend_dir / ".env"
                if default_env.exists():
                    print(f"기본 환경 파일 로드: {default_env}")
                    self._load_dotenv(default_env)
                else:
                    # Azure Functions 등 클라우드 환경에서는 파일이 없을 수 있음
                    print(f"⚠️ .env 파일 없음 (정상 - App Settings 사용 중)")
        except Exception as e:
            # .env 로딩 실패해도 계속 진행 (App Settings가 있으면 됨)
            print(f"⚠️ .env 파일 로딩 실패 (정상 - App Settings 사용 중): {e}")
    
    def _load_dotenv(self, filepath: Path) -> None:
        """
        .env 파일을 읽어서 환경변수로 설정
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 주석이나 빈 줄 무시
                    if not line or line.startswith('#'):
                        continue
                    
                    # KEY=VALUE 형태 파싱
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 따옴표 제거
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # 1) .env에 값이 비어 있으면 덮어쓰지 않음
                        if value == "":
                            continue

                        # 2) 이미 환경변수에 값이 있으면(docker/env_file/local.settings로 주입됨) 덮어쓰지 않음
                        existing = os.environ.get(key)
                        if existing is not None and existing != "":
                            continue
                        
                        os.environ[key] = value
        except Exception as e:
            print(f"환경 파일 로드 실패: {e}")
    
    def _get_required(self, key: str) -> str:
        """
        필수 환경변수 가져오기
        
        Args:
            key: 환경변수 이름
            
        Returns:
            환경변수 값
            
        Raises:
            ValueError: 환경변수가 없을 때
        """
        value = os.getenv(key)
        if not value:
            error_msg = (
                f"❌ 필수 환경변수 누락: {key}\n"
                f"   Environment: {self.environment}\n"
                f"   Azure Functions App Settings에서 {key}를 확인하세요."
            )
            print(error_msg)  # stdout에도 출력 (로그 확인용)
            raise ValueError(error_msg)
        return value
    
    def _get_default_log_level(self) -> str:
        """
        환경별 기본 로그 레벨 반환
        
        Returns:
            DEBUG | INFO | WARNING
        """
        defaults = {
            "development": "DEBUG",
            "staging": "INFO",
            "production": "WARNING"
        }
        return defaults.get(self.environment, "INFO")
    
    def _parse_pro_roles(self) -> set[str]:
        """
        Pro로 간주하는 Role 목록 파싱
        
        Returns:
            set[str]: Pro role 목록 (소문자 변환됨)
        """
        default_roles = {"pro_user", "internal_user", "pro_user_promotion"}
        
        raw = os.getenv("PRO_ROLE_ALLOWLIST", "").strip()
        if not raw:
            return default_roles
        
        # 쉼표로 구분된 문자열을 set으로 변환
        roles = {r.strip().lower() for r in raw.split(",") if r.strip()}
        return roles or default_roles
    
    @property
    def is_mock_mode(self) -> bool:
        """Mock 인증 모드 여부"""
        return self.auth_mode == "mock"
    
    @property
    def is_pro_only_policy(self) -> bool:
        """Pro 전용 정책 여부"""
        return self.access_policy == "pro_only"
    
    def is_pro_role(self, role: str) -> bool:
        """
        주어진 role이 Pro 등급인지 확인
        
        Args:
            role: 확인할 role 문자열
            
        Returns:
            bool: Pro role이면 True
        """
        return (role or "").strip().lower() in self.pro_role_allowlist

    def __repr__(self) -> str:
        """설정 정보 출력 (민감 정보 제외)"""
        return (
            f"Settings(\n"
            f"  environment={self.environment}\n"
            f"  port={self.port}\n"
            f"  log_level={self.log_level}\n"
            f"  repo_backend={self.repo_backend}\n"
            f"  storage_backend={self.storage_backend}\n"
            f"  auth_mode={self.auth_mode}\n"
            f"  access_policy={self.access_policy}\n"
            f"  cors_origins={self.cors_origins or '(not set)'}\n"
            f")"
        )
        


# 전역 설정 인스턴스
settings = Settings()