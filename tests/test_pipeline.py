import pytest
from app.db.mongo import get_db
from app.services.pipeline import pipeline_orchestrator
from app.agents.audit_agent import audit_agent
from app.db.attestations import attestation_ledger
from seed_data import seed_database

@pytest.fixture(autouse=True)
def setup_test_db():
    seed_database()

def test_pr_auto_merge_and_attestation():
    result = pipeline_orchestrator.create_pull_request(
        title="Test Ingress Rule",
        author="User A (Dev)",
        target_branch="dev",
        policy_changes=[{
            "name": "Test Ingress 443",
            "port_range": "443",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.0.0/16",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    assert result["status"] == "DEPLOYED"
    assert "attestation" in result["deployment"]
    att_id = result["deployment"]["attestation"]["attestation_id"]
    verif = attestation_ledger.verify_attestation(att_id)
    assert verif["valid"] is True
    assert verif["signature_status"] == "CRYPTOGRAPHICALLY_VERIFIED"

def test_prod_human_gate():
    result = pipeline_orchestrator.create_pull_request(
        title="Prod Route Update",
        author="User B (Lead)",
        target_branch="prod",
        policy_changes=[{
            "name": "Prod Ingress",
            "port_range": "443",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.0.0/16",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    assert result["status"] == "AWAITING_APPROVAL"
    assert result["validation"]["requires_human_approval"] is True

    # Approve
    approved = pipeline_orchestrator.approve_human_gate(result["pr_id"])
    assert approved["status"] == "DEPLOYED"

def test_synthetic_test_failure_triggers_rollback():
    result = pipeline_orchestrator.create_pull_request(
        title="Intentional Fail Rule",
        author="User A (Dev)",
        target_branch="qa",
        policy_changes=[{
            "name": "Broken Gateway Rule (FAIL)",
            "port_range": "9999",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/8",
            "destination_cidr": "192.168.1.1/32",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    assert result["status"] == "ROLLED_BACK"
    assert "rollback" in result["deployment"]
    assert "remediation_pr_id" in result["deployment"]

def test_audit_agent_drift_reconciliation():
    drift_sim = audit_agent.simulate_emergency_manual_change(
        env="prod",
        reason="Test Emergency Bypass"
    )
    assert drift_sim["audit_result"]["unattested_drifts_detected"] >= 1

    # Now verify PR validator agent recalls this context
    next_pr = pipeline_orchestrator.create_pull_request(
        title="Subsequent PR on Prod",
        author="User A (Dev)",
        target_branch="prod",
        policy_changes=[{
            "name": "Normal Rule",
            "port_range": "80",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.0.0/16",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    assert next_pr["status"] == "REJECTED"
    assert any("CONFLICT" in r for r in next_pr["validation"]["reasons"])
