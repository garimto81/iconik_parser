"""utils.py 단위 테스트."""

import os
import tempfile

import pytest

from utils import load_dotenv, normalize_base_url, require_env


class TestLoadDotenv:
    """load_dotenv 함수 테스트."""

    def test_loads_env_file(self, tmp_path):
        """정상적인 .env 파일을 로드할 수 있다."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=hello\nTEST_VAR2=world")

        # 기존 환경 변수 백업
        original = os.environ.get("TEST_VAR")
        original2 = os.environ.get("TEST_VAR2")

        try:
            os.environ.pop("TEST_VAR", None)
            os.environ.pop("TEST_VAR2", None)

            load_dotenv(str(env_file))

            assert os.environ.get("TEST_VAR") == "hello"
            assert os.environ.get("TEST_VAR2") == "world"
        finally:
            # 환경 변수 복원
            if original is not None:
                os.environ["TEST_VAR"] = original
            else:
                os.environ.pop("TEST_VAR", None)
            if original2 is not None:
                os.environ["TEST_VAR2"] = original2
            else:
                os.environ.pop("TEST_VAR2", None)

    def test_strips_quotes(self, tmp_path):
        """따옴표로 감싸진 값을 정리한다."""
        env_file = tmp_path / ".env"
        env_file.write_text('QUOTED_VAR="quoted value"\nSINGLE_QUOTED=\'single\'')

        os.environ.pop("QUOTED_VAR", None)
        os.environ.pop("SINGLE_QUOTED", None)

        try:
            load_dotenv(str(env_file))

            assert os.environ.get("QUOTED_VAR") == "quoted value"
            assert os.environ.get("SINGLE_QUOTED") == "single"
        finally:
            os.environ.pop("QUOTED_VAR", None)
            os.environ.pop("SINGLE_QUOTED", None)

    def test_ignores_comments_and_empty_lines(self, tmp_path):
        """주석과 빈 줄을 무시한다."""
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nVALID_VAR=value\n  \n# another comment")

        os.environ.pop("VALID_VAR", None)

        try:
            load_dotenv(str(env_file))

            assert os.environ.get("VALID_VAR") == "value"
        finally:
            os.environ.pop("VALID_VAR", None)

    def test_does_not_override_existing(self, tmp_path):
        """이미 존재하는 환경 변수는 덮어쓰지 않는다."""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=new_value")

        os.environ["EXISTING_VAR"] = "original_value"

        try:
            load_dotenv(str(env_file))

            assert os.environ.get("EXISTING_VAR") == "original_value"
        finally:
            os.environ.pop("EXISTING_VAR", None)

    def test_handles_missing_file(self):
        """존재하지 않는 파일은 조용히 무시한다."""
        load_dotenv("/nonexistent/path/.env")
        # 예외 없이 통과하면 성공


class TestRequireEnv:
    """require_env 함수 테스트."""

    def test_returns_existing_value(self):
        """존재하는 환경 변수 값을 반환한다."""
        os.environ["TEST_REQUIRE_VAR"] = "test_value"

        try:
            result = require_env("TEST_REQUIRE_VAR")
            assert result == "test_value"
        finally:
            os.environ.pop("TEST_REQUIRE_VAR", None)

    def test_exits_on_missing(self):
        """환경 변수가 없으면 시스템을 종료한다."""
        os.environ.pop("NONEXISTENT_VAR", None)

        with pytest.raises(SystemExit) as exc_info:
            require_env("NONEXISTENT_VAR")

        assert exc_info.value.code == 2


class TestNormalizeBaseUrl:
    """normalize_base_url 함수 테스트."""

    def test_adds_api_suffix(self):
        """API suffix가 없으면 추가한다."""
        result = normalize_base_url("https://app.iconik.io")
        assert result == "https://app.iconik.io/API/"

    def test_handles_trailing_slash(self):
        """trailing slash를 정리한다."""
        result = normalize_base_url("https://app.iconik.io/")
        assert result == "https://app.iconik.io/API/"

    def test_handles_existing_api_suffix(self):
        """이미 /API로 끝나면 슬래시만 추가한다."""
        result = normalize_base_url("https://app.iconik.io/API")
        assert result == "https://app.iconik.io/API/"

    def test_handles_lowercase_api(self):
        """/api (소문자)도 인식한다."""
        result = normalize_base_url("https://app.iconik.io/api")
        assert result == "https://app.iconik.io/api/"

    def test_handles_empty_string(self):
        """빈 문자열도 처리한다."""
        result = normalize_base_url("")
        assert result == "/API/"

    def test_handles_none(self):
        """None도 처리한다."""
        result = normalize_base_url(None)
        assert result == "/API/"
