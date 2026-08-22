# 디딤하트(DidimHeart)

자립준비청년이 흩어진 지원사업을 빠르게 찾고, 자신에게 맞는 혜택을 **실행 가능한 체크리스트**로 바꾸어 완료하도록 돕는 AI 자립 실행 코파일럿입니다.

**공개 데모 URL (로그인 불필요):**
<https://didimheart.delightfuldesert-be9dc481.koreacentral.azurecontainerapps.io>

- 기준 문서: [PRD.md](./PRD.md) · [TRD.md](./TRD.md) · [AGENTS.md](./AGENTS.md)

## 핵심 흐름 (골든 패스)

프로필 입력(6항목) → 개인화 추천 3건(출처·마지막 확인일 노출) → 실행 계획 생성 → 단계 완료 → 하트 적립 → 후원 임팩트 확인.

## 기술

- **AI**: GitHub Copilot SDK(`github-copilot-sdk`)를 Microsoft Agent Framework(`agent-framework-github-copilot`)의 `GitHubCopilotAgent` 공급자로 실행. `BenefitMatcherAgent`·`ActionPlannerAgent` 두 에이전트가 4개의 읽기 전용 도구(`search_benefits`, `get_benefit_detail`, `compare_benefits`, `get_source_metadata`)만 호출합니다.
- **백엔드**: Python 3.11 + FastAPI. API는 `/api/v1`, 상태 진단은 `/healthz`·`/readyz`·`/status/ai`.
- **프런트엔드**: React + TypeScript + Vite, 모바일 우선(360px~). 빌드 결과를 FastAPI가 정적 서빙.
- **저장소**: 로컬 JSON 파일 저장소(MVP). Cosmos DB는 후속 대상.
- **호스팅**: 단일 Azure Container Apps 컨테이너(포트 8000).

하트 적립·원장 변경 등 상태 변경은 **결정론적 도메인 로직**이 담당하며, AI는 하트 수량을 정하거나 데이터를 쓰지 못합니다. 에이전트 출력은 카탈로그 값으로 후검증하여 존재하지 않는 혜택·출처를 거부합니다.

## 로컬 실행

Python 3.11이 필요합니다(3.10은 `agent-framework-github-copilot`와 비호환).

```powershell
# 1) 백엔드 의존성
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Copilot 인증 토큰 (프런트 번들·로그·저장소에 절대 넣지 않음)
$env:COPILOT_GITHUB_TOKEN = (gh auth token)

# 2) 프런트엔드 빌드 (FastAPI가 web/dist를 서빙)
cd web; npm install; npm run build; cd ..

# 3) 서버 기동
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 브라우저에서 <http://localhost:8000> 접속.
- 개발 중 프런트만 핫리로드하려면 `cd web; npm run dev`(Vite가 `/api`를 8000으로 프록시).

### 테스트

```powershell
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest -q
```

사전 필터(나이/지역/마감), 환각 혜택 ID 거부, 중복 완료 시 하트 1회만 적립, 리버설 계산을 검증합니다.

## 배포

이 구독은 ACR Tasks가 차단되어 있고 로컬에 Docker가 없어, 이미지는 **GitHub Actions 러너**(`.github/workflows/build-image.yml`)에서 빌드해 ACR로 push하고 `az containerapp update`로 배포합니다.

```powershell
az containerapp update `
  --name didimheart --resource-group rg-didimheart `
  --image cabb6d0f60bdacr.azurecr.io/didimheart:<commit-sha>
# COPILOT_GITHUB_TOKEN 은 Container Apps secret 으로 주입
```

- `Dockerfile`: `node:20-alpine`에서 `web/` 빌드 → `python:3.11-slim` 런타임. Copilot 런타임 바이너리는 wheel에 **번들**되어 별도 다운로드가 없습니다(`COPILOT_SKIP_CLI_DOWNLOAD=1`).
- `infra/main.bicep` + `azure.yaml`: 재현 가능한 배포 정의(증빙용).
- 배포 직후 `/status/ai`로 런타임·인증 상태를 비밀값 노출 없이 진단합니다.

## 주의

추천은 **신청 가능성**에 대한 참고이며 공식 수급 자격을 보장하지 않습니다. 하트는 데모 포인트이며 실제 결제·정산은 포함되지 않습니다.