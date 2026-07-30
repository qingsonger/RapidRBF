param(
  [switch] $Snapshot
)

$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$arguments = @((Join-Path $prototype "review_issue63.py"))
if ($Snapshot) {
  $arguments += "--snapshot"
}
python @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Issue 63 live review failed with exit code $LASTEXITCODE"
}
