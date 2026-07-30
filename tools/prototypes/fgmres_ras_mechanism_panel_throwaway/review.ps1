param(
  [string] $Panel = "",
  [string] $Audit = ""
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @((Join-Path $prototype "review.py"))
if (-not [string]::IsNullOrWhiteSpace($Panel)) {
  $arguments += @("--panel", $Panel)
}
if (-not [string]::IsNullOrWhiteSpace($Audit)) {
  $arguments += @("--audit", $Audit)
}
python @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Live review failed with exit code $LASTEXITCODE"
}
