# SZL Platform — one entry point for humans and CI.
# Every target is safe to run repeatedly. Nothing here mutates the world:
# audits read, builders write only under ./dist and ./artifacts.
PY ?= python3
PACKAGES := $(wildcard packages/*) alignment

.PHONY: install test lint verify audit doctor clean

## install: editable-install every package that has a pyproject.toml
install:
	@for p in $(PACKAGES); do \
		if [ -f "$$p/pyproject.toml" ]; then \
			echo "== install $$p"; $(PY) -m pip install -q -e $$p || exit 1; \
		fi; \
	done
	$(PY) -m pip install -q pytest ruff

## test: run the full suite, one pytest invocation per package (monorepo-safe:
## packages own their own conftest/helpers; a single shared run collides)
test:
	@fail=0; for p in $(PACKAGES); do \
		if [ -d "$$p/tests" ]; then \
			echo "== test $$p"; \
			$(PY) -m pytest "$$p" -q || fail=1; \
		fi; \
	done; exit $$fail

## lint: ruff across all packages
lint:
	$(PY) -m ruff check packages

## verify: receipts must verify, payload must rebuild byte-identical
verify: test
	$(PY) -m szl_receipts.cli --help >/dev/null
	@if [ -d packages/szl-payload ]; then $(PY) -m szl_payload.build verify; fi

## idempotent: build twice, outputs must be byte-identical (determinism gate)
idempotent:
	@if [ -d packages/szl-payload ]; then \
		$(PY) -m szl_payload.build && cp dist/SZL_MASTER_PAYLOAD_V14.md /tmp/_p1.md && \
		$(PY) -m szl_payload.build && diff -q /tmp/_p1.md dist/SZL_MASTER_PAYLOAD_V14.md; \
	else echo "szl-payload not present yet"; fi

## audit: read-only estate audit (requires GH_TOKEN in env)
audit:
	$(PY) -m szl_estate.audit --org szl-holdings --out artifacts/audits || true

## doctor: environment, credentials, DNS, tunnels — exits non-zero on FATAL
doctor:
	@$(PY) -m szl_estate.doctor || true

clean:
	rm -rf dist artifacts/audits .pytest_cache **/__pycache__
