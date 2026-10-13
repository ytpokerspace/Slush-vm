/*
 * SHUSH capability VM — C11 reference slice.
 * This is a small, dependency-free dispatch prototype, not the full SHUSH parser/VM.
 * Aliases resolve only in an explicit namespace to exact canonical ID + version.
 */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define SHUSH_VERSION "0.1.0"
#define PERM_EXEC "capability.execute"

typedef enum {
    SHUSH_OK = 0,
    E_NAMESPACE_REQUIRED,
    E_ALIAS_NOT_FOUND,
    E_ALIAS_AMBIGUOUS,
    E_CAPABILITY_NOT_FOUND,
    E_VERSION_MISMATCH,
    E_CAPABILITY_UNVERIFIED,
    E_PERMISSION_DENIED,
    E_INPUT_TYPE,
    E_OUTPUT_TYPE,
    E_USAGE
} ShushStatus;

typedef struct {
    const char *id;
    const char *version;
    const char *status;
    const char *input_type;
    const char *output_type;
    const char *required_permission;
    const char *handler;
} Capability;

typedef struct {
    const char *symbol;
    const char *name_space;
    const char *capability_id;
    const char *version;
} Alias;

static const Capability CAPABILITIES[] = {
    {"text.normalize", "1.0.0", "tested", "STR", "STR", PERM_EXEC, "normalize"},
    {"text.word_count", "1.0.0", "tested", "STR", "NUM", PERM_EXEC, "word_count"}
};
static const size_t CAPABILITY_COUNT = sizeof(CAPABILITIES) / sizeof(CAPABILITIES[0]);

static const Alias ALIASES[] = {
    {"🧹", "workflow", "text.normalize", "1.0.0"},
    {"🧮", "workflow", "text.word_count", "1.0.0"}
};
static const size_t ALIAS_COUNT = sizeof(ALIASES) / sizeof(ALIASES[0]);

static const char *status_name(ShushStatus status) {
    switch (status) {
        case SHUSH_OK: return "OK";
        case E_NAMESPACE_REQUIRED: return "E_NAMESPACE_REQUIRED";
        case E_ALIAS_NOT_FOUND: return "E_ALIAS_NOT_FOUND";
        case E_ALIAS_AMBIGUOUS: return "E_ALIAS_AMBIGUOUS";
        case E_CAPABILITY_NOT_FOUND: return "E_CAPABILITY_NOT_FOUND";
        case E_VERSION_MISMATCH: return "E_VERSION_MISMATCH";
        case E_CAPABILITY_UNVERIFIED: return "E_CAPABILITY_UNVERIFIED";
        case E_PERMISSION_DENIED: return "E_PERMISSION_DENIED";
        case E_INPUT_TYPE: return "E_INPUT_TYPE";
        case E_OUTPUT_TYPE: return "E_OUTPUT_TYPE";
        case E_USAGE: return "E_USAGE";
        default: return "E_UNKNOWN";
    }
}

static const Capability *find_capability(const char *id) {
    size_t i;
    for (i = 0; i < CAPABILITY_COUNT; ++i) {
        if (strcmp(CAPABILITIES[i].id, id) == 0) return &CAPABILITIES[i];
    }
    return NULL;
}

static ShushStatus resolve_alias(const char *symbol, const char *name_space,
                                 const Alias **out) {
    size_t i, matches = 0;
    const Alias *found = NULL;
    if (!name_space || !*name_space) return E_NAMESPACE_REQUIRED;
    for (i = 0; i < ALIAS_COUNT; ++i) {
        if (strcmp(ALIASES[i].symbol, symbol) == 0 &&
            strcmp(ALIASES[i].name_space, name_space) == 0) {
            found = &ALIASES[i];
            ++matches;
        }
    }
    if (matches == 0) return E_ALIAS_NOT_FOUND;
    if (matches > 1) return E_ALIAS_AMBIGUOUS;
    *out = found;
    return SHUSH_OK;
}

static char *normalize_whitespace(const char *input) {
    size_t n = strlen(input), i, out_len = 0;
    char *out = (char *)malloc(n + 1);
    int pending_space = 0;
    if (!out) return NULL;
    for (i = 0; i < n; ++i) {
        unsigned char ch = (unsigned char)input[i];
        if (isspace(ch)) {
            if (out_len > 0) pending_space = 1;
        } else {
            if (pending_space) out[out_len++] = ' ';
            out[out_len++] = (char)ch;
            pending_space = 0;
        }
    }
    out[out_len] = '\0';
    return out;
}

static size_t count_words(const char *input) {
    size_t i, count = 0;
    int in_word = 0;
    for (i = 0; input[i] != '\0'; ++i) {
        unsigned char ch = (unsigned char)input[i];
        if (isspace(ch)) {
            in_word = 0;
        } else if (!in_word) {
            ++count;
            in_word = 1;
        }
    }
    return count;
}

static ShushStatus invoke(const char *symbol, const char *name_space,
                          const char *canonical_id, const char *version,
                          const char *permission, const char *input,
                          char **string_result, size_t *number_result,
                          const char **output_type) {
    const Alias *alias = NULL;
    const Capability *cap;
    ShushStatus status = resolve_alias(symbol, name_space, &alias);
    if (status != SHUSH_OK) return status;

    /* If a caller supplied canonical identity, it must match the alias exactly. */
    if (!canonical_id || strcmp(alias->capability_id, canonical_id) != 0)
        return E_CAPABILITY_NOT_FOUND;
    if (!version || strcmp(alias->version, version) != 0)
        return E_VERSION_MISMATCH;

    cap = find_capability(canonical_id);
    if (!cap) return E_CAPABILITY_NOT_FOUND;
    if (strcmp(cap->version, version) != 0) return E_VERSION_MISMATCH;
    if (strcmp(cap->status, "tested") != 0) return E_CAPABILITY_UNVERIFIED;
    if (!permission || strcmp(permission, cap->required_permission) != 0)
        return E_PERMISSION_DENIED;
    if (!input) return E_INPUT_TYPE;
    if (strcmp(cap->input_type, "STR") != 0) return E_INPUT_TYPE;

    if (strcmp(cap->handler, "normalize") == 0) {
        *string_result = normalize_whitespace(input);
        if (!*string_result) return E_OUTPUT_TYPE;
        *output_type = "STR";
        return SHUSH_OK;
    }
    if (strcmp(cap->handler, "word_count") == 0) {
        *number_result = count_words(input);
        *output_type = "NUM";
        return SHUSH_OK;
    }
    return E_CAPABILITY_NOT_FOUND;
}

static int expect_status(const char *label, ShushStatus actual, ShushStatus expected) {
    if (actual != expected) {
        fprintf(stderr, "FAIL %s: got %s, expected %s\n",
                label, status_name(actual), status_name(expected));
        return 0;
    }
    printf("PASS %s\n", label);
    return 1;
}

static int self_test(void) {
    int passed = 0, total = 0, ok = 1;
    const Alias *alias = NULL;
    char *s = NULL;
    size_t n = 0;
    const char *out_type = NULL;
    ShushStatus st;

#define CHECK(label, expr, expected) do { \
    ++total; st = (expr); \
    if (expect_status((label), st, (expected))) ++passed; else ok = 0; \
} while (0)

    CHECK("resolve normalize alias", resolve_alias("🧹", "workflow", &alias), SHUSH_OK);
    CHECK("unknown emoji rejected", resolve_alias("🦄", "workflow", &alias), E_ALIAS_NOT_FOUND);
    CHECK("namespace required", resolve_alias("🧹", "", &alias), E_NAMESPACE_REQUIRED);
    CHECK("wrong namespace rejected", resolve_alias("🧹", "language", &alias), E_ALIAS_NOT_FOUND);

    ++total;
    st = invoke("🧹", "workflow", "text.normalize", "1.0.0", PERM_EXEC,
                "  hello   SHUSH  ", &s, &n, &out_type);
    if (st == SHUSH_OK && s && strcmp(s, "hello SHUSH") == 0 &&
        strcmp(out_type, "STR") == 0) {
        printf("PASS normalize result\n"); ++passed;
    } else {
        fprintf(stderr, "FAIL normalize result: status=%s result=%s\n",
                status_name(st), s ? s : "(null)"); ok = 0;
    }
    free(s); s = NULL;

    ++total;
    st = invoke("🧮", "workflow", "text.word_count", "1.0.0", PERM_EXEC,
                "one   two\nthree", &s, &n, &out_type);
    if (st == SHUSH_OK && n == 3 && strcmp(out_type, "NUM") == 0) {
        printf("PASS word count result\n"); ++passed;
    } else {
        fprintf(stderr, "FAIL word count result: status=%s count=%zu\n",
                status_name(st), n); ok = 0;
    }

    CHECK("canonical ID mismatch rejected",
          invoke("🧹", "workflow", "text.word_count", "1.0.0", PERM_EXEC,
                 "x", &s, &n, &out_type), E_CAPABILITY_NOT_FOUND);
    CHECK("version mismatch rejected",
          invoke("🧹", "workflow", "text.normalize", "9.9.9", PERM_EXEC,
                 "x", &s, &n, &out_type), E_VERSION_MISMATCH);
    CHECK("permission denied",
          invoke("🧹", "workflow", "text.normalize", "1.0.0", "fs.write",
                 "x", &s, &n, &out_type), E_PERMISSION_DENIED);

#undef CHECK
    printf("C capability VM self-test: %d/%d passed\n", passed, total);
    return ok && passed == total ? 0 : 1;
}

static void usage(const char *argv0) {
    fprintf(stderr,
        "Usage:\n"
        "  %s --self-test\n"
        "  %s call NAMESPACE SYMBOL CAPABILITY_ID VERSION PERMISSION STRING_ARGUMENT\n"
        "Example:\n"
        "  %s call workflow '🧹' text.normalize 1.0.0 capability.execute '  hello   world  '\n",
        argv0, argv0, argv0);
}

int main(int argc, char **argv) {
    char *string_result = NULL;
    size_t number_result = 0;
    const char *output_type = NULL;
    ShushStatus status;

    if (argc == 2 && strcmp(argv[1], "--self-test") == 0) return self_test();
    if (argc == 8 && strcmp(argv[1], "call") == 0) {
        status = invoke(argv[3], argv[2], argv[4], argv[5], argv[6], argv[7],
                        &string_result, &number_result, &output_type);
        if (status != SHUSH_OK) {
            fprintf(stderr, "%s\n", status_name(status));
            free(string_result);
            return 2;
        }
        if (strcmp(output_type, "STR") == 0) {
            printf("%s\n", string_result);
            free(string_result);
        } else if (strcmp(output_type, "NUM") == 0) {
            printf("%zu\n", number_result);
        } else {
            fprintf(stderr, "%s\n", status_name(E_OUTPUT_TYPE));
            free(string_result);
            return 2;
        }
        return 0;
    }
    usage(argv[0]);
    return 64;
}
