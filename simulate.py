import time
import json
from app.db.mongo import get_db
from app.services.pipeline import pipeline_orchestrator
from app.agents.audit_agent import audit_agent
from app.db.attestations import attestation_ledger
from app.db.memory import memory_manager
from seed_data import seed_database

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print("\n" + "="*70)
    print(f"{BOLD}{CYAN}>>> {title}{RESET}")
    print("="*70)

def run_simulation():
    print(f"\n{BOLD}{GREEN}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}  NETTRACE AI - COMPREHENSIVE MULTI-AGENT SIMULATION SUITE          {RESET}")
    print(f"{BOLD}{GREEN}  Hackathon: MongoDB Toronto - Agents in Context                     {RESET}")
    print(f"{BOLD}{GREEN}======================================================================{RESET}")

    # 1. Reset Database & Seed Initial Memory
    print_header("INITIALIZING DATABASE & SEEDING CONTEXT MEMORY")
    seed_database()
    time.sleep(1)

    # -------------------------------------------------------------
    # Scenario 1: Standard Non-Prod Flow (User A -> DEV)
    # -------------------------------------------------------------
    print_header("SCENARIO 1: Standard Developer PR on 'dev' (Auto-Merge & Attest)")
    print(f"{BOLD}User A (Dev){RESET} submits PR to enable analytics ingress on port 443.")

    pr1 = pipeline_orchestrator.create_pull_request(
        title="Enable Analytics Ingress on Telemetry Port",
        author="User A (Dev)",
        target_branch="dev",
        source_branch="feature/analytics-ingress",
        policy_changes=[{
            "name": "Analytics Ingress Service",
            "port_range": "443",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.1.5.0/24",
            "action": "ALLOW",
            "risk_level": "LOW"
        }],
        auto_run=True
    )

    print(f"\n{BOLD}[1. PR Validation Agent]{RESET}")
    print(f"Status: {GREEN}{pr1['status']}{RESET}")
    print(f"Risk Level: {pr1['validation']['risk_level']}")
    for note in pr1['validation']['context_notes']:
        print(f"  • {note}")

    print(f"\n{BOLD}[2. Deployment & Synthetic Testing]{RESET}")
    deploy_info = pr1.get("deployment", {})
    test_info = deploy_info.get("tests", {})
    attest_info = deploy_info.get("attestation", {})
    print(f"Synthetic Tests: {GREEN}{test_info.get('passed_checks')}/{test_info.get('total_checks')} Checks Passed{RESET}")
    print(f"Average Probe Latency: {test_info.get('latency_avg_ms')} ms")
    print(f"SLSA Attestation ID: {CYAN}{attest_info.get('attestation_id')}{RESET}")
    print(f"Attestation Signature: {attest_info.get('signature', '')[:24]}...")

    # Verify Attestation
    verif = attestation_ledger.verify_attestation(attest_info.get('attestation_id'))
    print(f"Cryptographic Chain Verification: {GREEN}{verif.get('signature_status')}{RESET}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # Scenario 2: Sensitive Prod Flow (User B -> PROD)
    # -------------------------------------------------------------
    print_header("SCENARIO 2: Protected PR on 'prod' (Human Gate -> Sign-off)")
    print(f"{BOLD}User B (Lead){RESET} submits PR to route payment gateway transit on port 8443.")

    pr2 = pipeline_orchestrator.create_pull_request(
        title="PCI-DSS Payment Gateway Inter-VPC Transit",
        author="User B (Lead)",
        target_branch="prod",
        source_branch="infra/payment-transit",
        policy_changes=[{
            "name": "PCI Transit Inter-VPC",
            "port_range": "8443",
            "protocol": "TCP",
            "source_cidr": "10.10.0.0/16",
            "destination_cidr": "10.20.0.0/16",
            "action": "ALLOW",
            "risk_level": "MEDIUM"
        }],
        auto_run=True
    )

    print(f"\n{BOLD}[1. PR Validation Agent]{RESET}")
    print(f"Status: {YELLOW}{pr2['status']}{RESET}")
    print(f"Human Approval Required: {BOLD}{pr2['validation']['requires_human_approval']}{RESET}")
    for note in pr2['validation']['context_notes']:
        print(f"  • {note}")

    print(f"\n{BOLD}[2. Human-In-The-Loop Sign-Off]{RESET}")
    print(f"Network Team Manager & Lead reviewing PR {pr2['pr_id']}...")
    time.sleep(1)
    approved_pr2 = pipeline_orchestrator.approve_human_gate(pr2['pr_id'])
    print(f"Approval Granted! Final Status: {GREEN}{approved_pr2['status']}{RESET}")
    print(f"Attestation: {CYAN}{approved_pr2['deployment']['attestation']['attestation_id']}{RESET}")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # Scenario 3: Test Failure & Automated Rollback
    # -------------------------------------------------------------
    print_header("SCENARIO 3: Flawed Policy Deployed (Auto-Rollback & Auto-Revert PR)")
    print(f"{BOLD}User A (Dev){RESET} submits experimental routing rule with buffer isolation flaw.")

    pr3 = pipeline_orchestrator.create_pull_request(
        title="Experimental High-Throughput Route",
        author="User A (Dev)",
        target_branch="qa",
        source_branch="experiment/broken-route",
        policy_changes=[{
            "name": "Buffer Overload Route (Simulated Fail)",
            "port_range": "9999",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/8",
            "destination_cidr": "192.168.1.1/32",
            "action": "ALLOW",
            "risk_level": "HIGH"
        }],
        auto_run=True
    )

    print(f"\n{BOLD}[1. Synthetic Tests Failed!]{RESET}")
    dep3 = pr3.get("deployment", {})
    test3 = dep3.get("tests", {})
    print(f"Failed Checks: {RED}{test3.get('failed_checks')} probe(s) failed with packet drop / isolation leak!{RESET}")

    print(f"\n{BOLD}[2. Autonomous Rollback & Remediation]{RESET}")
    print(f"Rollback Result: {YELLOW}{dep3.get('rollback', {}).get('message')}{RESET}")
    print(f"Auto-Revert PR Created & Merged: {CYAN}{dep3.get('remediation_pr_id')}{RESET}")
    print(f"Episode Logged into MongoDB Episodic Memory for future context.")

    time.sleep(1.5)

    # -------------------------------------------------------------
    # Scenario 4: Midnight Emergency Drift & Memory Sync
    # -------------------------------------------------------------
    print_header("SCENARIO 4: Midnight Emergency Hotfix (Out-of-Band Drift Reconciliation)")
    print("At 3:00 AM, an engineer makes an out-of-band manual firewall change directly in cloud console.")

    drift_sim = audit_agent.simulate_emergency_manual_change(
        env="prod",
        reason="Emergency database replica connection bypass during outage"
    )

    audit_res = drift_sim["audit_result"]
    print(f"\n{BOLD}[Audit Agent Detection]{RESET}")
    print(f"Unattested Manual Changes Detected: {RED}{audit_res.get('unattested_drifts_detected')}{RESET}")
    for d in audit_res.get("drifts", []):
        print(f"  • {d.get('incident_id')}: {d.get('details')}")

    print(f"\n{BOLD}[MongoDB Agentic Memory Updated]{RESET}")
    print(f"Incident ingested into episodic & semantic memory to prevent cold starts.")

    # Now verify that subsequent PR immediately recalls this incident!
    print(f"\n{BOLD}[Subsequent PR Test - Zero Cold Start!]{RESET}")
    next_pr = pipeline_orchestrator.create_pull_request(
        title="Routine Database Port Maintenance",
        author="User A (Dev)",
        target_branch="prod",
        source_branch="maint/db-port",
        policy_changes=[{
            "name": "Database Port 8080 Rule",
            "port_range": "8080",
            "protocol": "TCP",
            "source_cidr": "10.0.0.0/16",
            "destination_cidr": "10.0.5.20/32",
            "action": "ALLOW"
        }],
        auto_run=True
    )

    print(f"Next PR Status: {RED}{next_pr['status']}{RESET}")
    print(f"Reasons flagged by PR Validator Agent:")
    for reason in next_pr['validation']['reasons']:
        print(f"  {RED}⚠ {reason}{RESET}")

    print("\n" + "="*70)
    print(f"{BOLD}{GREEN}ALL 4 HACKATHON SCENARIOS SUCCESSFULLY DEMONSTRATED!{RESET}")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_simulation()
