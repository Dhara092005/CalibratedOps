import io
import json
import os
from unittest.mock import patch
import unittest

from calibrated_ops.agents import AgentError, openai_proposal, validate_proposal


class AgentTests(unittest.TestCase):
    def test_invalid_action_and_nonfinite_confidence_are_blocked(self):
        for action, confidence in (("shell_command", 0.9), ("monitor", float("nan")), ("monitor", True), ("monitor", 1.1)):
            with self.assertRaises(AgentError):
                validate_proposal(dict(action=action, confidence=confidence, explanation="Evidence"))

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_missing_key_has_clear_error(self):
        with self.assertRaisesRegex(AgentError, "not configured"):
            openai_proposal("Evidence", "low")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret", "OPENAI_MODEL": "test-model"})
    def test_valid_structured_response_and_no_label_leakage(self):
        payload = dict(status="completed", output=[dict(type="message", content=[dict(type="output_text", text=json.dumps(dict(action="monitor", confidence=0.7, explanation="Healthy checks.")))])])
        captured = []
        def mock_request(req, timeout):
            captured.append(json.loads(req.data))
            return io.BytesIO(json.dumps(payload).encode())
        with patch("calibrated_ops.agents.request.urlopen", side_effect=mock_request):
            result = openai_proposal("Healthy checks", "low")
        self.assertEqual(result["action"], "monitor")
        self.assertEqual(result["model"], "test-model")
        self.assertEqual(captured[0]["store"], False)
        incident = json.loads(captured[0]["input"][1]["content"])
        self.assertEqual(set(incident), {"evidence", "impact_risk"})
        self.assertTrue(captured[0]["text"]["format"]["strict"])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-secret"})
    def test_refusal_and_incomplete_output_are_blocked(self):
        for payload in (None, dict(status="incomplete"), dict(status="completed", output=None), dict(status="completed", output=[dict(type="message", content=[dict(type="refusal")])])):
            with patch("calibrated_ops.agents.request.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())):
                with self.assertRaises(AgentError):
                    openai_proposal("Evidence", "high")
