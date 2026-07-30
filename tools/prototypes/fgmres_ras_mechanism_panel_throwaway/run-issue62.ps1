param(
  [string] $Output = "",
  [string] $Corpus = "D:\CODE\interp\RapidRBF-wayfinder\issue44-corpus",
  [string] $Reference = "D:\CODE\interp\RapidRBF-issue32\.prototype-cache\issue47\expanded\official-run-30450649081\rapidrbf-repaired-reference-46716da137e6b4a9eaf062cafa8ac3674a411f44-run-30450649081-attempt-1\reference-manifest.v1.json"
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Resolve-Path (Join-Path $prototype "..\..\..")
if ([string]::IsNullOrWhiteSpace($Output)) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $Output = Join-Path $repository ".prototype-cache\results\issue62-coarse4096-$stamp.json"
}
if (Test-Path -LiteralPath $Output) {
  throw "Issue 62 output must be fresh: $Output"
}

& (Join-Path $prototype "run.ps1") `
  -Corpus $Corpus `
  -Reference $Reference `
  -Output $Output `
  -MaximumIterations 100 `
  -Issue62Cohort
if ($LASTEXITCODE -ne 0) {
  throw "Issue 62 frozen cohort failed with exit code $LASTEXITCODE"
}

$evidence = Get-Content -Raw -LiteralPath $Output | ConvertFrom-Json
if ($evidence.schema -ne "RapidRBF/Coarse4096MechanismPanel/v1" -or
    $evidence.runs.Count -ne 18) {
  throw "Issue 62 evidence shape differs"
}
$digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $Output).Hash.ToLowerInvariant()
Write-Host "Issue 62 evidence: $Output"
Write-Host "Issue 62 SHA-256: $digest"
Write-Host "Issue 62 disposition: $($evidence.prototype_disposition)"
