# Security Policy

## Supported Versions

eXo-brain is a single-maintainer reference implementation. There are no
commercial support tiers, no SLA, and no guaranteed long-term support branch at
this time.

Security fixes, when accepted, target the current `main` branch first.

## Reporting a Vulnerability

Please do **not** open a public issue for suspected vulnerabilities.

Report security issues privately through the maintainer contact listed on the
GitHub profile for `@SavinRazvan` or by using GitHub's private vulnerability
reporting feature if it is enabled for this repository.

When reporting, include:

- A clear description of the issue.
- Reproduction steps or a minimal proof of concept.
- Affected files, APIs, or configuration.
- Expected impact and any known mitigations.

## Response Expectations

This is maintained part-time. Best-effort response target:

- Initial acknowledgement: within 7 days.
- Triage decision: within 14 days after enough information is available.
- Fix timeline: depends on severity, maintainer availability, and project scope.

No bug bounty program is currently offered.

## Disclosure

Please follow responsible disclosure. A 90-day coordinated disclosure window is
reasonable for most issues unless active exploitation requires a faster public
notice.

## Security Scope

In scope:

- Vulnerabilities in code under this repository.
- Policy or deterministic-execution bypasses in the default control-plane path.
- Tenant isolation weaknesses in documented local deployment modes.
- Secret-handling or redaction bugs in project code.

Out of scope:

- Vulnerabilities in third-party provider APIs or SDKs.
- Misconfiguration of private deployments outside this repository.
- Social engineering, spam, or denial-of-service testing against maintainer
  accounts.
- Issues in local artifacts intentionally excluded from git, such as `.env`,
  `.local/`, `.exo_data/`, and `_research_results/`.
