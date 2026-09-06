"""Contract checks for the fork's synthetic-only test environment."""

import json
import sys
import unittest
from pathlib import Path

import yaml

FORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FORK))
from mock_suggestions import PROPOSAL  # noqa: E402
from mock_suggestions import completion  # noqa: E402


class LabTests(unittest.TestCase):
    def test_native_tool_call(self):
        result = completion(
            {
                "model": "synthetic-fixture",
                "tools": [
                    {
                        "function": {"name": "DocumentClassifierSchema"},
                    },
                ],
            },
        )
        tool = result["choices"][0]["message"]["tool_calls"][0]
        self.assertEqual(json.loads(tool["function"]["arguments"]), PROPOSAL)

    def test_other_models_are_rejected(self):
        with self.assertRaises(ValueError):
            completion({"model": "real-provider"})

    def test_missing_tool_is_rejected(self):
        with self.assertRaises(ValueError):
            completion({"model": "synthetic-fixture"})

    def test_network_and_volume_boundary(self):
        config = yaml.safe_load((FORK / "compose.yaml").read_text())
        self.assertTrue(config["networks"]["lab"]["internal"])
        self.assertEqual(set(config["services"]), {"paperless", "db", "broker", "mock"})
        for name, service in config["services"].items():
            self.assertEqual(service["networks"], ["lab"])
            self.assertNotIn("network_mode", service)
            self.assertNotIn("env_file", service)
            self.assertNotIn("extra_hosts", service)
            self.assertFalse(service.get("privileged", False))
            ports = ["127.0.0.1:18080:8000"] if name == "paperless" else []
            self.assertEqual(service.get("ports", []), ports)
            for volume in service.get("volumes", []):
                source = volume.split(":")[0]
                if name == "mock":
                    self.assertEqual(
                        volume,
                        "./mock_suggestions.py:/mock/mock_suggestions.py:ro",
                    )
                else:
                    self.assertIn(source, config["volumes"])

    def test_fixed_smoke_target_and_fixture(self):
        import smoke

        self.assertEqual(smoke.BASE_URL, "http://127.0.0.1:18080")
        self.assertEqual(
            smoke.SAMPLE.relative_to(FORK.parent).as_posix(),
            "src/documents/tests/samples/simple.pdf",
        )


if __name__ == "__main__":
    unittest.main()
