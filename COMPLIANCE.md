# EagleEye Compliance Review

[English](COMPLIANCE.md) | [日本語](COMPLIANCE.ja.md)

> The English version is the canonical document. The Japanese translation is provided for convenience.

Last technical review: July 20, 2026

The result is a **CONDITIONAL PASS**. The default configuration of the open-source version implements data minimization, explicit consent, local-first storage, security controls, deletion, and non-retention of secrets. This is not a certification of compliance for any specific organization. Responsibility remains with the operator that determines the target sites, operating jurisdictions, data subjects, contracts, AI providers, and remote storage.

## Control matrix

| Area | Implementation and documentation | Result | Operator responsibility |
|---|---|---|---|
| Purpose disclosure | Prominent notice in the popup and [PRIVACY.md](PRIVACY.md) | PASS | Notices on the target site and internal policies |
| Explicit consent | Checkboxes confirming recording details and authorization to test the target site are required | PASS | Determine when a legal basis other than consent is required |
| Data minimization | Does not collect body text, HTML, input values, or cookies; uses a size-limited DOM summary | PASS | Do not start recording on confidential screens |
| Screenshots | Off by default, separate checkbox, visible viewport only, not sent to AI | PASS | Visually inspect and mask PII in images |
| Retention and deletion | Local storage, session-only extension state, one-click deletion API/UI | PASS | Delete backups and copies shared externally |
| Security controls | Host/CORS/Origin/CSP, `no-store`, path confinement, and redirect guard | PASS | Add TLS, authentication, and rate limits for remote deployment |
| URL Audit | Explicit authorization, observation-only methods, pinned IP, SSRF deny rules, fixed request/body/time/concurrency budgets, and local reports | PASS | Confirm ownership/authorization and delete local reports under the operator's retention policy |
| Third-party disclosure | Sends a minimized prompt to the selected provider only during AI generation | PASS | Provider contracts, international transfers, DPA/DPIA |
| Data-subject rights | View and export local data; delete individual sessions | PASS | Request intake, identity verification, and deadlines in organizational deployments |
| Breach response | Private security reporting and incident contact policy | PARTIAL | Organizational response procedures and regulator/data-subject notification |
| Children and sensitive data | Prohibited or directed to be avoided | POLICY | Add age verification, additional consent, or a DPIA if required |
| Chrome Web Store Limited Use | Single QA purpose, minimal permissions, local-first design, prominent disclosure | PASS | Privacy tab and Data Use declarations when publishing to the Store |
| OpenAI use | Distinguishes API and Codex/ChatGPT paths and does not retain tokens | PASS | Review current agreements and data controls for the selected product |

## Official principles reviewed

- Japan's Personal Information Protection Commission, *Guidelines on the Act on the Protection of Personal Information*: purpose specification, security controls, third-party disclosure, disclosure and other rights, and breach response.
  <https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/>
- GDPR text: data minimization, privacy by design and by default, and controller/processor responsibilities.
  <https://eur-lex.europa.eu/eli/reg/2016/679/oj>
- Chrome Web Store User Data FAQ / Limited Use: website content, browsing activity, and screenshots are user data and require prominent disclosure, consent, minimal permissions, and a privacy policy.
  <https://developer.chrome.com/docs/webstore/program-policies/user-data-faq>
- OpenAI API data controls: API and consumer/product paths have different retention and training policies, so the actual path must be identified.
  <https://developers.openai.com/api/docs/guides/your-data>

## Decisions required before publication or deployment

1. Roles such as controller, processor, and personal information handling business operator, plus a contact point
2. Authorization to test target sites, notices to employees and customers, and legal basis
3. Retention period, backups, deletion, access control, and incident response
4. AI, Report Hub, GitHub, and other recipients; DPAs, international transfers, and subprocessors
5. A DPIA or equivalent assessment for high-risk processing
6. Chrome Web Store Data Use declarations and policy URL when publishing to the Store

For deployments requiring legal determinations, obtain review from a qualified professional in the applicable jurisdiction.
