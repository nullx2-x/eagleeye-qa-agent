from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Workload = Literal["release_assurance", "balanced", "high_volume", "local_private"]


class ModelRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providerId: str
    model: str
    workload: Workload
    stability: Literal["stable", "preview", "local"]
    costTier: Literal["low", "medium", "high"]
    why: str
    minimumHardware: str | None = None
    sourceUrl: str


class ModelRecommendationCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verifiedAt: str
    defaultWorkload: Workload
    defaultProviderId: str
    defaultModel: str
    disclaimer: str
    recommendations: list[ModelRecommendation]


RECOMMENDATIONS = [
    ModelRecommendation(
        providerId="openai",
        model="gpt-5.6-sol",
        workload="release_assurance",
        stability="stable",
        costTier="high",
        why="複雑な根本原因分析、長い証跡、リリース前の反証探索を優先する場合。",
        sourceUrl="https://developers.openai.com/api/docs/models",
    ),
    ModelRecommendation(
        providerId="openai",
        model="gpt-5.6-terra",
        workload="balanced",
        stability="stable",
        costTier="medium",
        why="テスト設計、失敗分析、修正候補の品質と費用の既定バランス。",
        sourceUrl="https://developers.openai.com/api/docs/models",
    ),
    ModelRecommendation(
        providerId="openai",
        model="gpt-5.6-luna",
        workload="high_volume",
        stability="stable",
        costTier="low",
        why="大量ケースの分類、重複検出、一次トリアージ。重大判定は上位モデルか人間で確認する。",
        sourceUrl="https://developers.openai.com/api/docs/models",
    ),
    ModelRecommendation(
        providerId="anthropic",
        model="claude-fable-5",
        workload="release_assurance",
        stability="stable",
        costTier="high",
        why="長時間のエージェント評価と最も難しいQA分析を優先する場合。",
        sourceUrl="https://platform.claude.com/docs/en/about-claude/models/overview",
    ),
    ModelRecommendation(
        providerId="anthropic",
        model="claude-sonnet-5",
        workload="balanced",
        stability="stable",
        costTier="medium",
        why="速度と知能のバランスが必要な日常のケース生成とログ分析。",
        sourceUrl="https://platform.claude.com/docs/en/about-claude/models/overview",
    ),
    ModelRecommendation(
        providerId="google-gemini",
        model="gemini-3.5-flash",
        workload="balanced",
        stability="stable",
        costTier="medium",
        why="安定版で、エージェント・コーディング系QAを低遅延に処理する既定候補。",
        sourceUrl="https://ai.google.dev/gemini-api/docs/models",
    ),
    ModelRecommendation(
        providerId="google-gemini",
        model="gemini-3.1-flash-lite",
        workload="high_volume",
        stability="stable",
        costTier="low",
        why="高頻度の軽量な分類、要約、ケース品質の一次チェック。",
        sourceUrl="https://ai.google.dev/gemini-api/docs/models",
    ),
    ModelRecommendation(
        providerId="ollama",
        model="qwen3-coder:30b",
        workload="local_private",
        stability="local",
        costTier="low",
        why="リポジトリ規模のローカルQAとツール利用。GPU/RAMに余裕がある環境向け。",
        minimumHardware="モデル約19GB。十分なVRAMまたはRAMオフロードが必要。",
        sourceUrl="https://ollama.com/library/qwen3-coder",
    ),
    ModelRecommendation(
        providerId="ollama",
        model="qwen2.5-coder:7b",
        workload="local_private",
        stability="local",
        costTier="low",
        why="8GB級GPUでも扱いやすいローカル一次分析。重大な最終判定には単独利用しない。",
        minimumHardware="量子化により8GB級GPUまたはCPU/RAMで利用可能。",
        sourceUrl="https://ollama.com/library/qwen2.5-coder",
    ),
]


def catalog(
    workload: Workload | None = None,
    provider_id: str | None = None,
) -> ModelRecommendationCatalog:
    items = [
        item
        for item in RECOMMENDATIONS
        if (workload is None or item.workload == workload)
        and (provider_id is None or item.providerId == provider_id)
    ]
    return ModelRecommendationCatalog(
        verifiedAt="2026-07-16",
        defaultWorkload="balanced",
        defaultProviderId="openai",
        defaultModel="gpt-5.6-terra",
        disclaimer=(
            "AIはテストを提案・整理する補助です。決定論的テスト、安全ゲート、"
            "人間承認を置き換えません。利用可能なmodel IDは接続先で再確認してください。"
        ),
        recommendations=items,
    )
