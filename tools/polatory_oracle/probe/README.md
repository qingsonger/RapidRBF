# Frozen Polatory diagnostic probe

This executable captures **instrumented diagnostic evidence** from the clean
Polatory source tree at commit
`4a30beb08053fb339ce899e255be4b6d3f74aa0c`. It is intentionally not an
acceptance test: it emits observations, including exceptions and non-finite
values, and defines no comparison thresholds.

Every stdout line is one deterministic JSON object. Every observed `double` is
encoded as its exact IEEE-754 binary64 bit pattern plus an `fpclassify`
classification. Matrices are emitted as logical rows, independent of Eigen's
physical storage.

From the RapidRBF repository root on the frozen Windows build host:

```powershell
. D:/CODE/polatory/tools/Invoke-BatchFile.ps1
Invoke-BatchFile "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat"
cmake -S tools/polatory_oracle/probe -B tools/polatory_oracle/probe/build -G Ninja `
  -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_CXX_COMPILER="C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/Llvm/x64/bin/clang-cl.exe" `
  -DPOLATORY_SOURCE_DIR=D:/CODE/polatory `
  -DPOLATORY_EIGEN3_DIR=D:/CODE/polatory/build/vcpkg_installed/x64-windows/share/eigen3
cmake --build tools/polatory_oracle/probe/build
tools/polatory_oracle/probe/build/polatory_frozen_source_probe.exe `
  > tools/polatory_oracle/probe/build/probe.jsonl
```

The configuration refuses a different Polatory revision or tracked Polatory
modifications so that the revision label identifies the headers actually
compiled. Untracked build directories are permitted.
