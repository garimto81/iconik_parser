# PRD-0010: iconik ↔ Google Sheets 1:1 동기화 및 라운드트립

**버전**: 0.1.0  
**상태**: In Progress  
**작성일**: 2025-12-14  
**범위(코드)**: repo root

---

## 1. Overview

### 1.1 배경/문제
iconik에서 내려받은 에셋(클립) 메타데이터를 사람이 검수/편집한 뒤, 동일한 결과를 재현 가능하게 공유·관리할 방법이 필요합니다. 기존에는 JSON/CSV 산출물이 산발적으로 생성되고, “에셋 1개가 시트에서 정확히 어느 행인지”가 명확히 보장되지 않았습니다.

### 1.2 목표 솔루션(요약)
1) iconik Assets API → JSON export  
2) JSON → Google Sheets 새 탭에 **에셋 1개 = 행 1개(1:1)** 로 작성  
3) 실행 시 **매칭 리포트(행 번호 ↔ asset id/title)** 를 출력하여 검증 가능하게 함  
4) (다음 단계) 시트의 변경 내용을 iconik에 안전하게 반영(dry-run 기본)

---

## 2. Goals

### 2.1 Primary Goals
- **1:1 매핑 보장**: 에셋 개수 = 시트 행 개수(헤더 제외)로 일치
- **검증 가능성**: 매칭 결과(행↔asset)와 컬럼 채움 현황을 출력
- **재실행 안정성**: 탭 이름 충돌 시 타임스탬프 suffix로 항상 “새 탭” 생성

### 2.2 Non-Goals (현재 범위 제외)
- iconik 메타데이터 “스키마/필드 정의” 자동 생성(관리자 권한/별도 API 필요)
- 시트 편집 UI 제공(구글 시트 자체 UI 사용)
- 대규모 변경의 롤백/버전관리(추후 확장 가능)

---

## 3. User Stories
```
As a 운영/검수 담당자
I want to iconik 에셋 메타데이터를 Google Sheets에서 검수/편집하고
So that 팀과 공유하며 일관된 기준으로 수정할 수 있다
```

```
As a 개발자
I want to 시트의 각 행이 어떤 asset에 대응하는지(1:1) 자동으로 리포트되기를
So that 결과가 기존 시트/기준 데이터와 동일한지 빠르게 검증할 수 있다
```

---

## 4. Functional Requirements

### 4.1 iconik → JSON Export
1. `.env` 또는 환경변수로 iconik 인증을 설정할 수 있어야 한다.  
   - 필수: `ICONIK_APP_ID`, `ICONIK_AUTH_TOKEN`
   - 선택: `ICONIK_BASE_URL`, `ICONIK_COLLECTION_ID`, `ICONIK_LIMIT`, `ICONIK_OUTPUT`, `ICONIK_DETAIL=1`
2. 페이지네이션/재시도를 지원해야 한다(일시적 오류/레이트리밋 대응).

### 4.2 JSON → Google Sheets (1:1)
1. 입력 JSON이 `list[dict]` 또는 `{objects/assets: [...]}` 형태여도 처리해야 한다.
2. 시트 헤더는 **기본 헤더 + 실제 `metadata` 키 확장** 방식으로 구성해야 한다.
3. 같은 탭 이름이 이미 존재하면 **새 탭을 생성**하되, 타임스탬프 suffix를 붙여 충돌을 피해야 한다.
4. 실행 결과로 아래를 출력해야 한다.
   - 행 수(헤더 제외), 컬럼 수(기본/확장), 컬럼 채움 TOP, 빈 컬럼 목록
   - 매칭(시트 행 번호 ↔ asset id/title) 전체 또는 미리보기

### 4.3 (다음 단계) Google Sheets → iconik 적용(라운드트립)
1. 시트의 `id` 컬럼으로 asset을 1:1 매칭해야 한다(행 번호가 아닌 ID 기준).
2. 기본 동작은 **dry-run**으로 “변경 예정(diff)”만 출력해야 한다.
3. `--apply` 옵션에서만 실제 iconik 업데이트(PATCH/PUT)를 수행해야 한다.
4. 대상 필드(예: `title`, `time_start_milliseconds`, `time_end_milliseconds`, 메타데이터 키)는 옵션으로 제한 가능해야 한다.
5. 업데이트 결과(성공/실패/스킵, HTTP 코드, 메시지)를 로그로 남겨야 한다.

---

## 5. 상세 설계

### 5.1 구성요소(모듈) 및 책임
- `export_assets.py`
  - iconik Assets API에서 에셋 목록을 페이지네이션으로 수집하여 JSON으로 저장
  - 재시도/백오프(429/5xx) 지원
- `sync_to_sheet.py`
  - iconik export JSON을 Google Sheets “새 탭”에 1:1(에셋 1개 = 행 1개)로 작성
  - 헤더(컬럼)를 `BASE_HEADER` + 실제 `metadata` 키(확장 컬럼)로 구성
  - 매칭 리포트/컬럼 채움 리포트 출력
- (차기) `apply_sheet_to_iconik.py` 또는 `sync_to_sheet.py` 확장
  - Google Sheets 탭을 읽어 iconik에 변경사항을 적용(dry-run 기본)

### 5.2 데이터 모델(입력/출력)
#### 5.2.1 입력 JSON(에셋) 최소 요구
- 각 에셋은 최소 `id`(UUID 문자열)를 포함해야 한다.
- 선택 필드:
  - `title` 또는 `name`
  - `time_start_milliseconds`, `time_end_milliseconds`
  - `metadata`(dict): 키=메타데이터 필드명, 값=문자열/리스트/딕셔너리 등

#### 5.2.2 시트 탭 스키마(헤더/행)
- 1행은 헤더(컬럼명)이며, 2행부터 에셋 데이터가 시작한다.
- 필수 컬럼: `id`
- 기본 컬럼(고정, `BASE_HEADER`):
  - 식별/시간: `id`, `title`, `time_start_ms`, `time_end_ms`, `time_start_S`, `time_end_S`
  - 메타데이터 기본 키: `Description`, `ProjectName`, `Source`, `Year_` 등(프로젝트에서 사용하는 키)
- 파생(derived) 컬럼 규칙:
  - `time_start_S`, `time_end_S`는 `*_ms / 1000`으로 계산된 값이며 **iconik 반영 대상에서 제외**한다.
- 확장 컬럼(동적):
  - 입력 JSON의 `metadata`에서 발견된 키 중 `BASE_HEADER`에 없는 키는 알파벳 순으로 뒤에 추가한다.

### 5.3 iconik → Sheets(1:1) 동기화 플로우
1. JSON 로드(`--json`): `list[dict]` 또는 `{objects/assets: [...]}` 지원
2. 헤더 구성: `BASE_HEADER + (metadata 키 확장)`
3. 행 구성:
   - 각 에셋은 정확히 1행을 생성(순서는 입력 JSON 순서 유지)
   - 값 직렬화 규칙:
     - `list[str|int|float]` → 줄바꿈(`\n`) 연결
     - `dict` 또는 `list[dict|list]` → JSON 문자열로 저장
4. 탭 생성:
   - `--tab` 이름이 이미 존재하면 `_{YYYYMMDD_HHMMSS}` suffix로 새 탭 생성
5. 시트에 `A1`부터 전체 테이블을 한 번에 업데이트(values.update)
6. 실행 후 리포트 출력(요약 + 매칭)

### 5.4 매칭 리포트(검증 출력) 설계
- 기본 출력(미리보기): `--match-preview N`(기본 20)만큼 `row ↔ id/title` 출력
- 전체 출력: `--print-matches`
- 리포트에 포함해야 할 항목:
  - 행 수(헤더 제외), 컬럼 수(기본/확장)
  - 컬럼 채움 TOP 10, 빈 컬럼 목록
  - `row_number(2부터) ↔ asset id/title`

### 5.5 기준 탭 비교(동일성 검증) 설계
- 비교 기준(권장):
  1) `id` 컬럼을 기준으로 두 탭의 에셋 집합/순서가 동일한지 확인  
  2) 겹치는 컬럼(동일 헤더명)만 선택하여 셀 단위로 비교
- 출력:
  - 불일치 셀 수, 상위 N개 불일치 예시(`R{row}C{col}` + 값 diff)
  - 비교 대상 컬럼 목록(공통/좌측만/우측만)

### 5.6 Sheets → iconik 라운드트립(차기) 상세 설계
#### 5.6.1 입력 요구사항
- 탭의 1행 헤더에 `id`가 반드시 존재해야 한다.
- `id`가 비어있거나 중복인 행은 기본 동작에서 **스킵**하고 리포트에 남긴다.

#### 5.6.2 변경 감지(디프) 전략
- 기본 전략(권장): **baseline JSON 기반 diff**
  - iconik에서 export한 JSON(기준 상태)과 시트 값을 비교해 “의도된 변경”을 계산
  - 장점: 에셋당 GET 호출을 줄여 속도/레이트리밋 위험 감소
- 옵션 전략: **live iconik 상태와 재검증**
  - `--verify-live` 옵션에서만 iconik GET을 추가 호출해 충돌(동시 수정) 가능성을 탐지

#### 5.6.3 업데이트 범위(단계적 적용)
- Phase A(우선): Assets 엔드포인트로 수정 가능한 필드만 적용
  - `title`
  - `time_start_milliseconds`, `time_end_milliseconds`
- Phase B(확장): 메타데이터 적용
  - 엔드포인트/권한/페이로드가 확정되기 전까지는 **기본 비활성화**
  - 활성화 시에도 `--allow-metadata` 및 키 allowlist가 필요

#### 5.6.4 안전 장치(필수)
- 기본 모드: `--dry-run`(변경 예정만 출력, 네트워크 쓰기 없음)
- 실제 적용: `--apply` + `--limit N`(선택) + `--ids <id1,id2,...>`(선택)
- 컬럼 allowlist:
  - `--fields title,time_start_ms,time_end_ms,Description,...` 형태로 반영 범위를 제한
- 리포트 파일 출력:
  - 적용 결과를 `reports/roundtrip_YYYYMMDD_HHMMSS.json`로 저장(성공/실패/스킵 사유 포함)

---

## 6. Technical/Operational Notes
- `assets/v1/assets/{asset_id}/`는 `PATCH/PUT`이 가능(Allow 헤더 기준)하나, **메타데이터 쓰기 방식/권한**은 추가 검증이 필요합니다.
- `metadata/v1/assets/{asset_id}/`는 현재 토큰 기준 **admin 전용(403)** 으로 확인되어, 라운드트립 구현 시 권한/엔드포인트를 명확히 해야 합니다.
- Windows 콘솔(cp949)에서 이모지 등 출력 시 인코딩 오류가 발생할 수 있어, 리포트 출력은 안전한 에러 처리(예: `backslashreplace`)가 필요합니다.

---

## 7. Success Metrics
- 시트 작성 시: `rows_written == assets_count`
- 매칭 리포트 출력 시: “행 번호(2부터) ↔ asset id”가 모든 에셋에 대해 생성됨
- 기준 탭과 비교 시: 기본 컬럼(`A1:AI`) 불일치 셀 0개

---

## 8. 진행 현황 (이번 작업 반영)
- 완료: `iconik_parser/AGENTS.md`에 “항상 한글로 응답” 지침 추가 및 사용 가이드 정리
- 완료: `iconik_parser/sync_to_sheet.py` 1:1 매핑/새 탭 생성/매칭 리포트(`--print-matches`) 지원
- 완료: 기존 탭(`iconik_api_export`)과 새 탭(`iconik_export_compare`) 비교 결과, 기본 35컬럼 불일치 0개 확인
- 보류: 시트 → iconik 적용 기능(라운드트립) 구현 및 “메타데이터 쓰기” 엔드포인트/권한 확정

---

## 9. Open Questions
- iconik에서 “메타데이터 값 업데이트”의 공식 엔드포인트/페이로드는 무엇인가?
- 어떤 필드가 실제로 writable이며, 권한(관리자/앱 토큰)에 따라 제한되는 범위는?
- 시트 편집 내용과 iconik 최신 상태가 충돌할 때(동시 수정) 우선순위/정책은?
- 대량 업데이트 시 레이트리밋(429) 처리 정책(백오프/재시도/중단 기준)은?
