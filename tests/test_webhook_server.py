"""webhook_server.py 단위 테스트."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestWebhookEndpoint:
    """Webhook 엔드포인트 테스트."""

    @pytest.fixture
    def client(self):
        """테스트용 FastAPI 클라이언트."""
        from webhook_server import app

        return TestClient(app)

    def test_health_check(self, client):
        """헬스 체크 엔드포인트가 동작한다."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_webhook_accepts_valid_asset_create(self, client):
        """유효한 asset create 이벤트를 수락한다."""
        payload = {
            "object_type": "assets",
            "operation": "CREATE",
            "object_id": "d206796c-4cf3-11f0-a812-fa75e68441df",
            "data": {
                "id": "d206796c-4cf3-11f0-a812-fa75e68441df",
                "title": "Test Subclip",
                "type": "SUBCLIP",
                "original_asset_id": "ea200c74-4cd6-11f0-9ba5-b61b60fa9865",
                "time_start_milliseconds": 3561433,
                "time_end_milliseconds": 3916333,
            },
        }

        response = client.post("/webhook/iconik", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    def test_webhook_ignores_non_subclip_assets(self, client):
        """SUBCLIP이 아닌 asset은 무시한다."""
        payload = {
            "object_type": "assets",
            "operation": "CREATE",
            "object_id": "test-id",
            "data": {
                "id": "test-id",
                "title": "Regular Asset",
                "type": "ASSET",
            },
        }

        response = client.post("/webhook/iconik", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert "not a subclip" in response.json()["reason"].lower()

    def test_webhook_ignores_non_create_operations(self, client):
        """CREATE가 아닌 operation은 무시한다."""
        payload = {
            "object_type": "assets",
            "operation": "UPDATE",
            "object_id": "test-id",
            "data": {
                "id": "test-id",
                "title": "Test Subclip",
                "type": "SUBCLIP",
            },
        }

        response = client.post("/webhook/iconik", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_webhook_rejects_invalid_payload(self, client):
        """잘못된 payload는 거부한다 (422 Unprocessable Entity)."""
        response = client.post("/webhook/iconik", json={"invalid": "data"})

        assert response.status_code == 422

    def test_webhook_returns_422_for_missing_fields(self, client):
        """필수 필드가 없으면 422를 반환한다."""
        payload = {
            "object_type": "assets",
            # operation 누락
            "object_id": "test-id",
        }

        response = client.post("/webhook/iconik", json=payload)

        assert response.status_code == 422


class TestWebhookHandler:
    """WebhookHandler 클래스 테스트."""

    def test_is_target_event_returns_true_for_subclip_create(self):
        """SUBCLIP 생성 이벤트를 올바르게 식별한다."""
        from webhook_handler import WebhookHandler

        handler = WebhookHandler()
        event = {
            "object_type": "assets",
            "operation": "CREATE",
            "data": {"type": "SUBCLIP"},
        }

        assert handler.is_target_event(event) is True

    def test_is_target_event_returns_false_for_regular_asset(self):
        """일반 asset은 대상이 아니다."""
        from webhook_handler import WebhookHandler

        handler = WebhookHandler()
        event = {
            "object_type": "assets",
            "operation": "CREATE",
            "data": {"type": "ASSET"},
        }

        assert handler.is_target_event(event) is False

    def test_is_target_event_returns_false_for_update(self):
        """UPDATE operation은 대상이 아니다."""
        from webhook_handler import WebhookHandler

        handler = WebhookHandler()
        event = {
            "object_type": "assets",
            "operation": "UPDATE",
            "data": {"type": "SUBCLIP"},
        }

        assert handler.is_target_event(event) is False


class TestSubclipService:
    """SubclipService 클래스 테스트."""

    def test_extract_subclip_returns_result(self):
        """서브클립 추출 결과를 반환한다."""
        from subclip_service import SubclipService

        service = SubclipService()

        subclip_data = {
            "id": "test-id",
            "title": "Test Subclip",
            "type": "SUBCLIP",
            "original_asset_id": "original-id",
            "time_start_milliseconds": 0,
            "time_end_milliseconds": 10000,
        }

        with patch.object(service, "_process_subclip") as mock_process:
            mock_process.return_value = {
                "asset_id": "test-id",
                "success": True,
                "output_path": "/path/to/output.mp4",
            }

            result = service.extract_subclip(subclip_data)

        assert result["success"] is True
        assert result["asset_id"] == "test-id"

    def test_extract_subclip_handles_error(self):
        """추출 실패 시 에러를 처리한다."""
        from subclip_service import SubclipService

        service = SubclipService()

        subclip_data = {
            "id": "test-id",
            "title": "Test Subclip",
            "type": "SUBCLIP",
            # original_asset_id 누락
        }

        result = service.extract_subclip(subclip_data)

        assert result["success"] is False
        assert result["error"] is not None


class TestSlackNotifier:
    """SlackNotifier 클래스 테스트."""

    def test_send_success_notification(self):
        """성공 알림을 전송한다."""
        from slack_notifier import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")

        result = {
            "asset_id": "test-id",
            "title": "Test Subclip",
            "success": True,
            "output_path": "/path/to/output.mp4",
        }

        with patch("slack_notifier.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            notifier.notify(result)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = json.loads(call_args[1]["data"])
            assert "성공" in payload["text"] or "success" in payload["text"].lower()

    def test_send_failure_notification(self):
        """실패 알림을 전송한다."""
        from slack_notifier import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")

        result = {
            "asset_id": "test-id",
            "title": "Test Subclip",
            "success": False,
            "error": "파일을 찾을 수 없습니다",
        }

        with patch("slack_notifier.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            notifier.notify(result)

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            payload = json.loads(call_args[1]["data"])
            assert "실패" in payload["text"] or "failed" in payload["text"].lower()

    def test_skip_notification_when_url_not_set(self):
        """URL이 설정되지 않으면 알림을 건너뛴다."""
        from slack_notifier import SlackNotifier

        notifier = SlackNotifier(webhook_url=None)

        result = {"asset_id": "test-id", "success": True}

        with patch("slack_notifier.requests.post") as mock_post:
            notifier.notify(result)

            mock_post.assert_not_called()
