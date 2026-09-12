"""
CloudOps LLM - Evaluation Script CLI
Phase 5B: Executes evaluation suite on data/processed/test.jsonl and exports output artifacts.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add project root directory to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from model.inference import load_adapter_model
from model.evaluate import CloudOpsEvaluator


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("evaluate_cloudops")


def main():
    logger.info("==================================================")
    logger.info("CLOUDOPS LLM — MODEL EVALUATION RUNNER")
    logger.info("==================================================")

    model, tokenizer, is_peft = load_adapter_model()
    logger.info(f"Loaded evaluation engine. PEFT Adapter active: {is_peft}")

    eval_limit = int(os.getenv("EVAL_LIMIT", "15"))
    logger.info(f"Running evaluation on {eval_limit} test cases...")
    evaluator = CloudOpsEvaluator(model=model, tokenizer=tokenizer)
    summary, results = evaluator.evaluate(limit=eval_limit)

    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY RESULTS")
    print("=" * 50)
    print(json.dumps(summary, indent=2))
    print("=" * 50)

    print(f"\nEvaluation completed over {summary.get('test_count', 0)} test examples.")
    print(f"Valid JSON Rate:           {summary.get('valid_json_percentage', 0.0)}%")
    print(f"Schema Validity Rate:      {summary.get('schema_validity_percentage', 0.0)}%")
    print(f"Confidence Validity Rate:  {summary.get('confidence_validity_percentage', 0.0)}%")
    print(f"Evidence Grounding Rate:   {summary.get('evidence_grounding_percentage', 0.0)}%")
    print(f"Advisory Safety Pass Rate: {summary.get('safety_check_pass_percentage', 0.0)}%")
    print(f"Uncertainty Pass Rate:     {summary.get('uncertainty_behavior_pass_percentage', 0.0)}%")

    summary_file = os.path.join("outputs", "evaluation", "evaluation_summary.json")
    print(f"\nSaved evaluation summary artifact to: {os.path.abspath(summary_file)}")


if __name__ == "__main__":
    main()
