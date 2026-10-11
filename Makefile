CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Werror -pedantic -O2

.PHONY: all test clean
all: test_shush_registry

test_shush_registry: shush_registry.c test_shush_registry.c shush_registry.h
	$(CC) $(CFLAGS) shush_registry.c test_shush_registry.c -o $@

test: test_shush_registry
	./test_shush_registry

clean:
	rm -f test_shush_registry
