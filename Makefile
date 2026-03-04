# File: Makefile
# Path: Makefile
# Role: Developer convenience targets for common local workflows.
# Used By:
#  - local development
#  - CI jobs (optional)
# Depends On:
#  - scripts/ui/build.sh
#  - scripts/ui/verify_dist_sync.sh
# Notes:
#  - Keep targets thin wrappers around versioned scripts.

.PHONY: ui-build ui-verify rc-signoff

ui-build:
	./scripts/ui/build.sh

ui-verify:
	./scripts/ui/verify_dist_sync.sh

rc-signoff:
	python scripts/release/rc_signoff.py --out .local/rc-signoff.md
