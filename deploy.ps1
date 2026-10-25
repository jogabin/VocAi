$ErrorActionPreference = "Stop"

$VUE        = Join-Path $PSScriptRoot "frontend"
$API        = Join-Path $PSScriptRoot "backend"
$PROJECT_ID = "vocai-511109"
$REGION     = "asia-northeast3"
$INSTANCE   = "vocai"
$SERVICE    = "myapp"
$SA         = "api-runner@${PROJECT_ID}.iam.gserviceaccount.com"

# LLM 설정 (Cloud Run 환경변수). API 키는 Secret Manager(ollama-api-key)에서 주입
$ENV_VARS = "LLM_PROVIDER=ollama,OLLAMA_MODEL=gemma4:31b,AGENT_STEP_DELAY_SEC=1.0"
$SECRETS  = "DATABASE_URL=database-url:latest,OLLAMA_API_KEY=ollama-api-key:latest"

# 0) 서비스 주소 → APP_BASE_URL (메신저 알림의 '장애 상세' 링크 주소)
#    이미 배포된 서비스의 주소를 읽어 넣습니다. 최초 배포라 주소가 없으면 경고만 하고 진행 → 배포 후 한 번 더 실행
$prevEap = $ErrorActionPreference; $ErrorActionPreference = "Continue"
$URL = gcloud run services describe $SERVICE --region $REGION --project $PROJECT_ID --format "value(status.url)" 2>$null
$ErrorActionPreference = $prevEap
if ($URL) {
    $ENV_VARS += ",APP_BASE_URL=$URL"
    Write-Host "APP_BASE_URL = $URL"
} else {
    Write-Warning "서비스 주소를 읽지 못했습니다(최초 배포?). 메신저 링크가 localhost로 나가므로 배포 후 이 스크립트를 한 번 더 실행하세요."
}

# 1) Vue 빌드
Push-Location $VUE
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "Vue 빌드 실패" }
Pop-Location

# 2) 잘못된 API 주소가 박혔는지 점검 (127.0.0.1이 있으면 중단)
if (Select-String -Path "$VUE\dist\assets\*.js" -Pattern "127\.0\.0\.1" -Quiet) {
    throw "dist에 127.0.0.1 주소가 들어 있습니다. .env.production을 확인하세요."
}

# 3) dist를 FastAPI 폴더의 static으로 복사
Remove-Item "$API\static" -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item "$VUE\dist" "$API\static" -Recurse

# 4) 이미지 빌드 + Cloud Run 배포
#    --no-cpu-throttling : 상담이력 등록 응답 후 백그라운드로 도는 에이전트(LangGraph)가
#                          느려지지 않도록 CPU를 항상 할당 (인스턴스가 떠 있는 동안 과금)
Push-Location $API
gcloud run deploy $SERVICE `
  --source . `
  --region $REGION `
  --service-account $SA `
  --add-cloudsql-instances "${PROJECT_ID}:${REGION}:${INSTANCE}" `
  --set-secrets $SECRETS `
  --set-env-vars $ENV_VARS `
  --no-cpu-throttling `
  --memory 1Gi `
  --max-instances 3 `
  --allow-unauthenticated
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { throw "Cloud Run 배포 실패" }
