param(
  [ValidateRange(1, 100)]
  [int] $MaximumIterations = 8
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Resolve-Path (Join-Path $prototype "..\..\..")
$stamp = Get-Date -Format "yyyyMMdd-HHmmss-ffff"
$output = Join-Path $repository (
  ".prototype-cache\results\issue61-repro-$stamp.json"
)

& (Join-Path $prototype "run.ps1") `
  -Quick `
  -Workload "M3-HERMITE-10K" `
  -MaximumIterations $MaximumIterations `
  -Output $output
if ($LASTEXITCODE -ne 0) {
  throw "Issue 61 reproduction command failed before producing a verdict"
}

$evidence = Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
$run = $evidence.runs | Select-Object -First 1
$red = (
  $run.workload_id -eq "M3-HERMITE-10K" -and
  $run.topology -eq "frozen-residual-correction-ras" -and
  $run.status -eq "WORK_BUDGET_EXHAUSTED" -and
  -not $run.bound_certificate.pass -and
  $run.bound_certificate.gradient_residual -gt 1.0
)

Write-Output (
  "workload={0} topology={1} iterations={2} status={3}" -f
  $run.workload_id, $run.topology, $run.iterations, $run.status
)
Write-Output (
  "value_residual={0:E16} gradient_residual={1:E16} cpd_eta={2:E16}" -f
  $run.bound_certificate.value_residual,
  $run.bound_certificate.gradient_residual,
  $run.bound_certificate.cpd_eta
)
Write-Output ("evidence=" + $output)

if ($red) {
  Write-Error "RED: the isolated M3 mixed-gradient mechanism gap reproduced"
}

throw "The expected Issue 61 failure signature did not reproduce"
