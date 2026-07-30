param(
  [string] $Evidence = "",
  [switch] $Snapshot
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @((Join-Path $prototype "review_issue62.py"))
if (-not [string]::IsNullOrWhiteSpace($Evidence)) {
  $arguments += @("--evidence", $Evidence)
}
if ($Snapshot) {
  $arguments += "--snapshot"
}
python @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Issue 62 live review failed with exit code $LASTEXITCODE"
}
