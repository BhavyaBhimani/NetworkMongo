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

def test_auditor_reconstruction():
    # Deploy a valid PR first
    result = pipeline_orchestrator.create_pull_request(
        title="Reconstructible Ingress",
        author="User A (Dev)",
        target_branch="dev",
        policy_changes=[{
            "name": "Audit Test Rule",
            "port_range": "443",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.0.0/16",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    pr_id = result["pr_id"]

    # Reconstruct as an auditor
    recon = attestation_ledger.reconstruct_audit_trail(pr_id)
    assert recon["found"] is True
    assert recon["identity"]["initiator"] == "User A (Dev)"
    assert recon["pre_action_policy_check"]["policy_status"] == "VERIFIED_BEFORE_ACTION"
    assert recon["action_executed"]["target_environment"] == "dev"
    assert recon["cryptographic_attestation"]["is_cryptographically_valid"] is True
    assert len(recon["chronological_event_log"]) > 0

def test_emergency_circuit_breaker_mid_run():
    # Create PR on protected branch prod
    result = pipeline_orchestrator.create_pull_request(
        title="Halted Prod Change",
        author="User B (Lead)",
        target_branch="prod",
        policy_changes=[{
            "name": "Sensitive Rule",
            "port_range": "8443",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.0.0/16",
            "action": "ALLOW"
        }],
        auto_run=True
    )
    pr_id = result["pr_id"]
    assert result["status"] == "AWAITING_APPROVAL"

    # Trip the circuit breaker mid-run
    abort_res = pipeline_orchestrator.abort_mid_run(pr_id, reason="Security lead flagged suspicious commit", aborted_by="Security Lead")
    assert abort_res["status"] == "ABORTED_MID_RUN"

    # Check that database reflects aborted status
    db = get_db()
    updated = db.pull_requests.find_one({"pr_id": pr_id})
    assert updated["status"] == "ABORTED_MID_RUN"
    assert updated["abort_reason"] == "Security lead flagged suspicious commit"
