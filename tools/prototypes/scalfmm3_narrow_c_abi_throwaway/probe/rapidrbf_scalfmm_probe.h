#ifndef RAPIDRBF_SCALFMM_PROBE_H
#define RAPIDRBF_SCALFMM_PROBE_H

#include <stdint.h>

#if defined(_WIN32)
#if defined(RRSF_BUILDING_DLL)
#define RRSF_EXPORT __declspec(dllexport)
#else
#define RRSF_EXPORT __declspec(dllimport)
#endif
#define RRSF_CALL __cdecl
#else
#define RRSF_EXPORT __attribute__((visibility("default")))
#define RRSF_CALL
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define RRSF_ABI_V1 1u
#define RRSF_NO_INDEX UINT64_MAX
#define RRSF_UNBOUNDED_QUANTUM UINT64_MAX
#define RRSF_UNKNOWN_U32 UINT32_MAX

typedef struct rrsf_plan rrsf_plan;
typedef struct rrsf_lane rrsf_lane;

typedef enum rrsf_status_v1 {
  RRSF_OK_CERTIFIED = 0,
  RRSF_OK_UNCERTIFIED_EVIDENCE = 1,
  RRSF_ABI_MISMATCH = 100,
  RRSF_INVALID_REQUEST = 101,
  RRSF_UNSUPPORTED = 102,
  RRSF_UNDEFINED_DERIVATIVE = 103,
  RRSF_RESOURCE_EXHAUSTED = 104,
  RRSF_CANCELLED = 105,
  RRSF_DEADLINE_EXCEEDED = 106,
  RRSF_CERTIFICATE_UNAVAILABLE = 107,
  RRSF_ACCURACY_UNATTAINABLE = 108,
  RRSF_BUSY = 109,
  RRSF_INTERNAL_FAILURE = 110
} rrsf_status_v1;

typedef enum rrsf_plan_kind_v1 {
  RRSF_WEIGHTS_VARY = 1,
  RRSF_TARGETS_VARY = 2
} rrsf_plan_kind_v1;

typedef enum rrsf_action_v1 {
  RRSF_ACTION_A = 1,
  RRSF_ACTION_F = 2,
  RRSF_ACTION_FT = 3,
  RRSF_ACTION_H = 4
} rrsf_action_v1;

typedef enum rrsf_geometry_v1 {
  RRSF_GEOMETRY_SELF = 1,
  RRSF_GEOMETRY_CROSS = 2
} rrsf_geometry_v1;

typedef enum rrsf_kernel_v1 {
  RRSF_KERNEL_GAUSSIAN_PROBE_ONLY = 1
} rrsf_kernel_v1;

typedef enum rrsf_route_v1 {
  RRSF_ROUTE_LEGACY_DIRECT = 1,
  RRSF_ROUTE_SCALFMM = 2
} rrsf_route_v1;

typedef enum rrsf_certificate_kind_v1 {
  RRSF_CERTIFICATE_NONE = 0,
  RRSF_CERTIFICATE_FULL_DIRECT_DIAGNOSTIC = 1,
  RRSF_CERTIFICATE_SOUND_ABS_LINF = 2
} rrsf_certificate_kind_v1;

enum {
  RRSF_RUN_ALLOW_UNCERTIFIED_EVIDENCE = 1u << 0,
  RRSF_RUN_FULL_DIRECT_DIAGNOSTIC = 1u << 1,
  /* Throwaway-only catch-fence/poisoning probe; never a production flag. */
  RRSF_RUN_FORCE_EXCEPTION_FOR_PROBE = 1u << 31
};

enum {
  RRSF_REPORT_INPUTS_COPIED = 1u << 0,
  RRSF_REPORT_OUTPUT_STAGED = 1u << 1,
  RRSF_REPORT_RESOURCE_ACCOUNTING_PARTIAL = 1u << 2,
  RRSF_REPORT_THREAD_ACCOUNTING_PARTIAL = 1u << 3,
  RRSF_REPORT_CANCELLATION_QUANTUM_UNBOUNDED = 1u << 4,
  RRSF_REPORT_WEIGHT_SENSITIVE_CONFIG_UNCERTIFIED = 1u << 5
};

typedef struct rrsf_error_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  uint32_t stage;
  uint32_t detail;
  uint64_t offending_index;
  uint64_t incident_id;
  char message[192];
} rrsf_error_v1;

typedef struct rrsf_resource_grant_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  uint64_t persistent_bytes;
  uint64_t transient_bytes;
  uint32_t max_threads;
  uint32_t reserved;
} rrsf_resource_grant_v1;

typedef struct rrsf_plan_desc_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  uint32_t plan_kind;
  uint32_t action;
  uint32_t geometry;
  uint32_t dimension;
  uint32_t kernel;
  uint32_t reserved;
  const double *kernel_parameters;
  uint64_t kernel_parameter_count;
  const double *fixed_sources;
  uint64_t source_count;
  uint64_t fixed_source_value_count;
  const double *fixed_targets;
  uint64_t target_count;
  uint64_t fixed_target_value_count;
  const double *fixed_weights;
  uint64_t fixed_weight_value_count;
  double bbox_min[3];
  double bbox_max[3];
} rrsf_plan_desc_v1;

typedef struct rrsf_lane_desc_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  rrsf_resource_grant_v1 grant;
} rrsf_lane_desc_v1;

typedef struct rrsf_run_desc_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  uint32_t flags;
  uint32_t reserved;
  const double *changing_weights;
  uint64_t changing_weight_value_count;
  const double *changing_targets;
  uint64_t changing_target_count;
  uint64_t changing_target_value_count;
  double requested_abs_inf_budget;
} rrsf_run_desc_v1;

typedef struct rrsf_output_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  double *values;
  uint64_t value_capacity;
  uint64_t value_count;
} rrsf_output_v1;

typedef struct rrsf_report_v1 {
  uint32_t struct_size;
  uint32_t abi_version;
  uint32_t route;
  uint32_t certificate_kind;
  uint32_t configured_threads;
  /* RRSF_UNKNOWN_U32 when the partial probe cannot measure these values. */
  uint32_t effective_threads;
  uint32_t maximum_live_threads;
  uint32_t flags;
  uint64_t output_value_count;
  uint64_t persistent_bytes_estimate;
  uint64_t transient_bytes_estimate;
  uint64_t maximum_unpolled_work;
  double diagnostic_abs_inf_error;
  char backend_revision[41];
} rrsf_report_v1;

/*
 * Prototype lifetime and synchronization contract:
 *
 * - plan_create copies every fixed input. lane_open copies the plan state it
 *   needs, so a successfully opened lane does not borrow the plan.
 * - Dynamic run inputs and output storage are call-scoped and never retained.
 *   run resets output.value_count to zero on entry; the values buffer is only
 *   copied after successful evidence-only evaluation.
 * - One lane_run may execute per lane. An overlapping run returns RRSF_BUSY.
 *   lane_request_cancel may race lane_run. A request linearized before the
 *   successful publication commit applies to that run; a request at or after
 *   the commit is queued for the next run.
 * - plan_destroy must not race plan_create/lane_open on the same plan.
 *   lane_destroy must not race lane_run or lane_request_cancel.
 * - Callers initialize every versioned input/output/error structure's
 *   struct_size and abi_version fields before the call.
 */

RRSF_EXPORT uint32_t RRSF_CALL rrsf_plan_create_v1(
    const rrsf_plan_desc_v1 *desc, const rrsf_resource_grant_v1 *grant,
    rrsf_plan **out_plan, rrsf_error_v1 *error);

RRSF_EXPORT uint32_t RRSF_CALL rrsf_lane_open_v1(const rrsf_plan *plan,
                                                 const rrsf_lane_desc_v1 *desc,
                                                 rrsf_lane **out_lane,
                                                 rrsf_error_v1 *error);

RRSF_EXPORT uint32_t RRSF_CALL rrsf_lane_run_v1(rrsf_lane *lane,
                                                const rrsf_run_desc_v1 *desc,
                                                rrsf_output_v1 *output,
                                                rrsf_report_v1 *report,
                                                rrsf_error_v1 *error);

RRSF_EXPORT void RRSF_CALL rrsf_lane_request_cancel_v1(rrsf_lane *lane);
RRSF_EXPORT void RRSF_CALL rrsf_lane_destroy_v1(rrsf_lane *lane);
RRSF_EXPORT void RRSF_CALL rrsf_plan_destroy_v1(rrsf_plan *plan);

#ifdef __cplusplus
}
#endif

#endif
