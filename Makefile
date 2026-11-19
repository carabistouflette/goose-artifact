GOOSE ?= .toolchain/goose/build/goose
CC ?= gcc
SANITIZER_CC ?= gcc
OUTPUT ?= .build/results.json
CFLAGS = -std=c11 -Wall -Wextra -Werror
.NOTPARALLEL:
.PHONY: setup format check api signals test sanitize bench bench-smoke
setup:
	./scripts/setup-goose.sh
format:
	python3 examples/download/signals/fingerprint.py
	"$(GOOSE)" format artifact.goose tests examples
check:
	python3 examples/download/signals/fingerprint.py --check
	"$(GOOSE)" format --check artifact.goose tests examples
	"$(GOOSE)" check tests/api.goose
	"$(GOOSE)" check examples/download/main.goose
	python3 -m py_compile tests/*.py bench/measure.py examples/download/signals/fingerprint.py
	git diff --check
api:
	mkdir -p .build
	"$(GOOSE)" run tests/api.goose
	"$(GOOSE)" run tests/api.goose --debug
	"$(GOOSE)" build tests/api.goose --standalone --cc "$(CC)" -O2 -o .build/api
	./.build/api
signals:
	mkdir -p .build
	$(CC) $(CFLAGS) examples/download/signals/test.c examples/download/signals/signals.c -Wl,--wrap=sigaction -o .build/signals
	./.build/signals
test: api signals
	python3 tests/integration.py --goose "$(abspath $(GOOSE))" --cc "$(CC)" --output "$(OUTPUT)"
sanitize:
	mkdir -p .build
	$(SANITIZER_CC) $(CFLAGS) -O1 -g -fno-omit-frame-pointer -fsanitize=address,undefined -no-pie examples/download/signals/test.c examples/download/signals/signals.c -Wl,--wrap=sigaction -o .build/signals-sanitize-$(notdir $(SANITIZER_CC))
	ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./.build/signals-sanitize-$(notdir $(SANITIZER_CC))
	python3 tests/integration.py --goose "$(abspath $(GOOSE))" --cc "$(SANITIZER_CC)" --sanitize --output "$(OUTPUT)"
bench:
	mkdir -p .build
	python3 bench/measure.py --goose "$(abspath $(GOOSE))" --cc "$(CC)" --output .build/bench.json
bench-smoke:
	mkdir -p .build
	python3 bench/measure.py --goose "$(abspath $(GOOSE))" --cc "$(CC)" --sizes 65536,1048576 --samples 1,1 --controls 1 --startup-controls 1 --output .build/bench-smoke.json --force
