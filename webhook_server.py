"""iconik Webhook 수신 서버.

사용법:
    # 개발 모드로 실행
    uvicorn webhook_server:app --reload --port 8000

    # 프로덕션 모드로 실행
    uvicorn webhook_server:app --host 0.0.0.0 --port 8000

환경 변수:
    SLACK_WEBHOOK_URL: Slack Incoming Webhook URL (선택)
    SUBCLIP_OUTPUT_DIR: 서브클립 출력 디렉토리 (기본: ./subclips)
    LOCAL_NAS_MOUNT: 로컬 NAS 마운트 경로
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from utils import configure_stdio, load_dotenv
from webhook_handler import WebhookHandler
from subclip_service import SubclipService
from slack_notifier import SlackNotifier

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Pydantic 모델
class WebhookPayload(BaseModel):
    """iconik Webhook 페이로드."""

    object_type: str = Field(..., description="이벤트 대상 타입 (예: assets)")
    operation: str = Field(..., description="작업 유형 (CREATE, UPDATE, DELETE)")
    object_id: str = Field(..., description="대상 객체 ID")
    data: dict[str, Any] = Field(default_factory=dict, description="객체 데이터")


class WebhookResponse(BaseModel):
    """Webhook 응답."""

    status: str
    message: str | None = None
    reason: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HealthResponse(BaseModel):
    """헬스 체크 응답."""

    status: str
    version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# 전역 서비스 인스턴스
webhook_handler = WebhookHandler()
subclip_service: SubclipService | None = None
slack_notifier: SlackNotifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리."""
    global subclip_service, slack_notifier

    # 시작
    load_dotenv()
    configure_stdio()

    subclip_service = SubclipService()
    slack_notifier = SlackNotifier()

    logger.info("Webhook 서버 시작")
    yield

    # 종료
    logger.info("Webhook 서버 종료")


app = FastAPI(
    title="iconik Webhook Server",
    description="iconik 서브클립 생성 이벤트를 수신하여 자동으로 추출합니다.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """헬스 체크 엔드포인트."""
    return HealthResponse(status="healthy")


@app.post("/webhook/iconik", response_model=WebhookResponse)
async def receive_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
):
    """iconik Webhook을 수신합니다.

    서브클립 생성 이벤트만 처리하고, 나머지는 무시합니다.
    """
    event = payload.model_dump()
    logger.info(
        f"Webhook 수신: object_type={payload.object_type}, "
        f"operation={payload.operation}, object_id={payload.object_id}"
    )

    # 대상 이벤트 확인
    if not webhook_handler.is_target_event(event):
        reason = webhook_handler.get_ignore_reason(event)
        logger.info(f"이벤트 무시: {reason}")
        return WebhookResponse(status="ignored", reason=reason)

    # 백그라운드에서 추출 처리
    background_tasks.add_task(process_subclip_async, payload.data)

    return WebhookResponse(
        status="accepted",
        message=f"서브클립 추출 작업이 시작되었습니다: {payload.object_id}",
    )


async def process_subclip_async(subclip_data: dict[str, Any]) -> None:
    """백그라운드에서 서브클립을 추출합니다."""
    asset_id = subclip_data.get("id", "unknown")
    title = subclip_data.get("title", "")

    logger.info(f"서브클립 추출 시작: {title} ({asset_id})")

    try:
        # 동기 함수를 스레드 풀에서 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: subclip_service.extract_subclip(subclip_data),
        )

        if result["success"]:
            logger.info(f"서브클립 추출 완료: {result['output_path']}")
        else:
            logger.error(f"서브클립 추출 실패: {result['error']}")

        # Slack 알림
        if slack_notifier:
            await loop.run_in_executor(None, lambda: slack_notifier.notify(result))

    except Exception as e:
        logger.exception(f"서브클립 추출 중 예외 발생: {e}")

        # 실패 알림
        if slack_notifier:
            error_result = {
                "asset_id": asset_id,
                "title": title,
                "success": False,
                "error": str(e),
            }
            slack_notifier.notify(error_result)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
