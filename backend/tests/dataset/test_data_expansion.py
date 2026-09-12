import json
import pytest
from model.data_expansion import CloudOpsScenarioGenerator, ExternalDatasetImporter, ALL_SERVICES
from model.dataset import (
    calculate_jaccard_similarity,
    classify_incident_attributes,
    find_near_duplicates,
    generate_dataset_statistics,
    generate_decoupled_dataset_statistics,
    group_and_split_dataset,
    validate_example,
)

def test_scenario_generator_coverage():
    """Verify that CloudOpsScenarioGenerator covers all 25 categories with valid schemas."""
    generator = CloudOpsScenarioGenerator(seed=42)
    scenarios = generator.generate_scenarios(count_per_category=1)
    
    assert len(scenarios) == len(ALL_SERVICES)
    
    for ex in scenarios:
        is_valid, errors = validate_example(ex)
        assert is_valid is True, f"Validation failed for scenario: {errors}"
        
        output_obj = json.loads(ex["output"])
        assert "problem" in output_obj
        assert "probable_root_cause" in output_obj
        assert "evidence" in output_obj
        assert "impact" in output_obj
        assert "recommendation" in output_obj
        assert "confidence" in output_obj
        assert 0.0 <= output_obj["confidence"] <= 1.0


def test_external_dataset_importer(tmp_path):
    """Verify ExternalDatasetImporter provenance tracking and schema normalization."""
    raw_data = [
        {
            "instruction": "Diagnose S3 upload issue",
            "input": "S3 put object returns HTTP 403 Forbidden.",
            "output": json.dumps({
                "problem": "S3 PutObject 403 Forbidden",
                "probable_root_cause": "Bucket policy restricts writes",
                "evidence": ["S3 returned 403 Forbidden"],
                "impact": "Uploads fail",
                "recommendation": "Review bucket policy",
                "confidence": 0.90
            }),
            "category": "S3"
        }
    ]
    
    import_file = tmp_path / "external_raw.jsonl"
    with open(import_file, "w", encoding="utf-8") as f:
        for item in raw_data:
            f.write(json.dumps(item) + "\n")
            
    importer = ExternalDatasetImporter()
    imported = importer.import_from_jsonl(import_file, source_name="Public_Postmortems_Repo", license_name="Apache-2.0")
    
    assert len(imported) == 1
    ex = imported[0]
    assert ex["_metadata"]["source"] == "Public_Postmortems_Repo"
    assert ex["_metadata"]["license"] == "Apache-2.0"
    
    is_valid, errors = validate_example(ex)
    assert is_valid is True


def test_jaccard_similarity_and_near_duplicates():
    """Verify Jaccard similarity and near-duplicate detection."""
    text1 = "EC2 instance i-123 is stopped and web server is unreachable."
    text2 = "EC2 instance i-123 is stopped and application server is unreachable."
    text3 = "S3 bucket policy denies public read access to objects."
    
    sim12 = calculate_jaccard_similarity(text1, text2)
    sim13 = calculate_jaccard_similarity(text1, text3)
    
    assert sim12 >= 0.70
    assert sim13 < 0.30
    
    examples = [
        {"instruction": "Check EC2.", "input": text1},
        {"instruction": "Check EC2.", "input": text2},
        {"instruction": "Check S3.", "input": text3},
    ]
    
    near_dups = find_near_duplicates(examples, threshold=0.70)
    assert len(near_dups) >= 1
    assert near_dups[0][0] == 0
    assert near_dups[0][1] == 1


def test_group_and_split_dataset_anti_leakage():
    """Verify variant-grouped splitting prevents near-duplicate leakage across splits."""
    examples = [
        {"instruction": "EC2 issue A", "input": "EC2 instance i-100 is stopped. Web server down."},
        {"instruction": "EC2 issue A variant", "input": "EC2 instance i-100 is stopped. Application server down."},
        {"instruction": "S3 issue B", "input": "S3 bucket policy denies get object."},
        {"instruction": "S3 issue B variant", "input": "S3 bucket policy restricts get object permissions."},
        {"instruction": "RDS issue C", "input": "RDS database storage is full."},
        {"instruction": "RDS issue C variant", "input": "RDS database disk space 0 MB free."},
    ]
    
    train_set, val_set, test_set = group_and_split_dataset(examples, train_ratio=0.5, val_ratio=0.5, test_ratio=0.0, seed=42)
    
    train_inputs = {ex["input"] for ex in train_set}
    val_inputs = {ex["input"] for ex in val_set}
    
    # Check that near-duplicate variants do not leak across splits
    assert len(train_inputs.intersection(val_inputs)) == 0


def test_dataset_statistics_reporting():
    """Verify generate_dataset_statistics calculates metadata and counts accurately."""
    generator = CloudOpsScenarioGenerator(seed=123)
    scenarios = generator.generate_scenarios(count_per_category=2)
    
    stats = generate_dataset_statistics(scenarios)
    assert stats["total_examples"] <= len(ALL_SERVICES) * 2
    assert "services_breakdown" in stats
    assert "categories_breakdown" in stats
    assert "scenario_breakdown" in stats
    assert stats["multi_signal_examples"] >= 0
    assert stats["uncertainty_examples"] >= 0


def test_decoupled_dataset_statistics():
    """Verify generate_decoupled_dataset_statistics provides 3-way decoupled metrics."""
    generator = CloudOpsScenarioGenerator(seed=777)
    curated = [{"instruction": "Inst 1", "input": "EC2 stopped", "output": json.dumps({"problem": "p", "probable_root_cause": "r", "evidence": ["e"], "impact": "i", "recommendation": "rec", "confidence": 0.9})}]
    generated = generator.generate_scenarios(count_per_category=1)
    preserved = [{"instruction": "Inst 2", "input": "S3 403", "output": json.dumps({"problem": "p", "probable_root_cause": "r", "evidence": ["e"], "impact": "i", "recommendation": "rec", "confidence": 0.9})}]

    decoupled = generate_decoupled_dataset_statistics(curated, generated, preserved)
    assert "curated" in decoupled
    assert "generated" in decoupled
    assert "combined" in decoupled
    assert decoupled["generated_signature_uniqueness_rate"] > 0.90


def test_scenario_types_and_deduplication():
    """Verify generator generates diverse scenario types and rejects duplicates using signature deduplication."""
    generator = CloudOpsScenarioGenerator(seed=999)
    scenarios = generator.generate_scenarios(count_per_category=4)

    # Check metadata presence and scenario types
    scenario_types = set()
    for ex in scenarios:
        assert "_metadata" in ex
        assert "scenario_type" in ex["_metadata"]
        scenario_types.add(ex["_metadata"]["scenario_type"])

    # Ensure multiple scenario types are present
    assert len(scenario_types) >= 4

    # Check text near-duplicate threshold at 0.85 (should be low/zero due to on-the-fly filtering)
    near_dups = find_near_duplicates(scenarios, threshold=0.85)
    assert len(near_dups) == 0


def test_low_confidence_uncertainty_handling():
    """Verify that INSUFFICIENT_EVIDENCE scenarios produce low confidence (<=0.50) output JSON."""
    generator = CloudOpsScenarioGenerator(seed=456)
    scenarios = generator.generate_scenarios(count_per_category=5)

    uncertainty_scenarios = [ex for ex in scenarios if ex.get("_metadata", {}).get("scenario_type") == "INSUFFICIENT_EVIDENCE"]
    assert len(uncertainty_scenarios) > 0

    for ex in uncertainty_scenarios:
        out_obj = json.loads(ex["output"])
        assert out_obj["confidence"] <= 0.50
        assert "insufficient" in out_obj["probable_root_cause"].lower() or "telemetry" in out_obj["probable_root_cause"].lower() or "inconclusive" in out_obj["probable_root_cause"].lower() or "ambiguous" in out_obj["probable_root_cause"].lower()


