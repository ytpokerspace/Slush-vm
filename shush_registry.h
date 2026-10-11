#ifndef SHUSH_REGISTRY_H
#define SHUSH_REGISTRY_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SHUSH_CAP_ID_MAX 64
#define SHUSH_VERSION_MAX 24
#define SHUSH_TYPE_MAX 8
#define SHUSH_IMPL_MAX 64
#define SHUSH_PERMISSION_MAX 32

typedef enum {
    SHUSH_TYPE_I64 = 1
} ShushType;

typedef enum {
    SHUSH_TEST_UNVERIFIED = 0,
    SHUSH_TEST_VERIFIED = 1
} ShushTestStatus;

typedef struct {
    const char *id;
    const char *version;
    const ShushType *inputs;
    size_t input_count;
    const ShushType *outputs;
    size_t output_count;
    const char *implementation;
    const char *const *permissions;
    size_t permission_count;
    ShushTestStatus test_status;
} ShushCapability;

typedef enum {
    SHUSH_RESOLVE_OK = 0,
    SHUSH_RESOLVE_NOT_FOUND,
    SHUSH_RESOLVE_BAD_SIGNATURE,
    SHUSH_RESOLVE_PERMISSION_DENIED,
    SHUSH_RESOLVE_UNVERIFIED
} ShushResolveStatus;

typedef struct {
    const char *const *granted_permissions;
    size_t granted_count;
    int require_verified;
} ShushResolvePolicy;

const ShushCapability *shush_registry_find_exact(const char *id,
                                                  const char *version);
ShushResolveStatus shush_resolve(const char *id, const char *version,
                                 const ShushType *inputs, size_t input_count,
                                 const ShushResolvePolicy *policy,
                                 const ShushCapability **out);
const char *shush_resolve_status_string(ShushResolveStatus status);

#ifdef __cplusplus
}
#endif
#endif
