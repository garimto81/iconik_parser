"""Slack 알림 모듈."""

import json
import os
from typing import Any

import requests

from utils import load_dotenv


class SlackNotifier:
    """Slack Webhook 알림 발송기."""

    def __init__(self, webhook_url: str | None = None) -> None:
        """
        Args:
            webhook_url: Slack Incoming Webhook URL
        """
        load_dotenv()
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def notify(self, result: dict[str, Any]) -> bool:
        """추출 결과를 Slack으로 알립니다.

        Args:
            result: 추출 결과 dict

        Returns:
            True if notification was sent successfully
        """
        if not self.webhook_url:
            return False

        message = self._build_message(result)
        return self._send(message)

    def _build_message(self, result: dict[str, Any]) -> dict[str, Any]:
        """Slack 메시지를 생성합니다."""
        asset_id = result.get("asset_id", "unknown")
        title = result.get("title", "제목 없음")
        success = result.get("success", False)

        if success:
            output_path = result.get("output_path", "")
            text = (
                f"✅ 서브클립 추출 성공\n"
                f"• 제목: {title}\n"
                f"• Asset ID: {asset_id}\n"
                f"• 출력 경로: {output_path}"
            )
            color = "good"
        else:
            error = result.get("error", "알 수 없는 오류")
            text = (
                f"❌ 서브클립 추출 실패\n"
                f"• 제목: {title}\n"
                f"• Asset ID: {asset_id}\n"
                f"• 오류: {error}"
            )
            color = "danger"

        return {
            "text": text,
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Asset ID", "value": asset_id, "short": True},
                        {
                            "title": "상태",
                            "value": "성공" if success else "실패",
                            "short": True,
                        },
                    ],
                }
            ],
        }

    def _send(self, message: dict[str, Any]) -> bool:
        """Slack Webhook으로 메시지를 전송합니다."""
        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(message),
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False
