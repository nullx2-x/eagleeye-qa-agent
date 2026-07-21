# EagleEye Privacy Policy

[English](PRIVACY.md) | [日本語](PRIVACY.ja.md)

> The English version is the canonical policy. The Japanese translation is provided for convenience.

Last updated: July 22, 2026

EagleEye is a local-first QA tool for testing websites that the user controls or is legitimately authorized to test. This policy covers the default configuration of the open-source version. If an operator adds external AI, remote storage, custom authentication, or third-party sites, that operator must define the purposes, legal basis, retention period, and notices for the additional processing.

## 1. Data handled by the default configuration

| Category | Data | Default storage location |
|---|---|---|
| Session settings | Session name and test objective entered in the EagleEye popup | Device running EagleEye |
| URLs | HTTP(S) URLs with userinfo, fragments, and query keys that appear to contain secrets removed | Device running EagleEye |
| Action summaries | Action type (click / fill / select / check), timestamp, element role and name, and a constrained selector | Device running EagleEye |
| DOM summaries | Size-limited accessible summaries of page titles, headings, landmarks, and controls | Device running EagleEye |
| Optional images | Visible-viewport screenshots captured at start and stop only when explicitly enabled by the user | Device running EagleEye |
| Replay evidence | Results, screenshots, WebM recordings, byte counts, SHA-256 hashes, and timestamps | Device running EagleEye |
| Extension state | Current session state stored only in `chrome.storage.session` | Current Chrome session |

EagleEye does not collect or transmit values entered into web forms, selected values, cookies, authentication headers, `FormData`, passwords, one-time passwords, or payment information. However, if personal or confidential information is visible in page titles, headings, control names, or optional screenshots, that visible information may be included in a summary or image.

EagleEye does not include product telemetry that sends usage data to its developers. It does not automatically publish data, submit it to Report Hub, or post it to GitHub.

## 2. Data sent to AI providers

Only when the user invokes **AI generation**, EagleEye sends the following minimized information to the configured AI provider:

- Test objective
- URL with ID-like path segments and query values redacted
- Action types and constrained element summaries
- Size-limited DOM summary
- Safety constraints prohibiting requests for credentials, payments, or production writes

Web-form values and screenshots are not included in AI prompts. The Codex App Server path uses the local ChatGPT login managed by Codex; EagleEye does not read or store OAuth tokens. When the OpenAI API is selected directly, authentication uses an API key. API use and ChatGPT/Codex use are governed by different agreements and retention policies, so operators should review the current policies for the provider and product they select.

## 3. Purposes of processing

Data is processed only to generate test cases for sites designated by the user, replay tests, assess quality, analyze failures, create evidence reports, and perform explicit exports. EagleEye does not use data for advertising, personal profiling, credit decisions, or data sales.

## 4. Consent and valid authorization

Before recording begins, the Chrome extension displays prominent notices about recorded data, AI transmission, and optional screenshots. The start button remains disabled until the user confirms both authorization to test the target site and consent to the recording. The operator is responsible for giving required notices to site owners, administrators, employees, customers, and other data subjects, and for establishing an appropriate legal basis.

Do not begin recording on unauthorized sites, third-party accounts, highly sensitive medical, financial, employment, or child-related screens, or screens displaying credentials or payment information.

## 5. Retention and deletion

The default configuration does not impose an automatic retention period; users control data stored on their devices. When data is no longer needed, use **Delete this session from this device** in the popup or `DELETE /api/v1/browser-agent/sessions/{session_id}` to delete the session, DOM summaries, screenshots, replay videos, generated specs/YAML, and run results. Extension state is also cleared when the Chrome session ends or the extension is reloaded, disabled, or updated.

If a user copies data to backups, Report Hub, GitHub, chat systems, ticketing systems, or other destinations, the user must delete those copies from each destination separately.

## 6. Security measures

- The API binds to loopback by default, and replay targets are loopback by default.
- Host, Origin, and CORS values are validated against exact allowlists, and credentialed CORS is disabled.
- HTTP(S) redirects and subresources that leave the permitted boundary are blocked during replay.
- Optional screenshots are limited to 3 MiB; DOM summaries and API responses have count and length limits.
- HTML output is escaped, and security headers and a Content Security Policy are applied.
- API keys and similar secrets are stored in the operating-system keychain and are not returned in API responses.
- Absolute paths in reports are converted to project-relative or redacted representations.

See [SECURITY.md](SECURITY.md) for details.

## 7. Third-party disclosure, international transfers, and subprocessors

The default configuration does not send data to servers operated by the developers. If a user selects cloud AI, an external Report Hub, GitHub, or another service, the transmission occurs at the user's direction. Before use, review the recipient's location, subprocessors, retention, training use, cross-border transfers, and deletion options.

## 8. Scope of APPI, GDPR, and similar compliance

The project incorporates purpose disclosure, data minimization, privacy by default, access restrictions, security measures, deletion mechanisms, and a security-incident contact path into its technical design. It does not automatically guarantee or certify compliance for any specific organization, jurisdiction, or dataset. The actual operator must determine roles such as personal information handling business operator, controller, or processor, as well as legal basis, DPIAs, processing records, processor agreements, retention periods, data-subject notices and rights handling, and supervisory-authority reporting.

See [COMPLIANCE.md](COMPLIANCE.md) for the technical and operational control matrix.

## 9. Contact and incident reporting

Maintainers of the open-source version do not receive user data in the default configuration. If you discover a vulnerability or accidental disclosure, do not include personal data in a public issue. Use GitHub Private Vulnerability Reporting. For general improvement requests, open an issue containing only the minimum necessary information and excluding personal or confidential data.

## 10. Changes to this policy

Before materially changing collected data, destinations, or purposes, the project will update this policy and the extension's prominent disclosure and will request renewed consent when appropriate.
