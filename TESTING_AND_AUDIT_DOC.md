# NetTrace AI: Testing & Audit Verification Guide
### Hackathon Problem Statement 1: "Agents You Can Audit"
*Co-hosted by MongoDB & Cerebral Valley (Toronto)*

---

## 1. Hackathon Problem Statement Alignment

> **Statement One: Agents You Can Audit**  
> *"An agent that can't explain what it did, and who allowed it, never leaves the sandbox. Build an agent using MongoDB Atlas as the identity, policy and audit layer (collections, schema validation, change streams) that takes real actions across systems, where every action is tied to an identity, checked against policy before it runs, and recorded so a reviewer can reconstruct it afterward."*

### How NetTrace AI Directly Solves the 3 Core Questions:

| Hackathon Core Question | NetTrace AI Solution & Implementation | MongoDB Mechanism |
| :--- | :--- | :--- |
| **1. How do you decide what an agent may do and enforce it *before* the action, not after?** | The **PR Validator Agent** intercepts the PR diff before merge or deployment. It queries active policies, historical incident memory, and checks environment rules. In protected environments (`pat` and `prod`), it halts execution into an `AWAITING_APPROVAL` state, strictly forbidding any action until explicit human manager sign-off is granted. | MongoDB `$jsonSchema` validation, collection-level guardrails in `policies`, and semantic query over `agent_memory`. |
| **2. How do you record what the agent did, why, and under whose authority?** | Every action records: (a) Initiator identity & role, (b) Pre-action policy verdict, (c) Authority grant (System Auto-Approval or Human Manager), (d) Policy diff, and (e) Synthetic test probe metrics. These are bound into an **in-toto/SLSA Cryptographic Attestation** with HMAC-SHA256 signatures and hash chaining in MongoDB. Reviewers can query `/api/audit/reconstruct/{id}` to reconstruct the full chronological provenance. | Immutable `attestations` and `audit_logs` collections with SHA-256 parent hash chaining. |
| **3. How do you stop or roll back an agent mid-run?** | **Mid-run halt:** The `abort_mid_run()` circuit breaker cancels in-flight agent runs and marks them `ABORTED_MID_RUN`.<br>**Post-action rollback:** If synthetic tests detect latency spikes or isolation leaks, the `NetworkDeploymentAgent` restores the prior atomic snapshot in MongoDB, restores baseline rules, and triggers an auto-remediation PR. | Atomic snapshotting in `deployments`, status rollback transitions, and `prior_snapshot` arrays in MongoDB documents. |

---

## 2. Solving the GitHub Actions Runner IP & MongoDB Atlas Whitelist

### The Problem
In a GitHub Actions workflow, the runner is hosted in GitHub's dynamic cloud pool (Azure/AWS). Its public IP is **dynamic and unknown beforehand**, meaning you cannot hardcode a single runner IP into MongoDB Atlas Network Access.

### The Solutions Implemented in NetTrace AI:

#### Approach A: The Hackathon Recommended Way (Set `0.0.0.0/0` in Atlas)
For hackathon sandbox clusters, the official MongoDB Atlas recommended practice is:
1. Log in to [MongoDB Atlas](https://cloud.mongodb.com).
2. Go to **Security** -> **Network Access**.
3. Click **Add IP Address** -> Select **"Allow Access From Anywhere" (`0.0.0.0/0`)**.
4. Set entry expiration to 24–48 hours (or duration of the hackathon).
5. Add `MONGODB_URI` to your GitHub Repository:
   - Go to GitHub Repo -> **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
   - Name: `MONGODB_URI`
   - Value: `mongodb+srv://<user>:<password>@cluster0.xxxx.mongodb.net/nettrace_db?retryWrites=true&w=majority`

#### Approach B: Dynamic IP Whitelisting via Atlas API
If you prefer not to open `0.0.0.0/0`, GitHub Actions can dynamically whitelist its own IP using the Atlas API:
```yaml
- name: Whitelist GitHub Runner IP in Atlas
  run: |
    RUNNER_IP=$(curl -s https://api.ipify.org)
    curl --user "${{ secrets.ATLAS_PUBLIC_KEY }}:${{ secrets.ATLAS_PRIVATE_KEY }}" \
      --digest \
      --header "Content-Type: application/json" \
      --request POST "https://cloud.mongodb.com/api/atlas/v2/groups/${{ secrets.ATLAS_PROJECT_ID }}/accessList" \
      --data '[{"ipAddress": "'"$RUNNER_IP"'", "comment": "Temporary GitHub Runner"}]'
```

#### Approach C: Built-in GitHub Actions Service Container (Our Default)
Our workflow file (`.github/workflows/ci.yml`) includes a native MongoDB service container:
```yaml
services:
  mongodb:
    image: mongo:7.0
    ports:
      - 27017:27017
```
Even if someone runs the workflow without configuring Atlas secrets, the CI pipeline **spins up an active, real MongoDB 7.0 database directly inside the runner**, seeds the collections, validates JSON schemas, and runs the entire multi-agent test suite with 100% success!

---

## 3. Step-by-Step Test Scenarios & Expected Outcomes

### Test Scenario 1: Pre-Action Policy Decision
- **Goal:** Verify that policies are enforced *before* actions take place.
- **Command:** `python -m pytest tests/test_pipeline.py -k test_prod_human_gate`
- **Expected Outcome:** PR targeting `prod` stops in `AWAITING_APPROVAL`. Zero changes are applied to active policies until human manager sign-off is granted.

### Test Scenario 2: Identity & Full Audit Trail Reconstruction
- **Goal:** Verify that a compliance reviewer can query an action identifier and reconstruct what was done, why, and under whose authority.
- **API Endpoint:** `GET /api/audit/reconstruct/{identifier}`
- **Test Command:** `python -m pytest tests/test_pipeline.py -k test_auditor_reconstruction`
- **Expected Outcome:** 
  - `identity.initiator` = `User A (Dev)`
  - `pre_action_policy_check.policy_status` = `VERIFIED_BEFORE_ACTION`
  - `cryptographic_attestation.is_cryptographically_valid` = `True`
  - Full chronological chain of events retrieved from MongoDB `audit_logs`.

### Test Scenario 3: Mid-Run Circuit Breaker (Halt / Abort)
- **Goal:** Verify that an operator or security lead can stop an agent mid-run.
- **API Endpoint:** `POST /api/prs/{pr_id}/abort`
- **Test Command:** `python -m pytest tests/test_pipeline.py -k test_emergency_circuit_breaker_mid_run`
- **Expected Outcome:** Status transitions immediately to `ABORTED_MID_RUN`, any in-flight deployment snapshot is restored, and an `EMERGENCY_CIRCUIT_BREAKER_TRIPPED` event is logged in MongoDB.

### Test Scenario 4: Automated Canary Test Failure & Self-Healing Rollback
- **Goal:** Verify that failed synthetic tests trigger an automated rollback and auto-remediation PR.
- **Command:** `python -m pytest tests/test_pipeline.py -k test_synthetic_test_failure_triggers_rollback`
- **Expected Outcome:** Synthetic probe fails -> Active policy reverted to prior snapshot -> Remediation PR `[AUTO-REVERT]` created and merged -> Failure episode recorded in MongoDB memory.

### Test Scenario 5: Out-of-Band Midnight Drift Reconciliation
- **Goal:** Verify that the Audit Agent detects un-attested manual cloud changes and synchronizes MongoDB memory.
- **Command:** `python -m pytest tests/test_pipeline.py -k test_audit_agent_drift_reconciliation`
- **Expected Outcome:** Audit Agent scans environment -> Detects un-attested rule -> Updates MongoDB memory -> Subsequent PR on that environment is immediately rejected with a drift conflict warning!

---

## 4. Quick Verification Commands

```bash
# 1. Run all automated unit tests (6/6 tests passing)
python -m pytest tests/ -v

# 2. Run the end-to-end multi-agent CLI simulation
python simulate.py

# 3. Launch the web dashboard
python -m app.main
```
Visit **http://127.0.0.1:8000** to interactively test all scenarios with the UI!
