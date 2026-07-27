#include "rapidrbf_scalfmm_probe.h"

#include <stddef.h>

int main(void) {
  rrsf_plan_desc_v1 desc = {0};
  rrsf_resource_grant_v1 grant = {0};
  rrsf_error_v1 error = {0};
  rrsf_plan *plan = NULL;

  grant.struct_size = sizeof(grant);
  grant.abi_version = RRSF_ABI_V1;
  grant.persistent_bytes = 1024;
  grant.transient_bytes = 1024;
  grant.max_threads = 1;

  error.struct_size = sizeof(error);
  error.abi_version = RRSF_ABI_V1;

  /* A zero-sized descriptor must be rejected without crossing the C ABI. */
  uint32_t status = rrsf_plan_create_v1(&desc, &grant, &plan, &error);
  return status == RRSF_ABI_MISMATCH && error.stage == 1 && plan == NULL ? 0
                                                                         : 1;
}
