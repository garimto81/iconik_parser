# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 언어

모든 대화/리뷰/문서화 응답은 **한글**로 작성. 기술 용어(iconik, Google Sheets, API 등)는 영어 유지.

---

## 프로젝트 개요

iconik 에셋 메타데이터를 Google Sheets와 동기화하는 CLI 도구 모음. **에셋 1개 = 시트 행 1개(1:1)** 매핑을 보장하고, 셀 단위 검증/SHA256 증명을 제공.

### 핵심 흐름
```
iconik API → JSON export → Google Sheets 새 탭(1:1) → 검증(셀 비교 + SHA256)
```

---

## 스크립트 및 명령어

### 환경 설정
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests google-auth google-auth-oauthlib google-api-python-client
```

### `.env` 필수 변수
```
ICONIK_APP_ID=...
ICONIK_AUTH_TOKEN=...
```

### `.env` 선택 변수
```
ICONIK_BASE_URL=https://app.iconik.io/API/
ICONIK_COLLECTION_ID=...
ICONIK_LIMIT=0
ICONIK_OUTPUT=assets.json
ICONIK_DETAIL=0
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json
GOOGLE_SHEET_ID=...
```

### 주요 명령어

| 스크립트 | 용도 | 예시 |
|----------|------|------|
| `export_assets.py` | iconik → JSON 내보내기 | `python export_assets.py` |
| `list_collections.py` | 컬렉션 목록 조회 | `python list_collections.py` |
| `sync_to_sheet.py` | JSON → 시트 동기화(새 탭 생성) | `python sync_to_sheet.py --json assets.json --sheet <ID> --tab iconik_export` |
| `sync_to_sheet.py --dry-run` | CSV 출력만 | `python sync_to_sheet.py --dry-run > out.csv` |
| `verify_sheet_matches.py` | 시트 ↔ JSON 셀 단위 검증 | `python verify_sheet_matches.py --json assets.json --sheet <ID> --tab iconik_export --mode base` |
| `test_iconik.py` | iconik 인증/응답 스모크 테스트 | `python test_iconik.py` |

---

## 아키텍처

### 모듈 구조 (패키지 없음, 루트 스크립트)

```
export_assets.py    ← iconik API 페이지네이션/재시도 처리
sync_to_sheet.py    ← 헤더 구성(BASE_HEADER + 동적 metadata 키), 값 직렬화, 매칭 리포트
verify_sheet_matches.py ← 셀 비교, SHA256 증명, 불일치 리포트
```

### 주요 데이터 흐름

1. **Export**: `export_assets.py`가 iconik `/assets/v1/assets/` 엔드포인트를 페이지네이션으로 호출, JSON 파일 출력
2. **Sync**: `sync_to_sheet.py`가 JSON을 읽어 Google Sheets API로 새 탭 생성(동일 이름 시 타임스탬프 suffix)
3. **Verify**: `verify_sheet_matches.py`가 시트 값과 JSON을 셀 단위 비교, SHA256 해시로 동일성 증명

### 헤더 구성 규칙

`sync_to_sheet.py`의 `BASE_HEADER`(35개 고정 컬럼) + 입력 JSON `metadata` 키에서 발견된 추가 키(알파벳 순)

### 값 직렬화 규칙 (`normalize_cell_value`)

- `list[str|int|float]` → 줄바꿈(`\n`) 연결
- `dict` 또는 `list[dict|list]` → JSON 문자열

---

## 검증 모드 (verify_sheet_matches.py)

| 모드 | 설명 |
|------|------|
| `base` | BASE_HEADER 35컬럼만 비교 |
| `all` | JSON에서 파생된 전체 헤더 비교 |
| `common` | 시트와 JSON의 공통 컬럼만 비교 |
| `auto` | 헤더 일치 여부에 따라 자동 선택 |

---

## 코딩 스타일

- Python 3.10+ 기준, 들여쓰기 4칸
- `snake_case`(함수/변수), `UPPER_SNAKE_CASE`(환경변수)
- `main()` + `if __name__ == "__main__":` 패턴 유지

---

## 테스트

- 자동 테스트 스위트 없음. 수동 점검: `python test_iconik.py`
- 테스트 추가 시: `pytest`, 파일명 `test_*.py`

---

## 커밋/PR 규칙

- Conventional Commits: `feat(sync):`, `fix:`, `docs:`, `refactor:`, `test:`
- PR 작성 시: 변경 요약 + 검증 방법(명령어) + 샘플 출력(토큰/ID 마스킹)

---

## 주의 사항

- 생성물 파일(`assets_*.json`, `iconik_export.csv`) 커밋 금지
- `.env`, 서비스 계정 JSON 등 자격증명 커밋 금지
- Windows 콘솔(cp949) 한글/이모지 출력 시 `errors="backslashreplace"` 처리 필요
- PowerShell UTF-8 인코딩: `Get-Content -Encoding utf8 <file>`
