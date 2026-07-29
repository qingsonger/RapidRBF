# Canonical hierarchy admission result

## Immutable corpus

The v3 capture materialized all eight registered M1-M4 solver-panel rows as
twelve positive hierarchy fixtures because both M4 rungs contain the
clustered, near-coincident, and nonuniform valid geometries.

| Inventory item | Observed |
| --- | ---: |
| Positive workloads | 12 |
| Fine blocks | 192 |
| Coarse blocks | 12 |
| All blocks / `Q^T A Q` sources | 204 |
| Coarse `P_top` sources | 12 |
| Carried factor sources | 216 |
| Auxiliary workload-global `P_top` aliases | 12 |
| Materialized rank-invalid controls | 1 |
| Binary artifacts | 2,738 |
| Bound payload bytes | 1,361,547,231 |

The immutable corpus digest is
`38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`.
The checked-in raw manifest has SHA-256
`cf5aaa1e3fe6bf51c3f24f13455ac1036e7ec591668c18ec4c86f3243aa07f54`;
the complete lock file has SHA-256
`7abd17eabba0cd578fa8989075f9d09d5113a696df48c9643785822dadde5a75`.

Two different clean build roots produced byte-identical 773,632-byte capture
executables with SHA-256
`e73a4a3c953ba61cb08f68af800f94da672de7275d9cf3033caee24fe5c8530c`
and byte-identical 1,598,196-byte object files with SHA-256
`f250d5e51e04d9ece0af83659b34434c221d23307992b040e6fb212c6e684e94`.
Both compile and link commands used `/Brepro`, linking used
`/INCREMENTAL:NO`, and the PE carried `IMAGE_DEBUG_TYPE_REPRO`. Each
executable captured into its own new empty directory. All 2,739 relative
files, including every payload and the raw manifest, were byte-identical.
Each corpus was then independently locked and verified against the
executable that produced it; the complete lock bytes and corpus digest were
also identical.

The build coordinate was CMake 4.0.3, Visual Studio 17.14.11
(`17.14.36401.2`), MSBuild 17.14.18.37206, Windows SDK 10.0.26100.0,
ClangCL 19.1.5 targeting `x86_64-pc-windows-msvc`, and LLD 19.1.5. The
successor CMake file is isolated under `capture/hierarchy`; the Stage 0
`capture/CMakeLists.txt` remains byte-for-byte equal to its frozen repository
version. The effective 10k coarse target was 2,047 in both runs, as produced
by the frozen logarithm/power expression whose configured target is 2,048.

The lock independently reconstructed workload and block topology, artifact
shapes and storage, canonical global M3 row payloads, fine-inner ownership
partitions, carried/auxiliary factor aliases, exclusions, and the exact
rank-invalid coordinate mutation. Fifteen malformed-manifest or
self-consistent lock-body controls were all rejected before any candidate
factor backend call. Their corpus- and source-bound report has SHA-256
`caf906e6f5f23d8d9098e2abc6a6ab6ce932f73956040eddfda679c1198e97b4`.

## Semantic admission

The final report used `RapidRBF/RankScalingProfile/v1` with profile hash
`8d60d932464e04c1ce052ecf33acc93f6e72d424ba05d1af7e40cf69b456731e`.
It completed in approximately 170.237 seconds. The 8,989,713-byte report has
SHA-256
`bc907929fdf82976f83212ec514a0ccf43c59499a5dda45f9c4d4ef34aa37e90`.
Its length-prefixed certifier/dependency/profile source closure has SHA-256
`52247e094509d5e5c5a69ed999558a4ce59c395fd2c0b8acc630e5025077b9c2`.

Execution used uv 0.11.16. The report-bound runtime coordinate was CPython
3.13.5, Windows 10.0.26200 on AMD64, NumPy 2.3.2, threadpoolctl 3.6.0, and
scipy-openblas 0.3.30. Both `OPENBLAS_NUM_THREADS` and the effective loaded
controller count were sixteen. The actual loaded
`libscipy_openblas64_-860d95b1c38e637ce4509f5fa24fbf2a.dll` bytes have
SHA-256
`860d95b1c38e637ce4509f5fa24fbf2a98ba8696f9f3d28bf184bee74ad9a325`.
`uv.lock` pins NumPy and threadpoolctl and participates in the source closure.
The report binds that lock plus the listed Python, platform, library, loaded
binary, and thread identities before semantic judgment; the uv executable
version is an external reproduction coordinate rather than a report-bound
identity.

| Certificate family | Admitted | Other |
| --- | ---: | ---: |
| Block physical `P` rank | 204 | 0 |
| Carried `Q^T A Q` rank | 204 | 0 |
| Coarse `P_top` rank | 12 | 0 |
| Canonical-Q/nullspace | 204 | 0 |
| Materialized negative-control behavior | 1 | 0 |

All 420 production rank decisions closed at the binary64 analytic outward
checker, so no canonical subject needed precision escalation. The installed
production ladder is nevertheless executable: the genuine control begins
with a real 53-bit analytic straddle and closes at 256 bits using the
exact-dyadic Gram/Sturm outward checker. Every canonical-Q
certificate proved the exact rational `Q*` construction, structural identity
tail, canonical global row map, and captured-Q normalized residual bound. The
largest exact normalized captured-Q residual was
`3495/3339735176782158859796`, below `2^-32`. The materialized M4 control
proved that its exact duplicate non-anchor value rows form a projected
nullspace-tail direction with observed disposition `RankDeficient`;
certifying that expected behavior is itself reported as `Admitted`. The
aggregate state was `Admitted`, with 625 admitted certificates and zero
candidate factor-backend calls.

The separate admission-control report has SHA-256
`f5e4a3ce87c55ddd1c228ebc559a511289f447a602a1ca44f4fe1ebe8417dc32`.
Its nine controls record exact rank failure as `RankDeficient`, genuine
53-to-256-bit closure as `Admitted`, a completed narrow final straddle as
`IndeterminateRank`, non-finite input as `NonFinite`, metadata preflight
denial as `ResourceDenied`, authority loss during a started ladder as
`EVIDENCE_MISSING`, malformed input as `MalformedCorpus`, and both direct
hash corruption and self-consistent semantic profile drift as
`IntegrityMismatch`. All controls made zero backend calls. Concurrent
fresh-output tests produced exactly one complete winner and preserved every
prior report.

## Independent physical evaluation

The final profile-governed pure-Rust directed-rounding report completed in
approximately 6,858.011 seconds. The 1,511,307-byte report has SHA-256
`da75d43c66e7405676639c61e11c99686d291ea690b85ed0828233d957b6a769`.
It binds `RapidRBF/PhysicalEvidenceProfile/v1`,
`canonical-hierarchy-physical-evidence-v1`, profile SHA-256
`cf64f2b26e2a3f4844a5c63027deb5bd4e1f856f0c7f45d4d2afdcccbff724a1`,
and corpus
`38f39fee8b4059cd2619df4bbfabb6f7159b41df1511907e0346c32642737f79`,
evaluator source closure
`591670bcf1ab95bc2273b5af968f8eea9814e5e7f02208262153feaf03eee805`,
and the 1,332,736-byte release executable with SHA-256
`adee8fdca4f28a033f251e7d33f5fee5d50b160bd7dc033ace5d96dc848d1eb5`.
The executable was built with rustc 1.96.1, cargo 1.96.1, LLVM 22.1.2,
and target `x86_64-pc-windows-msvc`.

All 204 block witnesses were physically certified: 192 fine and twelve
coarse, with no rejection. Across those certificates the evaluator
independently reconstructed and bounded 83,470,740 packed `Q^T A_phys Q`
entries, 179,023 reduced-RHS entries, 179,023 reduced witness equations,
the complete `lambda=[Q_top;I]gamma` coefficients, physical residuals, CPD,
and scatter. Every recorded gate passed. The largest CPD
`eta+alpha` upper bound was
`2.2529510870496663854408753764981815081815166371433016401382703631780145845733e-17`,
below `2^-32`.

Resource preflight required and was granted exactly 685,751,487 payload
bytes and 1,158,236,153 pair-work units. Separate actual-corpus runs with
either grant reduced by one failed with `ResourceDenied` before publishing
payload-derived output. The source- and executable-bound physical-control
report has SHA-256
`b5ba41c993936198d093131a9f5c132c56869575ac2c1f9f5b5ef18eebae6c4f`;
all eighteen non-finite, malformed, M3 row-map, integrity, precision,
coefficient, exact identity-tail (including signed-zero), `Q^T A Q`, and
resource controls passed with zero backend calls.

The evaluator did not open captured `A`, `P`, or `P_top`. Captured
`Q^T A Q` was read only as a hash-bound candidate and compared entry by
entry with the independently reconstructed physical congruence. The report
and all 204 byte-identical sidecar certificates bind the physical profile and
record `backend_calls=0` and `admission_claim=false`.

## Decision boundary

This evidence does not select, publish, pack, or retain a factor backend. It
does not qualify faer health/thread/resource behavior, choose persistent
factor storage, compare mechanisms, or extend the corpus to 100k. Those
questions remain downstream of semantic admission.
