# Repository Guidelines

## 중요: 한국어 응답
- 이 저장소 관련 대화/리뷰/문서화 응답은 항상 한글로 작성합니다.
- PowerShell에서 한글이 깨지면 `Get-Content -Encoding utf8 AGENTS.md`처럼 UTF-8 인코딩을 지정하세요.

## Project Structure & Module Organization
- 루트 폴더에 파이썬 스크립트가 직접 배치된 형태입니다(패키지 구조 없음).
- 주요 스크립트:
  - `export_assets.py`: iconik Assets API → JSON 내보내기
  - `list_collections.py`: iconik Collections 목록을 JSON으로 출력
  - `sync_to_sheet.py`: iconik export JSON → Google Sheets(새 탭) 또는 CSV(`--dry-run`)
  - `test_iconik.py`: iconik 인증/응답 형식 스모크 테스트
- 생성물(대개 커밋 금지): `assets_*.json`, `assets_test.json`, `iconik_export.csv`

## Build, Test, and Development Commands
- 가상환경: `python -m venv .venv` → `.\.venv\Scripts\Activate.ps1`
- 의존성: `pip install requests google-auth google-auth-oauthlib google-api-python-client`
- iconik 설정(`.env`): `ICONIK_APP_ID`, `ICONIK_AUTH_TOKEN` (선택: `ICONIK_BASE_URL`, `ICONIK_COLLECTION_ID`, `ICONIK_LIMIT`, `ICONIK_OUTPUT`)
- 아이코닉 내보내기: `python export_assets.py`
- 시트 동기화: `python sync_to_sheet.py --json assets.json --sheet <SPREADSHEET_ID> --tab iconik_export`
  - 항상 새 탭을 생성(동일 이름이 있으면 타임스탬프 suffix)하고, 1:1(에셋 1개 = 행 1개)로 작성합니다.
  - 실행 후 매칭 리포트(행 번호 ↔ asset id/title, 컬럼 채움 현황)를 출력합니다.
- CSV만 생성: `python sync_to_sheet.py --dry-run > iconik_export.csv`

## Coding Style & Naming Conventions
- Python 3.10+ 기준, 들여쓰기 4칸.
- `snake_case`(함수/변수), `UPPER_SNAKE_CASE`(환경변수), `main()` + `if __name__ == "__main__":` 패턴 유지.

## Testing Guidelines
- 자동 테스트 스위트는 현재 없음. 수동 점검: `python test_iconik.py`
- 테스트 추가 시: `pytest`, 파일명 `test_*.py`

## Commit & Pull Request Guidelines
- 커밋: Conventional Commits(예: `feat(sync): ...`, `fix: ...`, `docs: ...`, `refactor: ...`, `test: ...`)
- PR: 변경 요약 + 검증 방법(명령어) + 샘플 출력(토큰/ID 마스킹) + 비밀정보/대용량 export 미포함 확인

## Security & Configuration Tips
- `.env`/서비스 계정 JSON 등 자격증명은 절대 커밋하지 않습니다.
- 공유용 데이터는 소량 fixture를 만들고, 전체 export는 첨부/커밋하지 않습니다.
