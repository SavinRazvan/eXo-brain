# GitHub Actions Architecture Fitness Skeleton

## Goal
Provide a ready-to-paste GitHub Actions workflow skeleton that maps architecture fitness checklist steps to CI jobs.

## Usage
- Copy this into `.github/workflows/architecture-fitness.yml`.
- Replace placeholder commands with your actual scripts/tooling.
- Keep `architecture_lint` and `forbidden_import_scan` as required checks on protected branches.

## Workflow Skeleton
```yaml
name: architecture-fitness

on:
  pull_request:
    branches: [main]
    paths:
      - "src/**"
      - "configs/**"
      - "tests/**"
      - ".github/workflows/**"
  push:
    branches: [main]

concurrency:
  group: architecture-fitness-${{ github.ref }}
  cancel-in-progress: true

jobs:
  architecture_lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
      - name: Validate layer boundaries
        run: |
          # replace with your boundary checker
          python scripts/architecture/validate_layers.py

  forbidden_import_scan:
    runs-on: ubuntu-latest
    needs: [architecture_lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Scan forbidden imports
        run: |
          # examples:
          # - core importing provider SDKs
          # - core importing transport/controller layers
          python scripts/architecture/scan_forbidden_imports.py

  contract_tests:
    runs-on: ubuntu-latest
    needs: [forbidden_import_scan]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
      - name: Runtime adapter contract tests
        run: pytest tests/contracts/runtime -q
      - name: Policy and tool envelope contract tests
        run: pytest tests/contracts/policy tests/contracts/tools -q

  integration_architecture_fitness:
    runs-on: ubuntu-latest
    needs: [contract_tests]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
      - name: Deterministic side-effect path integration
        run: pytest tests/integration/test_deterministic_tool_path.py -q
      - name: Adapter parity integration
        run: pytest tests/integration/test_multi_adapter_workflow_parity.py -q

  security_scan:
    runs-on: ubuntu-latest
    needs: [integration_architecture_fitness]
    steps:
      - uses: actions/checkout@v4
      - name: Secret scan
        run: |
          # replace with your scanner command
          echo "run secret scanner"
      - name: Dependency vulnerability scan
        run: |
          # replace with your scanner command
          echo "run dependency scanner"

  evidence_bundle_publish:
    runs-on: ubuntu-latest
    needs: [security_scan]
    if: always()
    steps:
      - uses: actions/checkout@v4
      - name: Build architecture fitness evidence bundle
        run: |
          mkdir -p artifacts/evidence
          # Collect reports from prior jobs or generated files
          # architecture boundary report, forbidden imports, contracts, integration, security
      - name: Upload evidence artifact
        uses: actions/upload-artifact@v4
        with:
          name: architecture-fitness-evidence
          path: artifacts/evidence
```

## Mapping to Checklist (`35-*`)
- `architecture_lint` -> Layer boundary rules + anti-monolith structural rules.
- `forbidden_import_scan` -> provider-neutral and cross-layer forbidden import checks.
- `contract_tests` -> runtime/policy/tool contract compliance.
- `integration_architecture_fitness` -> deterministic path + adapter parity.
- `security_scan` -> observability/security invariants (secret/dependency checks).
- `evidence_bundle_publish` -> required PR/RC evidence artifacts.

## Related Docs
- `35-architecture-fitness-ci-checklist.md`
- `17-enterprise-cicd-governance.md`
- `23-pr-release-evidence-templates.md`
