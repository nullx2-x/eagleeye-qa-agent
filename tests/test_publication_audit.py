from pathlib import Path

from scripts.publication_audit import (
    audit_repository,
    check_action_pins,
    check_environment_template,
)

ROOT = Path(__file__).resolve().parents[1]


def test_current_repository_passes_publication_audit() -> None:
    assert audit_repository(ROOT) == []


def test_action_pin_check_rejects_mutable_tag(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("steps:\n  - uses: actions/checkout@v7\n", encoding="utf-8")

    findings = check_action_pins(tmp_path, {".github/workflows/ci.yml"})

    assert [finding.rule for finding in findings] == ["ACTION_NOT_PINNED_TO_SHA"]


def test_environment_template_rejects_nonempty_secret(tmp_path: Path) -> None:
    (tmp_path / ".env.example").write_text("OPENAI_API_KEY=not-a-real-key\n", encoding="utf-8")

    findings = check_environment_template(tmp_path)

    assert [finding.rule for finding in findings] == ["ENV_EXAMPLE_SECRET_VALUE"]
