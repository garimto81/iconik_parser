"""Webhook 이벤트 처리 로직."""

from typing import Any


class WebhookHandler:
    """iconik Webhook 이벤트 핸들러."""

    TARGET_OBJECT_TYPE = "assets"
    TARGET_OPERATION = "CREATE"
    TARGET_ASSET_TYPE = "SUBCLIP"

    def is_target_event(self, event: dict[str, Any]) -> bool:
        """처리 대상 이벤트인지 확인합니다.

        Args:
            event: Webhook 이벤트 데이터

        Returns:
            True if the event is a subclip create event
        """
        object_type = event.get("object_type", "")
        operation = event.get("operation", "")
        data = event.get("data", {})
        asset_type = data.get("type", "")

        return (
            object_type == self.TARGET_OBJECT_TYPE
            and operation == self.TARGET_OPERATION
            and asset_type == self.TARGET_ASSET_TYPE
        )

    def get_ignore_reason(self, event: dict[str, Any]) -> str:
        """이벤트가 무시되는 이유를 반환합니다.

        Args:
            event: Webhook 이벤트 데이터

        Returns:
            Reason string for ignoring the event
        """
        object_type = event.get("object_type", "")
        operation = event.get("operation", "")
        data = event.get("data", {})
        asset_type = data.get("type", "")

        if object_type != self.TARGET_OBJECT_TYPE:
            return f"Not an asset event (object_type: {object_type})"

        if operation != self.TARGET_OPERATION:
            return f"Not a create operation (operation: {operation})"

        if asset_type != self.TARGET_ASSET_TYPE:
            return f"Not a subclip (asset type: {asset_type})"

        return "Unknown reason"
