import os
import sys
from pathlib import Path

# Ensure backend and root paths are in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

import time
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from model.model_loader import ModelSingletonManager

def test_singleton_loads_lora():
    """Verify that the model loader singleton initializes and reports LoRA adapter loaded."""
    manager = ModelSingletonManager()
    model, tokenizer, adapter_status, load_time = manager.get_instance()
    assert model is not None
    assert tokenizer is not None
    assert adapter_status == "LOADED"
    print("\n--- MODEL SINGLETON METADATA ---")
    print(f"Adapter Status: {adapter_status}")
    print(f"Model Load Time: {load_time}s")

def test_api_analyze_e2e_lora():
    """Verify that POST /api/analyze executes the full flow and returns valid schema with LoRA."""
    client = TestClient(app)
    
    payload = {
        "question": "ECS task in cluster ecs-cluster-001 continuously transitions PENDING to STOPPED with error Essential container in task exited with code 1.",
        "cloud_context": {
            "service": "ECS",
            "cluster_name": "ecs-cluster-001",
            "task_definition": "app-task:4",
            "resources": {
                "ecs_clusters": ["ecs-cluster-001"],
                "tasks": [{"task_arn": "arn:aws:ecs:us-east-1:123456789012:task/ecs-cluster-001/abc123def", "status": "STOPPED", "exit_code": 1}]
            },
            "logs": [
                "Essential container in task exited with code 1.",
                "Cannot connect to Redis host redis.internal:6379."
            ]
        },
        "collect_live_data": False
    }

    start_time = time.time()
    response = client.post("/api/analyze", json=payload)
    elapsed = time.time() - start_time
    
    assert response.status_code == 200, f"Error: {response.status_code} - {response.text}"
    data = response.json()
    
    print("\n--- END-TO-END POST /api/analyze RESULT ---")
    print(f"Elapsed Time: {elapsed:.2f}s")
    print(json.dumps(data, indent=2))
    
    # Required production fields under diagnosis
    diagnosis = data.get("diagnosis", data)
    assert "problem" in diagnosis
    assert "probable_root_cause" in diagnosis
    assert "evidence" in diagnosis and isinstance(diagnosis["evidence"], list)
    assert len(diagnosis["evidence"]) >= 1
    assert "impact" in diagnosis
    assert "recommendation" in diagnosis
    assert "confidence" in diagnosis and isinstance(diagnosis["confidence"], (int, float))
    
    print("\nE2E Schema Validation: PASSED")

if __name__ == "__main__":
    test_singleton_loads_lora()
    test_api_analyze_e2e_lora()
