import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.preprocessing import preprocess_cloud_context
from app.services.cloudops_analyzer import CloudOpsAnalyzer
from model.inference import _generate_synthetic_heuristic_response


class TestCpuRcaPipeline(unittest.TestCase):
    def setUp(self):
        self.analyzer = CloudOpsAnalyzer(
            rag_query_fn=lambda q: [],
            model_runner=lambda q, c, p: _generate_synthetic_heuristic_response(q, c)
        )

    def test_1_normal_cpu_no_cpu_root_cause(self):
        """Case 1: Normal CPU (15%) -> no CPU root cause."""
        raw_data = {
            "ec2": [{"instance_id": "i-cpu01", "state": "running"}],
            "cloudwatch": [
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-cpu01",
                    "average": 15.0,
                    "maximum": 18.0,
                    "unit": "Percent",
                    "timestamp": "2026-09-16T01:00:00Z"
                }
            ]
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="Why is CPU high on instance i-cpu01?",
            cloud_context=context,
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertIn("normal", diag.probable_root_cause.lower())
        self.assertNotIn("high cpu utilization", diag.probable_root_cause.lower())
        self.assertGreaterEqual(diag.confidence, 0.70)

    def test_2_cpu_above_80_anomaly_detected(self):
        """Case 2: CPU > 80% (85%) -> CPU anomaly detected."""
        raw_data = {
            "ec2": [{"instance_id": "i-cpu02", "state": "running"}],
            "cloudwatch": [
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-cpu02",
                    "average": 82.0,
                    "maximum": 85.0,
                    "unit": "Percent",
                    "timestamp": "2026-09-16T01:00:00Z"
                }
            ]
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="High CPU utilization spike on EC2 instance i-cpu02",
            cloud_context=context,
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertTrue("85" in diag.probable_root_cause or "high cpu" in diag.probable_root_cause.lower())
        self.assertTrue(any("85" in ev or "high cpu" in ev.lower() for ev in diag.evidence))
        self.assertGreaterEqual(diag.confidence, 0.85)

    def test_3_cpu_95_to_100_saturation_root_cause(self):
        """Case 3: CPU ~95–100% (98.5%) + service degradation -> CPU saturation is strong root cause."""
        raw_data = {
            "ec2": [{"instance_id": "i-cpu03", "state": "running"}],
            "cloudwatch": [
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-cpu03",
                    "average": 97.0,
                    "maximum": 98.5,
                    "unit": "Percent",
                    "timestamp": "2026-09-16T01:00:00Z"
                }
            ]
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="Why is my web server unresponsive and timing out?",
            cloud_context=context,
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertTrue("high cpu" in diag.probable_root_cause.lower() or "98.5" in diag.probable_root_cause)
        self.assertTrue(any("98.5" in ev for ev in diag.evidence))
        self.assertGreaterEqual(diag.confidence, 0.85)

    def test_4_cpu_normal_http_failure_no_cpu_blame(self):
        """Case 4: CPU normal (10%) + HTTP port 80 blocked -> Security Group diagnosed, not CPU."""
        raw_data = {
            "ec2": [{"instance_id": "i-cpu04", "state": "running", "security_group_ids": ["sg-block80"]}],
            "security_groups": [{
                "group_id": "sg-block80",
                "name": "web-sg",
                "inbound_rules": [{"protocol": "tcp", "from_port": 443, "to_port": 443, "sources": ["0.0.0.0/0"]}]
            }],
            "cloudwatch": [
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-cpu04",
                    "average": 8.0,
                    "maximum": 10.0,
                    "unit": "Percent"
                }
            ]
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="Why is my website unreachable over HTTP on port 80?",
            cloud_context=context,
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertTrue("80" in diag.probable_root_cause or "security group" in diag.probable_root_cause.lower())
        self.assertNotIn("high cpu", diag.probable_root_cause.lower())
        self.assertGreaterEqual(diag.confidence, 0.80)

    def test_5_missing_telemetry_reported(self):
        """Case 5: Missing CPU telemetry -> clearly report missing telemetry."""
        raw_data = {
            "ec2": [{"instance_id": "i-cpu05", "state": "running"}],
            "cloudwatch": []
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="Why is CPU high on instance i-cpu05?",
            cloud_context=context,
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertTrue("unavailable" in diag.probable_root_cause.lower() or "missing" in diag.probable_root_cause.lower() or "insufficient" in diag.probable_root_cause.lower())
        self.assertLessEqual(diag.confidence, 0.50)

    def test_6_wrong_resource_id_isolation(self):
        """Case 6: Wrong Resource ID -> do not use another resource's CPU data."""
        raw_data = {
            "ec2": [
                {"instance_id": "i-highcpu", "state": "running"},
                {"instance_id": "i-normalcpu", "state": "running"}
            ],
            "cloudwatch": [
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-highcpu",
                    "average": 99.0,
                    "maximum": 100.0,
                    "unit": "Percent"
                },
                {
                    "metric_name": "CPUUtilization",
                    "resource_id": "i-normalcpu",
                    "average": 5.0,
                    "maximum": 5.0,
                    "unit": "Percent"
                }
            ]
        }
        context = preprocess_cloud_context(raw_data)
        response = self.analyzer.analyze(
            question="Check CPU status for instance i-normalcpu",
            cloud_context=context,
            resource_id="i-normalcpu",
            collect_live_data=False
        )
        diag = response.diagnosis
        self.assertNotIn("100", diag.probable_root_cause)
        self.assertNotIn("high cpu utilization (100", diag.probable_root_cause.lower())
        self.assertIn("normal", diag.probable_root_cause.lower())


if __name__ == "__main__":
    unittest.main()
