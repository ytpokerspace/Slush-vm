#include "shush_registry.h"

#include <string.h>

static const ShushType add_inputs[] = { SHUSH_TYPE_I64, SHUSH_TYPE_I64 };
static const ShushType add_outputs[] = { SHUSH_TYPE_I64 };
static const char *const add_permissions[] = { NULL };

static const ShushCapability capabilities[] = {
    { "math.add", "1.0.0", add_inputs, 2, add_outputs, 1,
      "vm_op_add", add_permissions, 0, SHUSH_TEST_VERIFIED }
};

static int has_permission(const ShushResolvePolicy *policy, const char *required) {
    size_t i;
    if (!required || !required[0]) return 1;
    if (!policy) return 0;
    for (i = 0; i < policy->granted_count; ++i) {
        if (policy->granted_permissions && policy->granted_permissions[i] &&
            strcmp(policy->granted_permissions[i], required) == 0) return 1;
    }
    return 0;
}

const ShushCapability *shush_registry_find_exact(const char *id,
                                                  const char *version) {
    size_t i;
    if (!id || !version) return NULL;
    for (i = 0; i < sizeof(capabilities) / sizeof(capabilities[0]); ++i) {
        if (strcmp(capabilities[i].id, id) == 0 &&
            strcmp(capabilities[i].version, version) == 0) return &capabilities[i];
    }
    return NULL;
}

ShushResolveStatus shush_resolve(const char *id, const char *version,
                                 const ShushType *inputs, size_t input_count,
                                 const ShushResolvePolicy *policy,
                                 const ShushCapability **out) {
    const ShushCapability *cap;
    size_t i;
    if (out) *out = NULL;
    cap = shush_registry_find_exact(id, version);
    if (!cap) return SHUSH_RESOLVE_NOT_FOUND;
    if (input_count != cap->input_count || (input_count && !inputs))
        return SHUSH_RESOLVE_BAD_SIGNATURE;
    for (i = 0; i < input_count; ++i)
        if (inputs[i] != cap->inputs[i]) return SHUSH_RESOLVE_BAD_SIGNATURE;
    if (policy && policy->require_verified &&
        cap->test_status != SHUSH_TEST_VERIFIED) return SHUSH_RESOLVE_UNVERIFIED;
    for (i = 0; i < cap->permission_count; ++i)
        if (!has_permission(policy, cap->permissions[i]))
            return SHUSH_RESOLVE_PERMISSION_DENIED;
    if (out) *out = cap;
    return SHUSH_RESOLVE_OK;
}

const char *shush_resolve_status_string(ShushResolveStatus status) {
    switch (status) {
        case SHUSH_RESOLVE_OK: return "ok";
        case SHUSH_RESOLVE_NOT_FOUND: return "capability or exact version not found";
        case SHUSH_RESOLVE_BAD_SIGNATURE: return "input signature incompatible";
        case SHUSH_RESOLVE_PERMISSION_DENIED: return "required permission not granted";
        case SHUSH_RESOLVE_UNVERIFIED: return "capability has not passed required tests";
        default: return "unknown resolver status";
    }
}
