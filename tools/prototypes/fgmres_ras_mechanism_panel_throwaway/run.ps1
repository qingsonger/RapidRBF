param(
  [string] $Corpus = "D:\CODE\interp\RapidRBF-wayfinder\issue44-corpus",
  [string] $Reference = "D:\CODE\interp\RapidRBF-issue32\.prototype-cache\issue47\expanded\official-run-30450649081\rapidrbf-repaired-reference-46716da137e6b4a9eaf062cafa8ac3674a411f44-run-30450649081-attempt-1\reference-manifest.v1.json",
  [string] $Output = "",
  [string] $Workload = "",
  [switch] $Quick,
  [switch] $AuditOnly,
  [string] $PolatorySource = "D:\CODE\polatory",
  [string] $PolatoryBuild = "D:\CODE\polatory\build",
  [string] $OpenMpLibrary = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\lib\x64\libomp.lib"
)

$ErrorActionPreference = "Stop"
$env:OMP_DYNAMIC = "FALSE"
$env:OMP_NUM_THREADS = "8"
$env:MKL_DYNAMIC = "FALSE"
$env:MKL_NUM_THREADS = "1"
$prototype = Split-Path -Parent $MyInvocation.MyCommand.Path
$repository = Resolve-Path (Join-Path $prototype "..\..\..")
$build = Join-Path $prototype "build-vs"
$toolchain = Join-Path $PolatorySource "vcpkg\scripts\buildsystems\vcpkg.cmake"
$installed = Join-Path $PolatoryBuild "vcpkg_installed"
$prototypeInstalled = Join-Path $repository ".prototype-cache\vcpkg-installed"
$multiprecisionHeader = Join-Path $prototypeInstalled "x64-windows\include\boost\multiprecision\cpp_int.hpp"
$propertyTreeHeader = Join-Path $prototypeInstalled "x64-windows\include\boost\property_tree\json_parser.hpp"
if (-not (Test-Path -LiteralPath $multiprecisionHeader) -or
    -not (Test-Path -LiteralPath $propertyTreeHeader)) {
  & (Join-Path $PolatorySource "vcpkg\vcpkg.exe") install `
    boost-multiprecision:x64-windows boost-property-tree:x64-windows `
    "--x-install-root=$prototypeInstalled"
  if ($LASTEXITCODE -ne 0) {
    throw "Prototype-local Boost.Multiprecision installation failed with exit code $LASTEXITCODE"
  }
}
$multiprecisionInclude = Join-Path $prototypeInstalled "x64-windows\include"

cmake -Wno-dev -S $prototype -B $build `
  -G "Visual Studio 17 2022" -A x64 -T ClangCL `
  "-DCMAKE_TOOLCHAIN_FILE=$toolchain" `
  "-DVCPKG_INSTALLED_DIR=$installed" `
  "-DVCPKG_TARGET_TRIPLET=x64-windows" `
  "-DOpenMP_CXX_FLAGS=-Xclang -fopenmp" `
  "-DOpenMP_CXX_LIB_NAMES=libomp" `
  "-DOpenMP_libomp_LIBRARY=$OpenMpLibrary" `
  "-DBOOST_MULTIPRECISION_INCLUDE=$multiprecisionInclude" `
  "-DPOLATORY_SOURCE=$PolatorySource" `
  "-DPOLATORY_BUILD=$PolatoryBuild"
if ($LASTEXITCODE -ne 0) {
  throw "CMake configuration failed with exit code $LASTEXITCODE"
}
cmake --build $build --config Release
if ($LASTEXITCODE -ne 0) {
  throw "CMake build failed with exit code $LASTEXITCODE"
}

$runtime = Join-Path $PolatoryBuild "vcpkg_installed\x64-windows\bin"
$requiredDlls = @(
  "boost_filesystem-vc143-mt-x64-1_90.dll",
  "mkl_core.2.dll",
  "mkl_avx2.2.dll",
  "mkl_def.2.dll",
  "mkl_sequential.2.dll"
)
foreach ($dll in $requiredDlls) {
  Copy-Item -LiteralPath (Join-Path $runtime $dll) `
    -Destination (Join-Path $build "Release") -Force
}

if ([string]::IsNullOrWhiteSpace($Output)) {
  $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $Output = Join-Path $repository ".prototype-cache\results\mechanism-panel-$stamp.json"
}

$arguments = @(
  "--corpus", $Corpus,
  "--reference", $Reference,
  "--output", $Output
)
if (-not [string]::IsNullOrWhiteSpace($Workload)) {
  $arguments += @("--workload", $Workload)
}
if ($Quick) {
  $arguments += "--quick"
}
if ($AuditOnly) {
  $arguments += "--audit-only"
}
& (Join-Path $build "Release\rapidrbf-fgmres-ras-panel.exe") @arguments
if ($LASTEXITCODE -ne 0) {
  throw "Mechanism panel failed with exit code $LASTEXITCODE"
}
