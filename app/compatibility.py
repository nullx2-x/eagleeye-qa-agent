from .strategy_models import CompatibilityLevel

FUNCTIONAL_TESTS = (
    "instruction-conformance",
    "differential-oracle",
    "exception-conformance",
    "cp0-conformance",
    "tlb-conformance",
    "fpu-conformance",
    "cache-coherency",
    "deterministic-replay",
)
SYSTEM_TESTS = (
    "rom-matrix",
    "rsp-rdp-integration",
    "audio-video-sync",
    "long-soak",
)
CYCLE_TESTS = (
    "cycle-trace",
    "cache-timing",
    "sysad-protocol",
    "interrupt-timing",
    "reset-timing",
)
PHYSICAL_TESTS = (
    "silicon-waveform",
    "pvt-corners",
    "parasitic-correlation",
    "independent-lab-reproduction",
)

COMPATIBILITY_TESTS = {
    CompatibilityLevel.FUNCTIONAL: FUNCTIONAL_TESTS,
    CompatibilityLevel.SYSTEM: FUNCTIONAL_TESTS + SYSTEM_TESTS,
    CompatibilityLevel.CYCLE: FUNCTIONAL_TESTS + SYSTEM_TESTS + CYCLE_TESTS,
    CompatibilityLevel.PHYSICAL: FUNCTIONAL_TESTS + SYSTEM_TESTS + CYCLE_TESTS + PHYSICAL_TESTS,
}

FULL_COVERAGE_TESTS = frozenset(
    {
        "instruction-conformance",
        "exception-conformance",
        "cp0-conformance",
        "tlb-conformance",
        "fpu-conformance",
        "cache-coherency",
        "rom-matrix",
        "rsp-rdp-integration",
        "audio-video-sync",
        "long-soak",
        "cycle-trace",
        "cache-timing",
        "sysad-protocol",
        "interrupt-timing",
        "reset-timing",
        "silicon-waveform",
        "pvt-corners",
        "parasitic-correlation",
        "independent-lab-reproduction",
    }
)


def compatibility_tests(level: CompatibilityLevel | None) -> list[str]:
    if level is None:
        return []
    return list(COMPATIBILITY_TESTS[level])
