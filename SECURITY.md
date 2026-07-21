# EagleEye Security Policy

[English](SECURITY.md) | [日本語](SECURITY.ja.md)

> The English version is the canonical policy. The Japanese translation is provided for convenience.

## Supported versions

Security fixes target the latest `1.x` release line. Confirm that the issue reproduces on the latest public release.

## Reporting a vulnerability

Do not post personal data, confidential information, exploits, or undisclosed vulnerabilities in a public issue. Use **Security → Report a vulnerability** in the GitHub repository to submit a report through Private Vulnerability Reporting.

Include the following information and use synthetic values instead of real data:

- Affected version or commit
- Preconditions and minimal reproduction steps
- Expected and actual results
- Scope of impact
- Logs, video, or proof of concept with secrets removed

Maintainers will coordinate acknowledgment, triage, remediation, and disclosure timing in the same private advisory. This project does not promise a bug bounty.

## Default security boundaries

- API, MCP, and reporting features prefer loopback and restrict Host values and browser origins.
- Replay permits only loopback HTTP(S) by default and applies the same boundary to redirects and subresources.
- URL Audit requires explicit target authorization, pins each connection to a validated DNS result,
  follows only same-host safe redirects, and uses only fixed observation requests. It is capped at
  10 requests, 4 MiB, 30 seconds, and two concurrent audits.
- URL Audit defaults to global addresses. Localhost needs a request flag and environment opt-in;
  LAN, link-local, metadata, multicast, unspecified, and reserved addresses are always denied.
- The Chrome extension requests only `activeTab`, `scripting`, session-only storage, and two loopback host permissions.
- Form values, cookies, authentication headers, and `FormData` are not recorded.
- Screenshots are opt-in and are not included in AI prompts.
- Provider tokens and API keys are not returned in responses and are stored in the operating-system keychain where supported.
- Codex turns are read-only and ephemeral, reject approval requests, and require a fixed JSON Schema.
- Automated fixes require a local non-production target, a clean Git worktree, a fresh one-use attestation, change limits, and fixed validation; failures are rolled back.
- API input cannot execute external commands or arbitrary paths; fixed registries and allowlists are used.

## Operational limitations

EagleEye is not a substitute for an authentication or authorization product, DLP, WAF, EDR, or regulatory certification. It does not guarantee complete isolation from other loopback processes, operating-system administrators, or malicious browser extensions. On shared devices, use separate operating-system accounts, disk encryption, and short retention periods.

If you enable `EAGLEEYE_ALLOW_REMOTE=1`, external binding, a reverse proxy, cloud AI, or a remote Report Hub, the operator must add TLS, strong authentication, least privilege, network allowlists, rate limits, audit logging, encrypted backups, and deletion procedures. Never expose the default loopback API to the internet without authentication.

## Authorized testing only

Test only targets you own or are explicitly authorized to test. Credential theft, rate-limit bypass, destructive payloads, availability attacks, and acquisition of third-party data are prohibited. Production writes, payments, identity verification, legal consent, publication, and final submission actions must remain human approval boundaries.

URL Audit is not a penetration test. Do not extend its fixed request set with exploit payloads, port
scans, directory brute force, credential attempts, or state-changing requests.

## Release security gate

At minimum, each public release must pass the complete pytest suite, Ruff, the extension verifier, ESLint, dependency audits, Gitleaks, scans of the publication candidate for personal information and absolute paths, and CI. Results must be retained in a report.
