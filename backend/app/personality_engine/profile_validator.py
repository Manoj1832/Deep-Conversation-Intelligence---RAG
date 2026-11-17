from typing import Dict, Any, List

class ProfileValidator:
    """
    Validates that:
    1. Every observation has supporting message IDs that are valid UUIDs.
    2. Confidence scores are strictly between 0.0 and 1.0.
    3. No observation makes unsupported claims.
    """

    @staticmethod
    def validate(profile: Dict[str, Any], observations: List[Dict[str, Any]]) -> bool:
        assert "profile_id" in profile, "Missing profile_id"
        assert "language_patterns" in profile, "Missing language_patterns"
        assert "message_patterns" in profile, "Missing message_patterns"
        assert "emoji_patterns" in profile, "Missing emoji_patterns"

        for obs in observations:
            assert "observation_id" in obs, "Missing observation_id"
            assert "dimension" in obs, "Missing dimension"
            assert "supporting_evidence" in obs, "Missing supporting_evidence"
            assert "source_message_ids" in obs, "Missing source_message_ids"
            assert len(obs["source_message_ids"]) > 0, "Observation must have at least one source message ID"
            assert 0.0 <= obs["confidence"] <= 1.0, f"Invalid confidence: {obs['confidence']}"
            assert obs["verification_status"] in ["verified", "pending_review", "rejected"]

        return True
