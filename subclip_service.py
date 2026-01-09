"""서브클립 추출 서비스 모듈."""

from typing import Any

from utils import load_dotenv
from iconik_files_api import IconikFilesClient
from path_mapper import PathMapper
from ffmpeg_extractor import FFmpegExtractor, SubclipInfo


class SubclipService:
    """서브클립 추출 서비스.

    기존 extract_subclips.py의 process_subclip 함수를 서비스 클래스로 래핑합니다.
    """

    def __init__(
        self,
        output_dir: str | None = None,
        local_mount: str | None = None,
        ffmpeg_path: str | None = None,
    ) -> None:
        """
        Args:
            output_dir: 출력 디렉토리
            local_mount: 로컬 NAS 마운트 경로
            ffmpeg_path: FFmpeg 실행 파일 경로
        """
        load_dotenv()
        self.files_client = IconikFilesClient()
        self.path_mapper = PathMapper(local_mount=local_mount)
        self.extractor = FFmpegExtractor(
            output_dir=output_dir,
            ffmpeg_path=ffmpeg_path,
        )

    def extract_subclip(
        self,
        subclip_data: dict[str, Any],
        copy_mode: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """서브클립을 추출합니다.

        Args:
            subclip_data: 서브클립 에셋 데이터
            copy_mode: 코덱 복사 모드 (기본: True)
            dry_run: 드라이런 모드 (기본: False)

        Returns:
            추출 결과 dict
        """
        return self._process_subclip(subclip_data, copy_mode, dry_run)

    def _process_subclip(
        self,
        subclip_asset: dict[str, Any],
        copy_mode: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """단일 서브클립을 처리합니다."""
        asset_id = subclip_asset.get("id", "")
        title = subclip_asset.get("title", "")
        original_asset_id = subclip_asset.get("original_asset_id")
        start_ms = subclip_asset.get("time_start_milliseconds", 0)
        end_ms = subclip_asset.get("time_end_milliseconds", 0)

        result = {
            "asset_id": asset_id,
            "title": title,
            "original_asset_id": original_asset_id,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "success": False,
            "output_path": None,
            "source_path": None,
            "error": None,
        }

        if not original_asset_id:
            result["error"] = "original_asset_id가 없습니다"
            return result

        # 1. 원본 파일 정보 조회
        try:
            file_info = self.files_client.get_original_file_info(original_asset_id)
            if not file_info:
                result["error"] = "원본 파일 정보를 찾을 수 없습니다"
                return result
        except Exception as e:
            result["error"] = f"API 조회 실패: {e}"
            return result

        # 2. 로컬 경로로 매핑
        directory_path = file_info.get("directory_path", "")
        filename = file_info.get("original_name") or file_info.get("name", "")

        local_path = self.path_mapper.map_to_local(directory_path, filename)
        result["source_path"] = local_path

        valid, error = self.path_mapper.validate_path(local_path)
        if not valid:
            result["error"] = error
            return result

        # 3. 프레임레이트 정보 (proxies에서 추출)
        frame_rate = None
        proxies = subclip_asset.get("proxies") or []
        if proxies:
            frame_rate_str = proxies[0].get("frame_rate")
            if frame_rate_str:
                try:
                    frame_rate = float(frame_rate_str)
                except ValueError:
                    pass

        # 4. SubclipInfo 생성
        subclip_info = SubclipInfo(
            asset_id=asset_id,
            title=title,
            source_path=local_path,
            start_ms=start_ms,
            end_ms=end_ms,
            frame_rate=frame_rate,
        )

        # 5. FFmpeg 추출 실행
        success, output_path, message = self.extractor.extract(
            subclip_info,
            copy_mode=copy_mode,
            dry_run=dry_run,
        )

        result["success"] = success
        result["output_path"] = output_path
        if not success:
            result["error"] = message
        elif dry_run:
            result["command"] = message

        return result
