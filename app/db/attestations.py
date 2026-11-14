import hashlib
import hmac
import json
from datetime import datetime
from typing import Dict, Any, Optional
from app.config import settings
from app.db.mongo import get_db

class AttestationLedger:
    def __init__(self):
        self.db = get_db()
        self.signing_secret = settings.SECRET_KEY.encode("utf-8")

    def _calculate_policy_digest(self, policy_data: Any) -> str:
        serialized = json.dumps(policy_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _sign_payload(self, payload: str) -> str:
        return hmac.new(self.signing_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def get_latest_attestation_hash(self) -> str:
        latest = self.db.attestations.find_one(sort=[("timestamp", -1)])
        if latest and "attestation_hash" in latest:
            return latest["attestation_hash"]
        return "GENESIS_ROOT_0000000000000000000000000000000000000000000000000000000000000000"

    def create_attestation(
        self,
        pr_id: str,
        pr_author: str,
        target_env: str,
        commit_hash: str,
        policy_changes: Any,
        test_run_id: str,
        test_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Creates an immutable, cryptographically signed SLSA/in-toto style attestation
        and stores it in the MongoDB attestations collection.
        """
        policy_digest = self._calculate_policy_digest(policy_changes)
        prev_hash = self.get_latest_attestation_hash()
        attestation_id = f"ATT-{target_env.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{pr_id}"

        payload_to_sign = f"{attestation_id}:{policy_digest}:{pr_id}:{pr_author}:{target_env}:{commit_hash}:{test_run_id}:{prev_hash}"
        signature = self._sign_payload(payload_to_sign)
        attestation_hash = hashlib.sha256(f"{payload_to_sign}:{signature}".encode("utf-8")).hexdigest()

        attestation_doc = {
            "attestation_id": attestation_id,
            "schema_version": "https://in-toto.io/Statement/v1",
            "predicate_type": "https://slsa.dev/provenance/v1",
            "subject": {
                "name": f"network-policy-{target_env}",
                "digest": {
                    "sha256": policy_digest
                }
            },
            "predicate": {
                "builder": {
                    "id": "urn:agent:network-deployment-agent-v1"
                },
                "pr_id": pr_id,
                "pr_author": pr_author,
                "target_env": target_env,
                "commit_hash": commit_hash,
                "test_run_id": test_run_id,
                "test_status": "PASSED",
                "test_metrics": test_metrics
            },
            "previous_attestation_hash": prev_hash,
            "signature": signature,
            "attestation_hash": attestation_hash,
            "timestamp": datetime.utcnow()
        }

        self.db.attestations.insert_one(attestation_doc)

        # Log into audit trail
        self.db.audit_logs.insert_one({
            "event_type": "ATTESTATION_CREATED",
            "attestation_id": attestation_id,
            "pr_id": pr_id,
            "author": pr_author,
            "env": target_env,
            "attestation_hash": attestation_hash,
            "timestamp": datetime.utcnow()
        })

        clean_doc = {k: v for k, v in attestation_doc.items() if k != "_id"}
        return clean_doc

    def verify_attestation(self, attestation_id: str) -> Dict[str, Any]:
        """
        Verifies the cryptographic integrity of an attestation in MongoDB.
        """
        record = self.db.attestations.find_one({"attestation_id": attestation_id})
        if not record:
            return {"valid": False, "reason": "Attestation record not found in MongoDB"}

        policy_digest = record["subject"]["digest"]["sha256"]
        pr_id = record["predicate"]["pr_id"]
        pr_author = record["predicate"]["pr_author"]
        target_env = record["predicate"]["target_env"]
        commit_hash = record["predicate"]["commit_hash"]
        test_run_id = record["predicate"]["test_run_id"]
        prev_hash = record.get("previous_attestation_hash", "")
        recorded_sig = record["signature"]

        payload_to_verify = f"{attestation_id}:{policy_digest}:{pr_id}:{pr_author}:{target_env}:{commit_hash}:{test_run_id}:{prev_hash}"
        expected_sig = self._sign_payload(payload_to_verify)

        if hmac.compare_digest(recorded_sig, expected_sig):
            return {
                "valid": True,
                "attestation_id": attestation_id,
                "author": pr_author,
                "environment": target_env,
                "policy_digest": policy_digest,
                "signature_status": "CRYPTOGRAPHICALLY_VERIFIED",
                "chain_hash": record.get("attestation_hash")
            }
        else:
            return {
                "valid": False,
                "attestation_id": attestation_id,
                "reason": "Cryptographic signature mismatch! Artifact may have been tampered with."
            }

attestation_ledger = AttestationLedger()
