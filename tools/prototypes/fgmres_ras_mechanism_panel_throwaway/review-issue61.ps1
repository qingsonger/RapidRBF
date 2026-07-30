param(
  [string] $Results = ""
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @((Join-Path $prototype "review_issue61.py"))
if (-not [string]::IsNullOrWhiteSpace($Results)) {
  $arguments += @("--results", $Results)
}
python @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Issue 61 live review failed with exit code $LASTEXITCODE"
}
