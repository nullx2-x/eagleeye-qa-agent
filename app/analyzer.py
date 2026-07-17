from .models import FailureAnalysis


def analyze_failure(message: str) -> FailureAnalysis:
    lowered = message.lower()
    if "strict mode" in lowered or "locator" in lowered or "selector" in lowered:
        category = "SELECTOR_CHANGED"
        cause = "The recorded locator no longer identifies one actionable element."
        action = "Prefer an accessible role and name, then add a regression assertion."
    elif "timeout" in lowered:
        category = "TIMEOUT"
        cause = "The expected page state or element did not become available in time."
        action = "Verify navigation readiness and replace brittle waits with observable conditions."
    elif "net::" in lowered or "connection" in lowered:
        category = "NETWORK_FAILURE"
        cause = "The target application was unreachable or returned a network-level failure."
        action = "Check the local service, port, and test isolation before changing application code."
    elif "assert" in lowered or "expect" in lowered:
        category = "ASSERTION_MISMATCH"
        cause = "Observed behavior did not match the generated expectation."
        action = "Confirm product intent, then update either the implementation or the expectation."
    else:
        category = "APPLICATION_OR_TEST_BUG"
        cause = "The evidence is insufficient to distinguish an application defect from a test defect."
        action = "Inspect the screenshot, traceback, and generated steps before proposing a patch."
    return FailureAnalysis(
        category=category,
        summary=message[-600:],
        probable_cause=cause,
        recommended_action=action,
    )
