$ErrorActionPreference = "Stop"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $prototype "repro_issue63.py")
if ($LASTEXITCODE -ne 0) {
  throw "Issue 63 red replay failed with exit code $LASTEXITCODE"
}
