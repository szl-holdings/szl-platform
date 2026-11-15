# SZL Platform — one entry point for humans and CI.
# Every target is safe to run repeatedly. Nothing here mutates the world:
# audits read, builders write only under ./dist and ./artifacts.
PY ?= python3
# packages/szl-receipts is the trust core and a path/peer dependency of
# sibling packages (szl-adversarial, szl-payload, szl-evidence-litellm, ...).
# It is not published to any index, so it must be editable-installed FIRST.
PACKAGES := packages/szl-receipts $(filter-out packages/szl-receipts,$(wildcard packages/*)) alignment

.PHONY: install test lint verify idempotent audit doctor clean

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

## lint: ruff across every installable package (packages/* and alignment/;
## each directory's own pyproject.toml config applies)
lint:
	$(PY) -m ruff check packages alignment

## verify: receipts must verify, payload must rebuild byte-identical
verify: test
	$(PY) -m szl_receipts.cli --help >/dev/null
	@if [ -d packages/szl-payload ]; then $(PY) -m szl_payload.build verify --root packages/szl-payload; fi

## idempotent: build twice, outputs must be byte-identical (determinism gate)
idempotent:
	@if [ -d packages/szl-payload ]; then \
		$(PY) -m szl_payload.build --root packages/szl-payload && cp packages/szl-payload/dist/SZL_MASTER_PAYLOAD_V14.md /tmp/_p1.md && \
		$(PY) -m szl_payload.build --root packages/szl-payload && diff -q /tmp/_p1.md packages/szl-payload/dist/SZL_MASTER_PAYLOAD_V14.md; \
	else echo "szl-payload not present yet"; fi

## audit: read-only estate audit (requires GH_TOKEN in env). Findings are
## audit output and still exit 0; a non-zero exit means the audit itself broke.
## Rewrites the committed snapshot under artifacts/audits.
audit:
	$(PY) -m szl_estate.audit --org szl-holdings --out artifacts/audits

## doctor: environment, credentials, DNS, tunnels — exits 1 if any check is FAIL.
## To run every daily target even after a FAIL: make -k doctor audit verify
doctor:
	@$(PY) -m szl_estate.doctor

## clean: remove build/test caches only — never tracked files (artifacts/ is
## committed evidence; regenerate it with `make audit`, do not delete it)
clean:
	rm -rf packages/szl-payload/dist .pytest_cache .ruff_cache
	find . -path ./.git -prune -o -type d \( -name __pycache__ -o -name .pytest_cache \) -exec rm -rf {} +
