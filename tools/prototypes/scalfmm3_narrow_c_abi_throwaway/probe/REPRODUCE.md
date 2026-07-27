# Reproduce the frozen Windows observation

These steps use the existing local Polatory build. They do not establish a
clean-host or tier-one distribution result.

## Observed source heads and reused binary inputs

- RapidRBF repository: `D:\CODE\interp\RapidRBF`
- Polatory repository: `D:\CODE\polatory`
- Polatory revision: `4a30beb08053fb339ce899e255be4b6d3f74aa0c`
- Nested ScalFMM revision:
  `0be3d74f17adb28adec7004f712f693ac8ee9901`
- Existing static library: `D:\CODE\polatory\build\src\polatory.lib`
- Visual Studio 2022 Community LLVM, CMake, Ninja, LLVM OpenMP, and the existing
  vcpkg oneMKL artifacts

The probe content-hashes `polatory.lib`, the linked import libraries, and the
local OpenMP/MKL runtime files. This identifies exactly what was reused, but
does not prove that the pre-existing `polatory.lib` was produced from the
checkout heads below. Clean rebuild provenance remains unverified.

Verify the revisions:

```powershell
git -C D:\CODE\polatory rev-parse HEAD
git -C D:\CODE\polatory\build\scalfmm\src\scalfmm rev-parse HEAD
```

## Configure and build the throwaway DLL

From the RapidRBF repository root:

```powershell
$prototypeRoot = 'D:\CODE\interp\RapidRBF\tools\prototypes\scalfmm3_narrow_c_abi_throwaway\probe'
$vsDeveloper = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat'
$configure = '"' + $vsDeveloper + '" -arch=x64 -host_arch=x64 >nul && cmake -S "' + $prototypeRoot + '" -B "' + $prototypeRoot + '\build-vs" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\x64\bin\clang-cl.exe" -DCMAKE_CXX_COMPILER="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\x64\bin\clang-cl.exe" -DCMAKE_LINKER="C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\x64\bin\lld-link.exe" -DPOLATORY_ROOT="D:\CODE\polatory"'
& $env:ComSpec /d /s /c $configure

$build = '"' + $vsDeveloper + '" -arch=x64 -host_arch=x64 >nul && cmake --build "' + $prototypeRoot + '\build-vs" --config Release -v'
& $env:ComSpec /d /s /c $build
```

The untracked output is:

```text
tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/build-vs/rapidrbf_scalfmm_probe.dll
```

## Collect source and runtime evidence

```powershell
python tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/source_surface_probe.py `
  --output tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/reproduced-source-surface.json

python tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/abi_probe_driver.py `
  --output tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/reproduced-abi-windows-x86_64.json
```

The runtime driver:

- loads dependent DLLs from the existing Polatory build;
- inspects exports/imports with `dumpbin`;
- runs all small action/dimension/geometry cases;
- exercises 36 Gaussian workflow/action/dimension/geometry cases on the real
  ScalFMM route at 1024-by-1024;
- records direct diagnostics, failure-atomic values-buffer behavior,
  exclusive-lane behavior, and a short repeated-memory sample.

It exits nonzero if any mechanical check fails. Passing does not mean that the
six `Auto` promotion gates pass.

Treat these files as a new observation; the `reproduced-*` names are ignored by
Git and do not overwrite the checked-in baseline. Compare these stable fields:

- both source revisions, selected-source hashes, and matching installed/source
  ScalFMM header-tree hashes;
- reused `polatory.lib`/import/runtime artifact hashes;
- all 23 check booleans;
- 24 small operator, 12 small field, and 36 ScalFMM-route case
  workflow/action/dimension/geometry/status/route tuples;
- the six exported symbol names and imported runtime names.

The rebuilt shim DLL hash is a per-build identity and may change on relink
because this throwaway CMake target does not request reproducible PE output.
Process private/working-set samples, their span, incident identifiers, and host
descriptions may also vary. Do not use an exact whole-file diff as the
acceptance criterion.

## Inspect the decision model

```powershell
python -m py_compile `
  tools/prototypes/scalfmm3_narrow_c_abi_throwaway/model.py `
  tools/prototypes/scalfmm3_narrow_c_abi_throwaway/tui.py `
  tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/source_surface_probe.py `
  tools/prototypes/scalfmm3_narrow_c_abi_throwaway/probe/abi_probe_driver.py

python tools/prototypes/scalfmm3_narrow_c_abi_throwaway/tui.py --snapshot
```

The snapshot is deterministic. The interactive form uses the same pure state
model.
