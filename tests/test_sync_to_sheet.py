"""sync_to_sheet.py 단위 테스트."""

import json

import pytest

from sync_to_sheet import (
    BASE_HEADER,
    asset_to_row,
    build_header,
    flatten_assets,
    normalize_cell_value,
)


class TestNormalizeCellValue:
    """normalize_cell_value 함수 테스트."""

    def test_none_returns_empty(self):
        """None은 빈 문자열을 반환한다."""
        assert normalize_cell_value(None) == ""

    def test_string_strips_whitespace(self):
        """문자열의 앞뒤 공백을 제거한다."""
        assert normalize_cell_value("  hello  ") == "hello"

    def test_simple_list_joins_with_newline(self):
        """단순 리스트는 줄바꿈으로 연결한다."""
        result = normalize_cell_value(["a", "b", "c"])
        assert result == "a\nb\nc"

    def test_list_with_none_excludes_none(self):
        """리스트 내 None 값은 제외한다."""
        result = normalize_cell_value(["a", None, "b"])
        assert result == "a\nb"

    def test_dict_returns_json(self):
        """딕셔너리는 JSON 문자열로 반환한다."""
        result = normalize_cell_value({"key": "value"})
        assert result == '{"key": "value"}'

    def test_nested_list_returns_json(self):
        """중첩 리스트는 JSON 문자열로 반환한다."""
        result = normalize_cell_value([{"a": 1}, {"b": 2}])
        assert result == '[{"a": 1}, {"b": 2}]'

    def test_numbers_as_string(self):
        """숫자는 문자열로 변환한다."""
        assert normalize_cell_value(42) == "42"
        assert normalize_cell_value(3.14) == "3.14"


class TestBuildHeader:
    """build_header 함수 테스트."""

    def test_empty_assets_returns_base_header(self):
        """에셋이 없으면 BASE_HEADER만 반환한다."""
        result = build_header([])
        assert result == list(BASE_HEADER)

    def test_assets_without_metadata_returns_base_header(self):
        """metadata가 없는 에셋도 BASE_HEADER만 반환한다."""
        assets = [{"id": "1", "title": "Test"}]
        result = build_header(assets)
        assert result == list(BASE_HEADER)

    def test_extends_with_metadata_keys(self):
        """metadata 키로 헤더를 확장한다."""
        assets = [
            {"id": "1", "metadata": {"CustomField": "value", "AnotherField": "value2"}}
        ]
        result = build_header(assets)

        # BASE_HEADER 뒤에 알파벳 순으로 추가
        assert result[-2:] == ["AnotherField", "CustomField"]

    def test_does_not_duplicate_base_header_keys(self):
        """BASE_HEADER에 있는 키는 중복되지 않는다."""
        assets = [{"id": "1", "metadata": {"Description": "value", "NewField": "value2"}}]
        result = build_header(assets)

        # Description은 BASE_HEADER에 있으므로 중복 없음
        assert result.count("Description") == 1
        assert "NewField" in result


class TestAssetToRow:
    """asset_to_row 함수 테스트."""

    def test_extracts_basic_fields(self):
        """기본 필드를 추출한다."""
        asset = {
            "id": "asset-123",
            "title": "Test Asset",
            "time_start_milliseconds": 1000,
            "time_end_milliseconds": 2000,
        }
        header = ["id", "title", "time_start_ms", "time_end_ms", "time_start_S", "time_end_S"]
        row = asset_to_row(asset, header)

        assert row[0] == "asset-123"
        assert row[1] == "Test Asset"
        assert row[2] == "1000"
        assert row[3] == "2000"
        assert row[4] == "1.0"
        assert row[5] == "2.0"

    def test_extracts_metadata_fields(self):
        """metadata 필드를 추출한다."""
        asset = {
            "id": "asset-123",
            "metadata": {"Description": "A test", "CustomField": "custom"},
        }
        header = ["id", "Description", "CustomField"]
        row = asset_to_row(asset, header)

        assert row[0] == "asset-123"
        assert row[1] == "A test"
        assert row[2] == "custom"

    def test_missing_fields_are_empty(self):
        """없는 필드는 빈 문자열이다."""
        asset = {"id": "asset-123"}
        header = ["id", "title", "Description"]
        row = asset_to_row(asset, header)

        assert row[0] == "asset-123"
        assert row[1] == ""
        assert row[2] == ""


class TestFlattenAssets:
    """flatten_assets 함수 테스트."""

    def test_includes_header_as_first_row(self):
        """첫 번째 행은 헤더이다."""
        assets = [{"id": "1", "title": "Test"}]
        header = ["id", "title"]
        rows = flatten_assets(assets, header)

        assert rows[0] == header

    def test_one_asset_per_row(self):
        """에셋 하나당 행 하나를 생성한다."""
        assets = [
            {"id": "1", "title": "First"},
            {"id": "2", "title": "Second"},
        ]
        header = ["id", "title"]
        rows = flatten_assets(assets, header)

        assert len(rows) == 3  # 헤더 + 2 에셋
        assert rows[1] == ["1", "First"]
        assert rows[2] == ["2", "Second"]
