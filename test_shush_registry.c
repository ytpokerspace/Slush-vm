#include "shush_registry.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

int main(void) {
    const ShushCapability *cap = (const ShushCapability *)1;
    const ShushType good[] = { SHUSH_TYPE_I64, SHUSH_TYPE_I64 };
    const ShushType bad[] = { SHUSH_TYPE_I64 };
    const ShushResolvePolicy permissive = { NULL, 0, 0 };
    const ShushResolvePolicy require_verified = { NULL, 0, 1 };

    assert(shush_resolve("math.add", "1.0.0", good, 2, &permissive, &cap) == SHUSH_RESOLVE_OK);
    assert(cap != NULL && strcmp(cap->implementation, "vm_op_add") == 0);
    assert(shush_resolve("math.add", "1.0.0", good, 2, &require_verified, &cap) == SHUSH_RESOLVE_UNVERIFIED);
    assert(cap == NULL);
    assert(shush_resolve("math.add", "2.0.0", good, 2, &permissive, &cap) == SHUSH_RESOLVE_NOT_FOUND);
    assert(cap == NULL);
    assert(shush_resolve("math.add", "1.0.0", bad, 1, &permissive, &cap) == SHUSH_RESOLVE_BAD_SIGNATURE);
    assert(cap == NULL);
    assert(shush_resolve("net.fetch", "1.0.0", good, 2, &permissive, &cap) == SHUSH_RESOLVE_NOT_FOUND);
    assert(cap == NULL);
    puts("registry tests: PASS");
    return 0;
}
