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

.PHONY: ui-build ui-verify rc-signoff rc-signoff-json db-backup db-restore db-validate

ui-build:
	./scripts/ui/build.sh

ui-verify:
	./scripts/ui/verify_dist_sync.sh

rc-signoff:
	python scripts/release/rc_signoff.py --out .local/rc-signoff.md

rc-signoff-json:
	python scripts/release/parse_rc_signoff.py --in .local/rc-signoff.md --out .local/rc-signoff.json

db-backup:
	python scripts/release/local_data_safety.py backup --meta-out .local/db-backup-meta.json

db-restore:
	python scripts/release/local_data_safety.py restore --force --meta-out .local/db-restore-meta.json

db-validate:
	python scripts/release/local_data_safety.py validate --meta-out .local/db-validate-meta.json
