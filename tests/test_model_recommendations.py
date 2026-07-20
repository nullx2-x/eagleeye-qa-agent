from fastapi.testclient import TestClient

from app.main import app
from app.model_recommendations import catalog


def test_balanced_catalog_has_a_stable_default_and_sources() -> None:
    result = catalog("balanced")

    assert result.defaultModel == "gpt-5.6-terra"
    assert result.verifiedAt == "2026-07-16"
    assert result.recommendations
    assert all(item.sourceUrl.startswith("https://") for item in result.recommendations)
    assert all(item.stability == "stable" for item in result.recommendations)


def test_recommendation_api_filters_workload_without_credentials() -> None:
    response = TestClient(app).get(
        "/api/v1/ai/model-recommendations",
        params={"workload": "local_private"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"]
    assert {item["workload"] for item in payload["recommendations"]} == {"local_private"}
    assert "apiKey" not in response.text
