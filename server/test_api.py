"""
test_api.py — Integration tests for the FastAPI layer.

Run:
    python -m unittest test_api -v
"""

from __future__ import annotations

import textwrap
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from engine.orchestrator import EngineError

client = TestClient(app)


# =============================================================================
# Test: Health Probes
# =============================================================================

class TestHealth(unittest.TestCase):
    def test_health_check(self) -> None:
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "code-vision"})

    def test_version_check(self) -> None:
        response = client.get("/version")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"version": "1.0.0"})


# =============================================================================
# Test: Validation (Pydantic / FastAPI)
# =============================================================================

class TestValidation(unittest.TestCase):
    def test_missing_code_payload(self) -> None:
        response = client.post("/api/v1/visualize", json={})
        self.assertEqual(response.status_code, 422)  # FastAPI validation error

    def test_empty_code_payload(self) -> None:
        response = client.post("/api/v1/visualize", json={"code": ""})
        self.assertEqual(response.status_code, 422)  # min_length=1

    def test_invalid_data_type(self) -> None:
        response = client.post("/api/v1/visualize", json={"code": 123})
        self.assertEqual(response.status_code, 422)


# =============================================================================
# Test: Success Scenarios (Integration)
# =============================================================================

class TestVisualizeIntegration(unittest.TestCase):
    def test_visualize_success(self) -> None:
        """Integration test verifying a full valid request through the API."""
        source = textwrap.dedent("""\
            def add(a: int, b: int) -> int:
                return a + b
        """)
        
        response = client.post("/api/v1/visualize", json={"code": source})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        if not data["success"]:
            self.fail(f"Visualize failed: {data.get('error')}")
        self.assertTrue(data["success"])
        self.assertIn("events", data)
        self.assertIn("frames", data)
        self.assertIsInstance(data["output"], str)
        self.assertIsNone(data["error"])
        
        # Verify events were captured
        self.assertGreater(data["total_events"], 0)


# =============================================================================
# Test: Error Scenarios & Exception Handlers
# =============================================================================

class TestErrorHandling(unittest.TestCase):
    def test_engine_error_mapped_to_422(self) -> None:
        """Verify that an EngineError raised inside the dependency translates to HTTP 422."""
        
        # We mock the engine dependency to force an EngineError
        def override_get_engine():
            mock_engine = MagicMock()
            mock_engine.visualize.side_effect = EngineError("Mocked failure", stage="analyzer")
            return mock_engine
            
        from api.dependencies import get_engine
        app.dependency_overrides[get_engine] = override_get_engine
        
        try:
            response = client.post("/api/v1/visualize", json={"code": "dummy code"})
            
            self.assertEqual(response.status_code, 422)
            data = response.json()
            
            self.assertFalse(data["success"])
            self.assertEqual(data["error"], "Mocked failure")
            self.assertEqual(data["error_type"], "EngineError")
            self.assertEqual(data["stage"], "analyzer")
        finally:
            # Clear overrides so other tests aren't affected
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
