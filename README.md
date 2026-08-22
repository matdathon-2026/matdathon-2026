# 디딤하트(DidimHeart)

자립준비청년이 흩어진 지원사업을 빠르게 찾고, 자신에게 맞는 혜택을 **실행 가능한 체크리스트**로 바꾸어 완료하도록 돕는 AI 자립 실행 코파일럿입니다.

**공개 데모 URL (로그인 불필요):**
<https://api.ambitiouswave-21c719e8.koreacentral.azurecontainerapps.io>

- 기준 문서: [PRD.md](./PRD.md) · [TRD.md](./TRD.md) · [AGENTS.md](./AGENTS.md)

## 핵심 흐름 (골든 패스)

프로필 입력(6항목) → 개인화 추천 3건(출처·마지막 확인일 노출) → 실행 계획 생성 → 단계 완료 → 하트 적립 → 후원 임팩트 확인.

## 기술

- **AI**: GitHub Copilot SDK(`github-copilot-sdk`)를 Microsoft Agent Framework(`agent-framework-github-copilot`)의 `GitHubCopilotAgent` 공급자로 실행. `BenefitMatcherAgent`·`ActionPlannerAgent` 두 에이전트가 4개의 읽기 전용 도구(`search_benefits`, `get_benefit_detail`, `compare_benefits`, `get_source_metadata`)만 호출합니다.
- **백엔드**: Python 3.11 + FastAPI. API는 `/api/v1`, 상태 진단은 `/healthz`·`/readyz`·`/status/ai`.
- **프런트엔드**: React + TypeScript + Vite, 모바일 우선(360px~). 빌드 결과를 FastAPI가 정적 서빙.
- **저장소**: Azure Cosmos DB for NoSQL. 로컬 개발에서만 JSON 저장소로 폴백.
- **수집**: Aspire가 배포한 Azure Container Apps Job이 온통청년과 저장소 스냅샷을 정기 수집·검증·upsert.
- **호스팅**: Azure Container Apps API와 스케줄 수집 Job. 모든 Azure 리소스는 .NET Aspire AppHost에서 선언.

하트 적립·원장 변경 등 상태 변경은 **결정론적 도메인 로직**이 담당하며, AI는 하트 수량을 정하거나 데이터를 쓰지 못합니다. 에이전트 출력은 카탈로그 값으로 후검증하여 존재하지 않는 혜택·출처를 거부합니다.

## 로컬 실행

Python 3.11이 필요합니다(3.10은 `agent-framework-github-copilot`와 비호환).

```powershell
# 1) 백엔드 의존성
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Foundry BYOK: 로컬 Azure CLI 자격증명 사용
az login
$env:FOUNDRY_RESOURCE_URL = "https://<resource>.openai.azure.com"
$env:FOUNDRY_MODEL = "<deployment-name>"

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

인프라의 단일 진실 원천은 `infra/DidimHeart.AppHost/AppHost.cs`입니다. 로컬 Docker 데몬은 사용하지 않고 이미지는 Azure ACR에서 빌드합니다.

```powershell
azd env new didimheart
azd env set AZURE_LOCATION koreacentral
azd provision

# azd provision 출력의 ACR 이름 사용
az acr build --registry <acr-name> --image didimheart:<commit-sha> --file Dockerfile .

$env:DIDIMHEART_IMAGE = "<acr-name>.azurecr.io/didimheart:<commit-sha>"
azd deploy
```

- `Dockerfile`: `node:20-alpine`에서 `web/` 빌드 → `python:3.11-slim` 런타임. Copilot 런타임 바이너리는 wheel에 **번들**되어 별도 다운로드가 없습니다(`COPILOT_SKIP_CLI_DOWNLOAD=1`).
- `azure.yaml` + Aspire AppHost: ACR, Container Apps 환경, API, 스케줄 Job, Cosmos DB, Blob Storage, Foundry 모델과 역할 할당을 생성합니다.
- `az acr build`는 Azure 안에서 이미지를 빌드하므로 로컬 Docker가 필요하지 않습니다.
- 배포 직후 `/status/ai`로 런타임·인증 상태를 비밀값 노출 없이 진단합니다.

## 주의

추천은 **신청 가능성**에 대한 참고이며 공식 수급 자격을 보장하지 않습니다. 하트는 데모 포인트이며 실제 결제·정산은 포함되지 않습니다.