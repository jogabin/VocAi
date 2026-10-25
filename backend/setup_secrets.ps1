# 최초 1회: .env 의 OLLAMA_API_KEY 를 Secret Manager(ollama-api-key)에 등록하고
#           Cloud Run 서비스 계정이 읽을 수 있게 권한을 줍니다. 키를 바꿨을 때 다시 실행하면 새 버전이 추가됩니다.
$ErrorActionPreference = "Stop"

$API        = $PSScriptRoot
$PROJECT_ID = "vocai-511109"
$SA         = "api-runner@${PROJECT_ID}.iam.gserviceaccount.com"
$SECRET     = "ollama-api-key"

# .env 에서 키 읽기
$line = Get-Content "$API\.env" | Where-Object { $_ -match '^\s*OLLAMA_API_KEY\s*=' } | Select-Object -First 1
if (-not $line) { throw ".env 에 OLLAMA_API_KEY 가 없습니다." }
$key = ($line -split '=', 2)[1]
$key = ($key -replace '\s+#.*$', '').Trim().Trim('"').Trim("'")
if (-not $key) { throw "OLLAMA_API_KEY 값이 비어 있습니다." }

# 줄바꿈 없이 임시 파일에 저장 (키 끝에 줄바꿈이 붙으면 인증 실패)
$tmp = [System.IO.Path]::GetTempFileName()
[System.IO.File]::WriteAllText($tmp, $key)

try {
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    gcloud secrets describe $SECRET --project $PROJECT_ID *> $null
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prev

    if ($exists) {
        gcloud secrets versions add $SECRET --data-file="$tmp" --project $PROJECT_ID
    } else {
        gcloud secrets create $SECRET --data-file="$tmp" --replication-policy=automatic --project $PROJECT_ID
    }
    if ($LASTEXITCODE -ne 0) { throw "시크릿 등록 실패" }

    gcloud secrets add-iam-policy-binding $SECRET `
      --member="serviceAccount:$SA" `
      --role="roles/secretmanager.secretAccessor" `
      --project $PROJECT_ID
    if ($LASTEXITCODE -ne 0) { throw "권한 부여 실패" }
}
finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}
Write-Host "완료: $SECRET 등록 및 $SA 읽기 권한 부여"
