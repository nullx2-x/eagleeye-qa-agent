## Summary

Describe the user-visible change and its trust-boundary impact.

## Verification

- [ ] Tests relevant to the change pass.
- [ ] Ruff lint and format checks pass for Python changes.
- [ ] Chrome extension verifier and ESLint pass for extension changes.
- [ ] `python scripts/publication_audit.py` passes.
- [ ] No credential, token, private path, personal data, or generated runtime artifact is included.
- [ ] New or changed dependencies have a compatible license and a documented reason.
- [ ] Security, privacy, and compliance documentation remains accurate.

## Risk and rollback

State the remaining risk and the exact rollback commit or procedure.
