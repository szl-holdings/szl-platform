# szl-payload — package-local Makefile.
#
# Doctrine: sections/ is the source of truth; dist/ is derived and is never
# hand-edited. The payload body carries no timestamps (build time lives only
# in the export receipt), which is what makes `make idempotent` a real proof.
#
# PYTHONPATH carries ../szl-receipts/src so the estate RFC 8785 JCS fallback
# (szl_receipts.jcs) is importable when the pinned rfc8785 distribution is
# not available in the environment.

PACKAGE_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
RECEIPTS_SRC := $(abspath $(PACKAGE_ROOT)/../szl-receipts/src)
export PYTHONPATH := $(PACKAGE_ROOT)/src:$(RECEIPTS_SRC)$(if $(PYTHONPATH),:$(PYTHONPATH))

PY ?= python3
MODULE ?= szl_payload.build

.PHONY: all generate compile extract export verify idempotent clean test

all: generate compile extract export

generate:
	$(PY) -m $(MODULE) generate --root $(PACKAGE_ROOT)

compile:
	$(PY) -m $(MODULE) compile --root $(PACKAGE_ROOT)

extract:
	$(PY) -m $(MODULE) extract --root $(PACKAGE_ROOT)

export:
	$(PY) -m $(MODULE) export --root $(PACKAGE_ROOT)

# verify: re-digest sections, re-run gates over the built file, assert the
# export manifest is honestly named with signatures == [], grep dist/ for the
# forbidden domain, and assert publication_eligible is false.
verify:
	$(PY) -m $(MODULE) verify --root $(PACKAGE_ROOT)

# idempotent: build → copy → rebuild → byte-identical diff. Possible only
# because the payload body embeds no timestamps.
idempotent: clean
	$(MAKE) --no-print-directory all
	rm -rf /tmp/szl-payload-dist-first
	cp -r $(PACKAGE_ROOT)/dist /tmp/szl-payload-dist-first
	$(MAKE) --no-print-directory all
	diff -r -q /tmp/szl-payload-dist-first $(PACKAGE_ROOT)/dist
	@echo "idempotent: rebuild is byte-identical"

test:
	$(PY) -m pytest -q

clean:
	rm -rf $(PACKAGE_ROOT)/dist
