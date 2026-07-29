"""THROWAWAY external process observer for the Issue 51 witness gate.

The question is whether the unchanged refinement candidate can be judged with
one sole waiter, a sampler that never polls or reaps, complete process-tree
thread inventories, and the narrowly frozen macOS terminal-race rule.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence


SAMPLE_PERIOD_SECONDS = 0.002
RECONCILIATION_SECONDS = 1.0


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_identity(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


class AdapterFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        adapter: str,
        error_number: int | None = None,
        root_taskinfo: bool = False,
    ) -> None:
        super().__init__(message)
        self.adapter = adapter
        self.error_number = error_number
        self.root_taskinfo = root_taskinfo

    def evidence(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "errno": self.error_number,
            "error_name": (
                errno.errorcode.get(self.error_number)
                if self.error_number is not None
                else None
            ),
            "message": str(self),
            "root_taskinfo": self.root_taskinfo,
        }


class Recorder:
    def __init__(self, invocation_nonce: str) -> None:
        self.invocation_nonce = invocation_nonce
        self.started_ns = time.monotonic_ns()
        self.lock = threading.Lock()
        self.events: list[dict[str, Any]] = []

    def now_ns(self) -> int:
        return time.monotonic_ns() - self.started_ns

    def append(self, kind: str, **values: Any) -> dict[str, Any]:
        with self.lock:
            event = {
                "sequence": len(self.events),
                "kind": kind,
                "monotonic_ns": self.now_ns(),
                "invocation_nonce": self.invocation_nonce,
                **values,
            }
            self.events.append(event)
            return event


def _linux_stat(pid: int) -> tuple[int, int]:
    path = Path(f"/proc/{pid}/stat")
    try:
        text = path.read_text(encoding="ascii")
    except OSError as error:
        raise AdapterFailure(
            f"cannot read {path}: {error}",
            adapter="linux-proc-process-tree",
            error_number=error.errno,
        ) from error
    close = text.rfind(")")
    if close < 0:
        raise AdapterFailure(
            f"malformed {path}",
            adapter="linux-proc-process-tree",
        )
    fields = text[close + 2 :].split()
    if len(fields) <= 19:
        raise AdapterFailure(
            f"short {path}",
            adapter="linux-proc-process-tree",
        )
    return int(fields[2]), int(fields[19])


def _linux_group_pids(group_id: int) -> list[int]:
    result: list[int] = []
    for child in Path("/proc").iterdir():
        if not child.name.isdigit():
            continue
        pid = int(child.name)
        try:
            process_group, _ = _linux_stat(pid)
        except AdapterFailure as error:
            if error.error_number in {errno.ENOENT, errno.ESRCH}:
                continue
            raise
        if process_group == group_id:
            result.append(pid)
    return sorted(result)


def _linux_inventory(group_id: int, root_pid: int) -> list[dict[str, Any]]:
    before = _linux_group_pids(group_id)
    if root_pid not in before:
        raise AdapterFailure(
            "root is absent from the Linux process group",
            adapter="linux-proc-process-tree",
            error_number=errno.ESRCH,
        )
    inventory: list[dict[str, Any]] = []
    for pid in before:
        process_group, starttime = _linux_stat(pid)
        if process_group != group_id:
            raise AdapterFailure(
                "Linux process-group membership changed during sampling",
                adapter="linux-proc-process-tree",
            )
        task_dir = Path(f"/proc/{pid}/task")
        try:
            threads = len([item for item in task_dir.iterdir() if item.name.isdigit()])
        except OSError as error:
            raise AdapterFailure(
                f"cannot enumerate {task_dir}: {error}",
                adapter="linux-proc-process-tree",
                error_number=error.errno,
            ) from error
        if threads < 1:
            raise AdapterFailure(
                "Linux task inventory is empty",
                adapter="linux-proc-process-tree",
            )
        inventory.append(
            {
                "pid": pid,
                "process_identity": f"linux:{pid}:{starttime}",
                "is_root": pid == root_pid,
                "threads": threads,
            }
        )
    return inventory


class MacProcBsdInfo(ctypes.Structure):
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32),
        ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32),
        ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32),
        ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32),
        ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32),
        ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32),
        ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16),
        ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32),
        ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64),
        ("pbi_start_tvusec", ctypes.c_uint64),
    ]


class MacProcTaskInfo(ctypes.Structure):
    _fields_ = [
        ("pti_virtual_size", ctypes.c_uint64),
        ("pti_resident_size", ctypes.c_uint64),
        ("pti_total_user", ctypes.c_uint64),
        ("pti_total_system", ctypes.c_uint64),
        ("pti_threads_user", ctypes.c_uint64),
        ("pti_threads_system", ctypes.c_uint64),
        ("pti_policy", ctypes.c_int32),
        ("pti_faults", ctypes.c_int32),
        ("pti_pageins", ctypes.c_int32),
        ("pti_cow_faults", ctypes.c_int32),
        ("pti_messages_sent", ctypes.c_int32),
        ("pti_messages_received", ctypes.c_int32),
        ("pti_syscalls_mach", ctypes.c_int32),
        ("pti_syscalls_unix", ctypes.c_int32),
        ("pti_csw", ctypes.c_int32),
        ("pti_threadnum", ctypes.c_int32),
        ("pti_numrunning", ctypes.c_int32),
        ("pti_priority", ctypes.c_int32),
    ]


def _mac_libproc() -> Any:
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    library.proc_listpids.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    library.proc_listpids.restype = ctypes.c_int
    library.proc_pidinfo.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    library.proc_pidinfo.restype = ctypes.c_int
    return library


def _mac_group_pids(library: Any, group_id: int) -> list[int]:
    required = library.proc_listpids(2, group_id, None, 0)
    if required < 0:
        number = ctypes.get_errno()
        raise AdapterFailure(
            "proc_listpids size query failed",
            adapter="macos-proc-process-tree",
            error_number=number,
        )
    capacity = max(1, required // ctypes.sizeof(ctypes.c_int) + 32)
    values = (ctypes.c_int * capacity)()
    observed = library.proc_listpids(
        2, group_id, ctypes.byref(values), ctypes.sizeof(values)
    )
    if observed < 0 or observed > ctypes.sizeof(values):
        number = ctypes.get_errno()
        raise AdapterFailure(
            "proc_listpids inventory failed or overflowed",
            adapter="macos-proc-process-tree",
            error_number=number,
        )
    count = observed // ctypes.sizeof(ctypes.c_int)
    return sorted({int(values[index]) for index in range(count) if values[index] > 0})


def _mac_pidinfo(
    library: Any,
    pid: int,
    flavor: int,
    value: ctypes.Structure,
    *,
    root_taskinfo: bool = False,
) -> None:
    ctypes.set_errno(0)
    observed = library.proc_pidinfo(
        pid, flavor, 0, ctypes.byref(value), ctypes.sizeof(value)
    )
    if observed != ctypes.sizeof(value):
        number = ctypes.get_errno() or errno.EIO
        raise AdapterFailure(
            f"proc_pidinfo flavor {flavor} returned {observed}/{ctypes.sizeof(value)}",
            adapter=(
                "macos-proc_pidinfo"
                if root_taskinfo
                else "macos-proc-process-tree"
            ),
            error_number=number,
            root_taskinfo=root_taskinfo,
        )


def _mac_inventory(group_id: int, root_pid: int) -> list[dict[str, Any]]:
    library = _mac_libproc()
    before = _mac_group_pids(library, group_id)
    if root_pid not in before:
        raise AdapterFailure(
            "root is absent from the macOS process group",
            adapter="macos-proc-process-tree",
            error_number=errno.ESRCH,
        )
    inventory: list[dict[str, Any]] = []
    for pid in before:
        bsd = MacProcBsdInfo()
        _mac_pidinfo(library, pid, 3, bsd)
        if int(bsd.pbi_pgid) != group_id:
            raise AdapterFailure(
                "macOS process-group membership changed during sampling",
                adapter="macos-proc-process-tree",
            )
        task = MacProcTaskInfo()
        _mac_pidinfo(
            library,
            pid,
            4,
            task,
            root_taskinfo=pid == root_pid,
        )
        threads = int(task.pti_threadnum)
        if threads < 1:
            raise AdapterFailure(
                "macOS task inventory reported no threads",
                adapter="macos-proc-process-tree",
            )
        inventory.append(
            {
                "pid": pid,
                "process_identity": (
                    f"macos:{pid}:{int(bsd.pbi_start_tvsec)}:"
                    f"{int(bsd.pbi_start_tvusec)}"
                ),
                "is_root": pid == root_pid,
                "threads": threads,
            }
        )
    return inventory


if sys.platform == "win32":
    from ctypes import wintypes

    class WinFileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    class WinThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    class WinIoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class WinBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class WinExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", WinBasicLimitInformation),
            ("IoInfo", WinIoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]


class SubjectGroup:
    def __init__(self, process: subprocess.Popen[Any], job_handle: int | None) -> None:
        self.process = process
        self.root_pid = process.pid
        self.group_id = process.pid
        self.job_handle = job_handle

    @classmethod
    def launch(
        cls,
        command: Sequence[str],
        *,
        cwd: Path,
        env: dict[str, str],
        stdout: Any,
        stderr: Any,
    ) -> "SubjectGroup":
        if sys.platform == "win32":
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=stdout,
                stderr=stderr,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            kernel32.AssignProcessToJobObject.argtypes = [
                wintypes.HANDLE,
                wintypes.HANDLE,
            ]
            kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel32.SetInformationJobObject.argtypes = [
                wintypes.HANDLE,
                ctypes.c_int,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            kernel32.SetInformationJobObject.restype = wintypes.BOOL
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                process.kill()
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
            limits = WinExtendedLimitInformation()
            limits.BasicLimitInformation.LimitFlags = 0x00002000
            if not kernel32.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            ):
                process.kill()
                kernel32.CloseHandle(job)
                raise OSError(
                    ctypes.get_last_error(), "SetInformationJobObject"
                )
            if not kernel32.AssignProcessToJobObject(job, process._handle):
                process.kill()
                kernel32.CloseHandle(job)
                raise OSError(
                    ctypes.get_last_error(), "AssignProcessToJobObject"
                )
            return cls(process, int(job))
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        return cls(process, None)

    def _windows_pids(self) -> list[int]:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryInformationJobObject.restype = wintypes.BOOL
        buffer = ctypes.create_string_buffer(65536)
        returned = wintypes.DWORD()
        if not kernel32.QueryInformationJobObject(
            self.job_handle,
            3,
            buffer,
            ctypes.sizeof(buffer),
            ctypes.byref(returned),
        ):
            raise AdapterFailure(
                "QueryInformationJobObject failed",
                adapter="windows-job-toolhelp-process-tree",
                error_number=ctypes.get_last_error(),
            )
        header = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD * 2)).contents
        count = int(header[1])
        offset = 8
        values = (ctypes.c_size_t * count).from_buffer(buffer, offset)
        return sorted(int(values[index]) for index in range(count))

    def _windows_process_identity(self, pid: int) -> str:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(WinFileTime),
            ctypes.POINTER(WinFileTime),
            ctypes.POINTER(WinFileTime),
            ctypes.POINTER(WinFileTime),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            raise AdapterFailure(
                f"OpenProcess failed for {pid}",
                adapter="windows-job-toolhelp-process-tree",
                error_number=ctypes.get_last_error(),
            )
        creation = WinFileTime()
        exit_time = WinFileTime()
        kernel = WinFileTime()
        user = WinFileTime()
        try:
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_time),
                ctypes.byref(kernel),
                ctypes.byref(user),
            ):
                raise AdapterFailure(
                    f"GetProcessTimes failed for {pid}",
                    adapter="windows-job-toolhelp-process-tree",
                    error_number=ctypes.get_last_error(),
                )
        finally:
            kernel32.CloseHandle(handle)
        created = (int(creation.dwHighDateTime) << 32) | int(
            creation.dwLowDateTime
        )
        return f"windows:{pid}:{created}"

    def _windows_thread_counts(self, pids: list[int]) -> dict[int, int]:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Thread32First.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(WinThreadEntry32),
        ]
        kernel32.Thread32First.restype = wintypes.BOOL
        kernel32.Thread32Next.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(WinThreadEntry32),
        ]
        kernel32.Thread32Next.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            raise AdapterFailure(
                "CreateToolhelp32Snapshot failed",
                adapter="windows-job-toolhelp-process-tree",
                error_number=ctypes.get_last_error(),
            )
        counts = {pid: 0 for pid in pids}
        entry = WinThreadEntry32()
        entry.dwSize = ctypes.sizeof(entry)
        try:
            success = kernel32.Thread32First(snapshot, ctypes.byref(entry))
            while success:
                owner = int(entry.th32OwnerProcessID)
                if owner in counts:
                    counts[owner] += 1
                success = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)
        return counts

    def inventory(self) -> list[dict[str, Any]]:
        if sys.platform == "win32":
            before = self._windows_pids()
            if self.root_pid not in before:
                raise AdapterFailure(
                    "root is absent from the Windows Job Object",
                    adapter="windows-job-toolhelp-process-tree",
                    error_number=errno.ESRCH,
                )
            identities = {
                pid: self._windows_process_identity(pid) for pid in before
            }
            counts = self._windows_thread_counts(before)
            if any(counts[pid] < 1 for pid in before):
                raise AdapterFailure(
                    "Windows process inventory contains an empty thread set",
                    adapter="windows-job-toolhelp-process-tree",
                )
            return [
                {
                    "pid": pid,
                    "process_identity": identities[pid],
                    "is_root": pid == self.root_pid,
                    "threads": counts[pid],
                }
                for pid in before
            ]
        if sys.platform == "darwin":
            return _mac_inventory(self.group_id, self.root_pid)
        return _linux_inventory(self.group_id, self.root_pid)

    def terminate(self) -> None:
        if sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateJobObject.argtypes = [
                wintypes.HANDLE,
                wintypes.UINT,
            ]
            kernel32.TerminateJobObject.restype = wintypes.BOOL
            if not kernel32.TerminateJobObject(self.job_handle, 1):
                raise OSError(ctypes.get_last_error(), "TerminateJobObject")
            return
        try:
            os.killpg(self.group_id, signal.SIGKILL)
        except ProcessLookupError:
            return

    def is_empty(self) -> bool:
        try:
            if sys.platform == "win32":
                return not self._windows_pids()
            if sys.platform == "darwin":
                return not _mac_group_pids(_mac_libproc(), self.group_id)
            return not _linux_group_pids(self.group_id)
        except (AdapterFailure, OSError):
            return False

    def close(self) -> None:
        if sys.platform == "win32" and self.job_handle:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle(self.job_handle)
            self.job_handle = None


def observe_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float,
    maximum_live_threads: int,
    candidate_entry: Path | None,
    candidate_output: Path | None,
    require_candidate_entry: bool,
    require_successful_sample: bool,
    invocation_kind: str,
    fault_mode: str | None = None,
    after_first_sample: Callable[[], None] | None = None,
    stop_sampling_after_first_callback: bool = False,
    sample_readiness: Callable[[], bool] | None = None,
) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
    """Run one subject with a sole waiter and a non-reaping sampler."""

    invocation_nonce = uuid.uuid4().hex
    recorder = Recorder(invocation_nonce)
    terminal_event = threading.Event()
    stop_deadline = threading.Event()
    abort_event = threading.Event()
    timed_out = threading.Event()
    waiter_done = threading.Event()
    state_lock = threading.Lock()
    terminal_record: dict[str, Any] | None = None
    invalidity: list[dict[str, Any]] = []
    benign_terminal_races = 0
    successful_samples = 0
    maximum_observed = 0
    timeout_kill_history: list[dict[str, Any]] = []

    stdout_fd, stdout_name = tempfile.mkstemp(prefix="rapidrbf-observer-stdout-")
    stderr_fd, stderr_name = tempfile.mkstemp(prefix="rapidrbf-observer-stderr-")
    os.close(stdout_fd)
    os.close(stderr_fd)
    stdout_path = Path(stdout_name)
    stderr_path = Path(stderr_name)
    group: SubjectGroup | None = None
    stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")
    try:
        group = SubjectGroup.launch(
            command,
            cwd=cwd,
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
        )
        recorder.append(
            "launch",
            invocation_kind=invocation_kind,
            diagnostic_pid=group.root_pid,
            handle_owner="controller",
            process_scope=(
                "windows-job-object"
                if sys.platform == "win32"
                else "posix-process-group"
            ),
        )

        def waiter() -> None:
            nonlocal terminal_record
            returncode = group.process.wait()
            terminal = recorder.append(
                "terminal_observed",
                owner="sole-waiter",
                returncode=returncode,
                signal=(-returncode if returncode < 0 else None),
            )
            with state_lock:
                terminal_record = terminal
            terminal_event.set()
            stop_deadline.set()
            recorder.append(
                "reaped",
                owner="sole-waiter",
                returncode=returncode,
                signal=(-returncode if returncode < 0 else None),
            )
            waiter_done.set()

        def deadline_owner() -> None:
            if not stop_deadline.wait(timeout_seconds):
                timed_out.set()
                event = recorder.append(
                    "timeout",
                    owner="monotonic-deadline",
                    timeout_seconds=timeout_seconds,
                )
                timeout_kill_history.append(event)
                try:
                    group.terminate()
                    timeout_kill_history.append(
                        recorder.append(
                            "kill",
                            owner="monotonic-deadline",
                            reason="timeout",
                        )
                    )
                except OSError as error:
                    with state_lock:
                        invalidity.append(
                            {
                                "gate": "timeout-kill",
                                "error": str(error),
                            }
                        )
                return
            if abort_event.is_set() and not terminal_event.is_set():
                try:
                    group.terminate()
                    timeout_kill_history.append(
                        recorder.append(
                            "kill",
                            owner="monotonic-deadline",
                            reason="controller-invalidity",
                        )
                    )
                except OSError as error:
                    with state_lock:
                        invalidity.append(
                            {
                                "gate": "controller-abort-kill",
                                "error": str(error),
                            }
                        )

        def sampler() -> None:
            nonlocal benign_terminal_races
            nonlocal successful_samples
            nonlocal maximum_observed
            sample_id = 0
            injected = False
            callback_invoked = False
            while not terminal_event.is_set():
                sample_started = recorder.append(
                    "sample_begin",
                    sample_id=sample_id,
                )
                if sample_readiness is not None and not sample_readiness():
                    recorder.append(
                        "sample_deferred",
                        sample_id=sample_id,
                        sample_started_ns=sample_started["monotonic_ns"],
                        reason="preflight-readiness-marker-absent",
                    )
                    sample_id += 1
                    terminal_event.wait(SAMPLE_PERIOD_SECONDS)
                    continue
                try:
                    if fault_mode and not injected:
                        injected = True
                        if fault_mode == "unpaired-esrch":
                            raise AdapterFailure(
                                "[Errno 3] injected proc_pidinfo",
                                adapter="macos-proc_pidinfo",
                                error_number=errno.ESRCH,
                                root_taskinfo=True,
                            )
                        if fault_mode == "non-esrch":
                            raise AdapterFailure(
                                "[Errno 1] injected adapter error",
                                adapter="macos-proc_pidinfo",
                                error_number=errno.EPERM,
                                root_taskinfo=True,
                            )
                    inventory = group.inventory()
                    total = sum(item["threads"] for item in inventory)
                    if total < 1 or not any(item["is_root"] for item in inventory):
                        raise AdapterFailure(
                            "process-tree inventory is incomplete",
                            adapter="controller-process-tree",
                        )
                    event = recorder.append(
                        "sample_ok",
                        sample_id=sample_id,
                        sample_started_ns=sample_started["monotonic_ns"],
                        process_inventory=inventory,
                        summed_live_threads=total,
                    )
                    with state_lock:
                        successful_samples += 1
                        maximum_observed = max(maximum_observed, total)
                    if after_first_sample is not None and not callback_invoked:
                        try:
                            after_first_sample()
                            callback_invoked = True
                            recorder.append(
                                "after_first_sample",
                                owner="sampler",
                            )
                            if stop_sampling_after_first_callback:
                                return
                        except OSError as error:
                            with state_lock:
                                invalidity.append(
                                    {
                                        "gate": "after-first-sample",
                                        "error": str(error),
                                    }
                                )
                            abort_event.set()
                            stop_deadline.set()
                            return
                    if event["monotonic_ns"] < sample_started["monotonic_ns"]:
                        with state_lock:
                            invalidity.append(
                                {
                                    "gate": "sample-order",
                                    "error": "sample timestamp moved backward",
                                }
                            )
                        abort_event.set()
                        stop_deadline.set()
                        return
                except AdapterFailure as error:
                    finished = recorder.now_ns()
                    raw = error.evidence()
                    recorder.append(
                        "sample_error",
                        sample_id=sample_id,
                        sample_started_ns=sample_started["monotonic_ns"],
                        sample_finished_ns=finished,
                        raw_adapter_result=raw,
                    )
                    eligible = (
                        raw["adapter"] == "macos-proc_pidinfo"
                        and raw["errno"] == errno.ESRCH
                        and raw["error_name"] == "ESRCH"
                        and raw["root_taskinfo"]
                        and (
                            sys.platform == "darwin"
                            or fault_mode == "unpaired-esrch"
                        )
                    )
                    if not eligible:
                        with state_lock:
                            invalidity.append(
                                {
                                    "gate": "sampling",
                                    "error": raw,
                                }
                            )
                        abort_event.set()
                        stop_deadline.set()
                        return
                    with state_lock:
                        already = benign_terminal_races
                        terminal = terminal_record
                    if already:
                        with state_lock:
                            invalidity.append(
                                {
                                    "gate": "sampling",
                                    "error": "more than one eligible ESRCH race",
                                }
                            )
                        abort_event.set()
                        stop_deadline.set()
                        return
                    if terminal is None:
                        if not terminal_event.wait(RECONCILIATION_SECONDS):
                            with state_lock:
                                invalidity.append(
                                    {
                                        "gate": "sampling",
                                        "error": (
                                            "ESRCH did not close against the same "
                                            "handle within 1000 ms"
                                        ),
                                    }
                                )
                            abort_event.set()
                            stop_deadline.set()
                            return
                        with state_lock:
                            terminal = terminal_record
                    if (
                        terminal is None
                        or terminal["invocation_nonce"] != invocation_nonce
                        or terminal["monotonic_ns"]
                        < sample_started["monotonic_ns"]
                        or terminal["monotonic_ns"]
                        > finished + int(RECONCILIATION_SECONDS * 1_000_000_000)
                    ):
                        with state_lock:
                            invalidity.append(
                                {
                                    "gate": "sampling",
                                    "error": (
                                        "ESRCH closure has the wrong handle or "
                                        "event order"
                                    ),
                                }
                            )
                        abort_event.set()
                        stop_deadline.set()
                        return
                    with state_lock:
                        benign_terminal_races += 1
                    recorder.append(
                        "benign_terminal_race",
                        sample_id=sample_id,
                        classification="BENIGN_TERMINAL_RACE",
                        terminal_sequence=terminal["sequence"],
                        effect="no-sample-no-error-maximum-unchanged",
                    )
                    return
                sample_id += 1
                terminal_event.wait(SAMPLE_PERIOD_SECONDS)

        waiter_thread = threading.Thread(
            target=waiter,
            name=f"sole-waiter-{invocation_nonce}",
        )
        deadline_thread = threading.Thread(
            target=deadline_owner,
            name=f"deadline-{invocation_nonce}",
        )
        sampler_thread = threading.Thread(
            target=sampler,
            name=f"sampler-{invocation_nonce}",
        )
        waiter_thread.start()
        deadline_thread.start()
        sampler_thread.start()
        waiter_done.wait(timeout_seconds + 30.0)
        if not waiter_done.is_set():
            with state_lock:
                invalidity.append(
                    {
                        "gate": "sole-waiter",
                        "error": "waiter did not report after deadline closure",
                    }
                )
            abort_event.set()
            stop_deadline.set()
        waiter_thread.join(timeout=5.0)
        sampler_thread.join(timeout=RECONCILIATION_SECONDS + 5.0)
        deadline_thread.join(timeout=5.0)
        if waiter_thread.is_alive() or sampler_thread.is_alive() or deadline_thread.is_alive():
            with state_lock:
                invalidity.append(
                    {
                        "gate": "controller-thread-cleanup",
                        "error": "controller helper thread survived coordinate closure",
                    }
                )

        stdout_handle.close()
        stderr_handle.close()
        stdout_data = stdout_path.read_bytes()
        stderr_data = stderr_path.read_bytes()
        returncode = group.process.returncode
        process_group_empty = group.is_empty()
        if not process_group_empty:
            with state_lock:
                invalidity.append(
                    {
                        "gate": "subject-process-tree-cleanup",
                        "error": "subject process tree is non-empty after root reap",
                    }
                )
            try:
                group.terminate()
            except OSError:
                pass

        entry_identity = file_identity(candidate_entry)
        output_identity = file_identity(candidate_output)
        with state_lock:
            invalid_snapshot = list(invalidity)
            samples = successful_samples
            maximum = maximum_observed
            terminal_snapshot = terminal_record
            benign_count = benign_terminal_races
        if terminal_snapshot is None:
            invalid_snapshot.append(
                {"gate": "process-result", "error": "terminal result is absent"}
            )
        if require_candidate_entry and entry_identity is None:
            invalid_snapshot.append(
                {
                    "gate": "candidate-entry",
                    "error": "frozen candidate-entry marker is absent",
                }
            )
        if require_successful_sample and samples < 1:
            invalid_snapshot.append(
                {
                    "gate": "thread-evidence",
                    "error": "no successful complete process-tree sample",
                }
            )
        if invalid_snapshot:
            classification = "INVALID_CONTROLLER_EVIDENCE"
        elif (
            (returncode is not None and returncode != 0)
            or timed_out.is_set()
            or maximum > maximum_live_threads
        ):
            classification = "VALID_CANDIDATE_OWNED_NONPASS"
        else:
            classification = "PASS"

        record = {
            "schema": "RapidRBF/ControllerValidProcessObservation/v1",
            "classification": classification,
            "method": (
                "sole waiter plus non-reaping 2ms native complete "
                "process-tree sampler"
            ),
            "invocation_kind": invocation_kind,
            "invocation_nonce": invocation_nonce,
            "diagnostic_pid": group.root_pid,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out.is_set(),
            "maximum_live_threads_grant": maximum_live_threads,
            "successful_samples": samples,
            "maximum_live_threads": maximum,
            "benign_terminal_races": benign_count,
            "invalidity": invalid_snapshot,
            "event_log": recorder.events,
            "process_result": {
                "returncode": returncode,
                "signal": (
                    -returncode
                    if returncode is not None and returncode < 0
                    else None
                ),
                "terminal_sequence": (
                    terminal_snapshot["sequence"]
                    if terminal_snapshot is not None
                    else None
                ),
                "stdout": {
                    "bytes": len(stdout_data),
                    "sha256": sha256_bytes(stdout_data),
                },
                "stderr": {
                    "bytes": len(stderr_data),
                    "sha256": sha256_bytes(stderr_data),
                },
                "candidate_entry": entry_identity,
                "candidate_output": output_identity,
                "timeout_kill_history": timeout_kill_history,
                "process_tree_empty_after_reap": process_group_empty,
            },
        }
        completed = subprocess.CompletedProcess(
            list(command),
            returncode if returncode is not None else -1,
            stdout_data,
            stderr_data,
        )
        return completed, record
    finally:
        if not stdout_handle.closed:
            stdout_handle.close()
        if not stderr_handle.closed:
            stderr_handle.close()
        if group is not None:
            group.close()
        stdout_path.unlink(missing_ok=True)
        stderr_path.unlink(missing_ok=True)
