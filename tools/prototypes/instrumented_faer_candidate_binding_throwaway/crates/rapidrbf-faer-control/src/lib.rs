//! Private control plane shared by the exact instrumented faer source closure.
//!
//! The production-facing factor seam does not expose this crate.  It exists so
//! the selected faer, private-gemm, and dyn-stack paths all report to one
//! caller-owned execution lease without each dependency inventing its own
//! resource or cancellation state.

use std::cell::Cell;
use std::panic::{catch_unwind, panic_any, resume_unwind, AssertUnwindSafe};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum EventKind {
    BackendEntry = 1,
    ReserveTransient = 2,
    ReleaseTransient = 3,
    StackCarve = 4,
    Pivot = 5,
    Panel = 6,
    Packing = 7,
    MacroKernel = 8,
    Solve = 9,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(C)]
pub struct Event {
    pub kind: EventKind,
    pub work_units: usize,
    pub bytes: usize,
    pub align: usize,
}

impl Event {
    #[inline]
    pub const fn checkpoint(kind: EventKind, work_units: usize) -> Self {
        Self {
            kind,
            work_units,
            bytes: 0,
            align: 1,
        }
    }

    #[inline]
    pub const fn allocation(kind: EventKind, bytes: usize, align: usize) -> Self {
        Self {
            kind,
            work_units: 0,
            bytes,
            align,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum AbortKind {
    ResourceDenied = 1,
    Cancelled = 2,
    ContractViolation = 3,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decision {
    Continue,
    Abort(AbortKind),
}

pub trait Observer {
    fn observe(&self, event: Event) -> Decision;
}

#[derive(Clone, Copy)]
struct RawObserver {
    data: *const (),
    call: unsafe fn(*const (), Event) -> Decision,
}

thread_local! {
    // This cell owns no allocation, cache, factor, or source lifetime.  It is
    // populated only for the dynamic extent of one caller-owned lease.
    static CURRENT: Cell<Option<RawObserver>> = const { Cell::new(None) };
}

#[derive(Debug)]
struct AbortPanic(AbortKind);

struct ResetGuard;

impl Drop for ResetGuard {
    fn drop(&mut self) {
        CURRENT.with(|current| current.set(None));
    }
}

#[inline]
unsafe fn call_observer<O: Observer>(data: *const (), event: Event) -> Decision {
    // SAFETY: `with_observer` installs this pointer only for the lifetime of
    // the borrowed observer and always clears it before returning.
    unsafe { (&*(data as *const O)).observe(event) }
}

pub fn with_observer<O, F, T>(observer: &O, operation: F) -> Result<T, AbortKind>
where
    O: Observer,
    F: FnOnce() -> T,
{
    let raw = RawObserver {
        data: observer as *const O as *const (),
        call: call_observer::<O>,
    };
    let was_occupied = CURRENT.with(|current| {
        let occupied = current.get().is_some();
        if !occupied {
            current.set(Some(raw));
        }
        occupied
    });
    if was_occupied {
        return Err(AbortKind::ContractViolation);
    }

    let guard = ResetGuard;
    let result = catch_unwind(AssertUnwindSafe(operation));
    drop(guard);

    match result {
        Ok(value) => Ok(value),
        Err(payload) => match payload.downcast::<AbortPanic>() {
            Ok(abort) => Err(abort.0),
            Err(payload) => resume_unwind(payload),
        },
    }
}

#[inline]
pub fn emit(event: Event) {
    let decision = CURRENT.with(|current| {
        current
            .get()
            .map(|observer| {
                // SAFETY: the raw pointer and callback are installed and
                // cleared together by `with_observer`.
                unsafe { (observer.call)(observer.data, event) }
            })
            .unwrap_or(Decision::Continue)
    });
    if let Decision::Abort(kind) = decision {
        panic_any(AbortPanic(kind));
    }
}

#[inline]
pub fn backend_entry() {
    emit(Event::checkpoint(EventKind::BackendEntry, 0));
}

#[inline]
pub fn reserve_transient(bytes: usize, align: usize) {
    emit(Event::allocation(EventKind::ReserveTransient, bytes, align));
}

#[inline]
pub fn release_transient(bytes: usize, align: usize) {
    emit(Event::allocation(EventKind::ReleaseTransient, bytes, align));
}

#[inline]
pub fn stack_carve(bytes: usize, align: usize) {
    emit(Event::allocation(EventKind::StackCarve, bytes, align));
}

#[inline]
pub fn checkpoint(kind: EventKind, work_units: usize) {
    debug_assert!(matches!(
        kind,
        EventKind::Pivot
            | EventKind::Panel
            | EventKind::Packing
            | EventKind::MacroKernel
            | EventKind::Solve
    ));
    emit(Event::checkpoint(kind, work_units));
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    struct CancelAtPacking {
        observations: Cell<usize>,
    }

    impl Observer for CancelAtPacking {
        fn observe(&self, event: Event) -> Decision {
            self.observations.set(self.observations.get() + 1);
            if event.kind == EventKind::Packing {
                Decision::Abort(AbortKind::Cancelled)
            } else {
                Decision::Continue
            }
        }
    }

    #[test]
    fn typed_abort_is_caught_and_context_is_cleared() {
        let observer = CancelAtPacking {
            observations: Cell::new(0),
        };
        let result = with_observer(&observer, || {
            checkpoint(EventKind::Panel, 8);
            checkpoint(EventKind::Packing, 16);
        });
        assert_eq!(result, Err(AbortKind::Cancelled));
        assert_eq!(observer.observations.get(), 2);

        // A second scope proves the first panic path released the TLS slot.
        assert_eq!(with_observer(&observer, || 7), Ok(7));
    }
}
