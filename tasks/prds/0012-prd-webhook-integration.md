# PRD-0012: iconik Webhook 연동으로 서브클립 자동 추출

**버전**: 1.0.0
**상태**: In Progress
**작성일**: 2026-01-09
**범위(코드)**: repo root
**관련 이슈**: [#1](https://github.com/garimto81/claude/issues/1)

---

## 1. Overview

### 1.1 배경/문제
PRD-0011에서 서브클립 로컬 추출 CLI 도구가 완성되었습니다. 현재는 수동으로 CLI를 실행해야 하므로:

- **수동 실행 필요**: `python extract_subclips.py --json assets.json` 명령 직접 실행
- **실시간 처리 불가**: iconik에서 서브클립 생성 시 즉시 추출 불가
- **워크플로우 단절**: iconik UI ↔ 로컬 추출 도구 간 자동 연동 없음

### 1.2 목표 솔루션(요약)
iconik Webhook을 통해 서브클립 생성 이벤트를 실시간으로 수신하고, 자동으로 로컬 추출을 실행합니다.

```
iconik 서브클립 생성 → Webhook 이벤트 → FastAPI 서버 → extract_subclips 모듈 → Slack 알림
```

---

## 2. Goals

### 2.1 Primary Goals
- **실시간 이벤트 수신**: iconik에서 서브클립 생성 시 Webhook으로 즉시 수신
- **자동 추출 실행**: 기존 extract_subclips 모듈 재사용하여 자동 추출
- **알림 제공**: Slack으로 추출 성공/실패 알림

### 2.2 Non-Goals (현재 범위 제외)
- iconik 메타데이터 업데이트 (추출 완료 후 원본 에셋에 태그 추가)
- 웹 대시보드 UI
- 추출 큐 관리 (Redis 등)
- 다중 인스턴스 배포

---

## 3. User Stories

```
As a 영상 편집자
I want to iconik에서 서브클립 만들면 자동으로 추출되기를 원한다
So that 별도 명령 실행 없이 바로 편집 파일을 얻을 수 있다
```

```
As a 운영 담당자
I want to 서브클립 추출 결과를 Slack으로 알림 받고 싶다
So that 추출 실패 시 빠르게 대응할 수 있다
```

---

## 4. Functional Requirements

### 4.1 Webhook 수신
1. FastAPI 서버가 iconik Webhook을 `/webhook/iconik` 엔드포인트로 수신해야 한다.
2. `object_type: assets`, `operation: CREATE`, `type: SUBCLIP` 이벤트만 처리해야 한다.
3. 그 외 이벤트는 무시하고 200 응답을 반환해야 한다.

### 4.2 서브클립 추출
1. Webhook 데이터에서 서브클립 정보를 추출해야 한다.
2. 기존 `subclip_service.py`를 사용하여 FFmpeg 추출을 실행해야 한다.
3. 추출은 백그라운드에서 비동기로 처리해야 한다.

### 4.3 알림
1. 추출 완료 시 Slack Webhook으로 성공/실패 알림을 전송해야 한다.
2. 알림에는 서브클립 제목, Asset ID, 출력 경로 (또는 에러 메시지)가 포함되어야 한다.

---

## 5. 상세 설계

### 5.1 구성요소(모듈) 및 책임

| 모듈 | 책임 |
|------|------|
| `webhook_server.py` | FastAPI Webhook 수신 서버 |
| `webhook_handler.py` | 이벤트 필터링 로직 |
| `subclip_service.py` | 서브클립 추출 서비스 (기존 모듈 래핑) |
| `slack_notifier.py` | Slack 알림 발송 |

### 5.2 Webhook 페이로드 구조

```json
{
  "object_type": "assets",
  "operation": "CREATE",
  "object_id": "d206796c-4cf3-11f0-a812-fa75e68441df",
  "data": {
    "id": "d206796c-4cf3-11f0-a812-fa75e68441df",
    "title": "WSOP 2025 ... _subclip_ROITER vs LINDE",
    "type": "SUBCLIP",
    "original_asset_id": "ea200c74-4cd6-11f0-9ba5-b61b60fa9865",
    "time_start_milliseconds": 3561433,
    "time_end_milliseconds": 3916333
  }
}
```

### 5.3 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스 체크 |
| POST | `/webhook/iconik` | iconik Webhook 수신 |

### 5.4 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ICONIK_APP_ID` | ✅ | iconik App ID |
| `ICONIK_AUTH_TOKEN` | ✅ | iconik Auth Token |
| `LOCAL_NAS_MOUNT` | ✅ | 로컬 NAS 마운트 경로 |
| `SLACK_WEBHOOK_URL` | ⬜ | Slack Incoming Webhook URL |
| `SUBCLIP_OUTPUT_DIR` | ⬜ | 출력 디렉토리 (기본: ./subclips) |

---

## 6. Technical/Operational Notes

### 6.1 iconik Webhook 설정

iconik Admin에서 Webhook을 다음과 같이 설정합니다:

1. **Settings → Webhooks → Add**
2. 설정:
   - **URL**: `http://<서버IP>:8000/webhook/iconik`
   - **Type**: `assets`
   - **Operation**: `CREATE`
   - **Status**: `ENABLED`

또는 API로 설정:

```bash
curl -X POST "https://app.iconik.io/API/notifications/v1/webhooks/" \
  -H "App-ID: $ICONIK_APP_ID" \
  -H "Auth-Token: $ICONIK_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://<서버IP>:8000/webhook/iconik",
    "object_type": "assets",
    "operation": "CREATE",
    "status": "ENABLED"
  }'
```

### 6.2 서버 실행

```powershell
# 개발 모드
uvicorn webhook_server:app --reload --port 8000

# 프로덕션 모드
uvicorn webhook_server:app --host 0.0.0.0 --port 8000
```

### 6.3 네트워크 요구사항

- Webhook 서버가 iconik 클라우드에서 접근 가능해야 함
- 방화벽에서 8000 포트 오픈 필요
- 또는 ngrok 등 터널링 서비스 사용

---

## 7. Success Metrics

| 지표 | 목표 |
|------|------|
| Webhook 응답 시간 | 1초 이내 응답 |
| 자동 추출 성공률 | 90% 이상 |
| 알림 전송 성공률 | 99% 이상 |

---

## 8. 진행 현황

- [x] PRD 작성
- [x] iconik Webhooks API 조사
- [x] 아키텍처 설계
- [x] TDD 테스트 작성 (14개)
- [x] FastAPI Webhook 서버 구현 (`webhook_server.py`)
- [x] Webhook 핸들러 구현 (`webhook_handler.py`)
- [x] 서브클립 서비스 구현 (`subclip_service.py`)
- [x] Slack 알림 구현 (`slack_notifier.py`)
- [x] 단위 테스트 통과 (14/14)
- [ ] iconik Webhook 설정
- [ ] 통합 테스트 (실제 iconik 연동)
- [ ] 프로덕션 배포

---

## 9. 참조 문서

- [iconik Webhooks Documentation](https://app.iconik.io/docs/webhooks.html)
- [iconik Notifications API](https://app.iconik.io/docs/apidocs.html?url=/docs/notifications/spec/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- PRD-0011: iconik 서브클립 로컬 추출 도구
