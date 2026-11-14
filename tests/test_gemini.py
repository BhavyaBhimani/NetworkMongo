import pytest
import json
from unittest.mock import patch, MagicMock
from app.services.gemini_service import gemini_service
from app.agents.validator_agent import validator_agent
from seed_data import seed_database

@pytest.fixture(autouse=True)
def setup_db():
    seed_database()

def test_gemini_service_fallback_when_unconfigured():
    assert gemini_service.is_configured is False or isinstance(gemini_service.is_configured, bool)
    # When not configured, calling Gemini returns None and does not crash
    with patch.object(gemini_service, 'is_configured', False):
        result = gemini_service.analyze_pr_risk(
            {"target_branch": "dev", "policy_changes": []},
            {"active_emergency_drifts": []}
        )
        assert result is None

def test_validator_with_mocked_gemini():
    mock_llm_response = {
        "approved": True,
        "risk_level": "LOW",
        "reasoning": "Gemini analyzed MongoDB context: No conflicting incidents or port collisions detected.",
        "recommendations": ["Follow least privilege for staging CIDR"]
    }

    with patch.object(gemini_service, 'is_configured', True), \
         patch.object(gemini_service, 'analyze_pr_risk', return_value=mock_llm_response):
        
        pr_data = {
            "pr_id": "PR-GEMINI-TEST",
            "author": "User A (Dev)",
            "target_branch": "dev",
            "policy_changes": [{
                "name": "Standard Ingress",
                "port_range": "443",
                "protocol": "TCP",
                "source_cidr": "10.0.0.0/16",
                "destination_cidr": "10.1.0.0/16",
                "action": "ALLOW"
            }]
        }
        res = validator_agent.validate_pr(pr_data)
        assert res["approved"] is True
        assert res["llm_assisted"] is True
        assert "Gemini" in res["gemini_reasoning"]
        assert len(res["gemini_recommendations"]) == 1
