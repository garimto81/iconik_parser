# PRD-0010 UI 목업 (Mermaid)

이 프로젝트는 현재 CLI 스크립트 중심이지만, 운영/검수 흐름을 표준화하기 위해 “동기화·검증·증명 리포트”를 한 화면에서 다루는 간단한 UI(예: Streamlit/내부 웹) 구성을 가정합니다.

> 참고: Mermaid “다이어그램 프리뷰”는 코드 블록만 렌더링하는 경우가 있어 본문 설명이 안 보일 수 있습니다. 이 파일 전체 텍스트를 보려면 Markdown 프리뷰를 사용하세요.

## 화면/기능 맵
```mermaid
flowchart TB
  Start(["시작"]) --> Config["설정"]
  Config -->|"Sheet ID/탭"| SheetSel["시트 선택/새 탭 생성"]
  Config -->|"iconik/env"| IconikCfg["iconik 설정(.env)"]
  Config -->|"Google Auth"| GoogleCfg["서비스계정/OAuth"]

  SheetSel --> Actions["작업 선택"]
  IconikCfg --> Actions
  GoogleCfg --> Actions

  Actions --> Export["Export: iconik API → JSON"]
  Actions --> Sync["Sync: JSON → Sheet(1:1)"]
  Actions --> Verify["Verify: Sheet ↔ JSON(증명)"]
  Actions --> Roundtrip["Roundtrip: Sheet → iconik<br/>(dry-run 기본)"]

  Export --> Results["결과/리포트"]
  Sync --> Results
  Verify --> Results
  Roundtrip --> Results
```

## Verify 화면 레이아웃(목업)
```mermaid
flowchart LR
  subgraph Controls["상단 컨트롤"]
    A["Sheet ID"] --> B["Tab"]
    C["기준 JSON 경로"] --> D["모드(base/all/common)"]
    E["매칭(order/id)"] --> F["Verify 실행"]
  end
  subgraph Summary["요약"]
    S1["PASS/FAIL"]
    S2["행/컬럼 수"]
    S3["불일치 셀 수"]
  end
  subgraph Proof["증명(해시)"]
    P1["SHA256(expected)"]
    P2["SHA256(actual)"]
  end
  subgraph Details["상세"]
    D1["불일치 예시 TOP N"]
    D2["행 ↔ asset(id/title) 전체 매칭 출력"]
  end

  Controls --> Summary --> Proof --> Details
```

## 데이터 플로우(검증/증명)
```mermaid
sequenceDiagram
  participant U as User
  participant C as CLI/UI
  participant I as iconik API
  participant S as Google Sheets

  U->>C: Export 실행
  C->>I: GET assets (collection/limit)
  I-->>C: assets JSON
  U->>C: Sync 실행
  C->>S: values.update(새 탭, 1:1)
  U->>C: Verify 실행
  C->>S: values.get(탭 전체)
  C->>C: 셀 단위 비교 + SHA256 산출
  C-->>U: PASS/FAIL + 증명 리포트
```

## 설계 의도(다이어그램)

### 1) 왜 “설정”을 먼저 고정하는가
```mermaid
flowchart TB
  U["사용자"] --> Config["설정(재현성 고정)"]
  Config --> Iconik["iconik 연결(.env)"]
  Config --> Google["Google 인증"]
  Config --> Sheet["Sheet ID/탭 규칙"]

  WhyConfig(["왜 설정을 먼저?<br/>검증/증명은 '같은 입력'이 전제"]) -.-> Config
  WhyIconik(["왜 iconik 연결?<br/>API 기준(JSON)을 언제든 재생성"]) -.-> Iconik
  WhyGoogle(["왜 Google 인증?<br/>읽기/쓰기 권한을 사전에 확정"]) -.-> Google
  WhySheet(["왜 시트/탭 고정?<br/>탭이 바뀌면 비교 대상이 달라짐"]) -.-> Sheet

  classDef callout fill:#FFF7E6,stroke:#E0A800,stroke-dasharray: 3 3,color:#333;
  class WhyConfig,WhyIconik,WhyGoogle,WhySheet callout;
```

### 2) 왜 작업을 Export/Sync/Verify/Roundtrip 4개로 나누는가
```mermaid
flowchart LR
  Actions["작업 선택"] --> Export["Export"]
  Actions --> Sync["Sync"]
  Actions --> Verify["Verify"]
  Actions --> Roundtrip["Roundtrip(dry-run)"]

  ExportWhy(["Export<br/>기준 생성: iconik → JSON"]) -.-> Export
  SyncWhy(["Sync<br/>검수/편집: JSON → 시트(1:1)"]) -.-> Sync
  VerifyWhy(["Verify<br/>완전 동일성 증명: 셀 비교 + SHA256"]) -.-> Verify
  RoundtripWhy(["Roundtrip<br/>안전장치: 먼저 diff 확인 후 apply"]) -.-> Roundtrip

  classDef callout fill:#FFF7E6,stroke:#E0A800,stroke-dasharray: 3 3,color:#333;
  class ExportWhy,SyncWhy,VerifyWhy,RoundtripWhy callout;
```

### 3) 왜 Verify 결과를 “요약 → 증명(해시) → 상세” 순서로 보여주는가
```mermaid
flowchart LR
  Controls["컨트롤<br/>Sheet ID/Tab/JSON/모드/매칭"] --> Summary["요약<br/>PASS/FAIL·행/컬럼·불일치 수"]
  Summary --> Proof["증명(해시)<br/>SHA256(expected) vs SHA256(actual)"]
  Proof --> Details["상세<br/>불일치 TOP N·행↔asset 매칭"]

  WhySummary(["왜 요약이 먼저?<br/>운영자는 즉시 판정이 필요"]) -.-> Summary
  WhyProof(["왜 해시를 분리?<br/>결과를 한 줄로 고정·공유"]) -.-> Proof
  WhyDetails(["왜 상세는 마지막?<br/>실패 시에만 디버깅 비용 발생"]) -.-> Details

  classDef callout fill:#FFF7E6,stroke:#E0A800,stroke-dasharray: 3 3,color:#333;
  class WhySummary,WhyProof,WhyDetails callout;
```

### 4) “완벽 매칭 증명(SHA256)”은 어떤 논리로 성립하는가
```mermaid
flowchart TB
  JSON["기준 JSON(assets)"] --> Canon["표준화<br/>컬럼 선택·값 정규화"]
  SheetTab["시트 탭 값"] --> Canon

  Canon --> Exp["expected table"]
  Canon --> Act["actual table"]

  Exp --> H1["SHA256(expected)"]
  Act --> H2["SHA256(actual)"]

  H1 --> Compare{"해시 동일?"}
  H2 --> Compare

  Compare -->|"같음"| PASS["PASS<br/>테이블 전체 동일"]
  Compare -->|"다름"| FAIL["FAIL<br/>diff 출력"]

  WhyCanon(["왜 표준화?<br/>개행/공백/숫자 포맷 차이 오탐 방지"]) -.-> Canon
  WhyHash(["왜 SHA256?<br/>전체 테이블을 짧은 증명값으로 고정"]) -.-> H1

  classDef callout fill:#FFF7E6,stroke:#E0A800,stroke-dasharray: 3 3,color:#333;
  class WhyCanon,WhyHash callout;
```
