"""공통 유틸리티 함수 모듈."""

import os
import sys


def configure_stdio() -> None:
    """Windows 콘솔의 UTF-8 인코딩 및 에러 처리를 설정합니다."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            try:
                stream.reconfigure(errors="backslashreplace")
            except Exception:
                pass


def load_dotenv(path: str = ".env") -> None:
    """환경 변수 파일(.env)을 로드합니다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    """필수 환경 변수를 가져옵니다. 없으면 종료합니다."""
    value = os.getenv(name)
    if not value:
        print(f"Missing env var: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def normalize_base_url(base_url: str) -> str:
    """iconik API base URL을 정규화합니다."""
    normalized = (base_url or "").rstrip("/")
    if not normalized.lower().endswith("/api"):
        return normalized + "/API/"
    return normalized + "/"
