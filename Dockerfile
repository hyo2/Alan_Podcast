# Azure Functions Python 3.11 베이스 이미지
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# 작업 디렉토리 설정
WORKDIR /home/site/wwwroot

# UTF-8 환경 설정
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Azure Functions 설정
ENV AzureWebJobsScriptRoot=/home/site/wwwroot
ENV AzureFunctionsJobHost__Logging__Console__IsEnabled=true

# 시스템 패키지 설치 (ffmpeg + libreoffice 추가)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        build-essential \
        libpq-dev \
        curl \
        ffmpeg \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일만 먼저 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사 (.dockerignore로 .python_packages 제외)
COPY . .

# .python_packages가 혹시 복사되었다면 삭제
RUN rm -rf .python_packages .venv

# 포트 노출
EXPOSE 80

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:80/api/v1/health || exit 1

# Azure Functions 실행
CMD [ "/azure-functions-host/Microsoft.Azure.WebJobs.Script.WebHost" ]
