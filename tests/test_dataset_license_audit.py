"""
Step 3 -- Dataset License and Provenance Audit Tests.

Safety rules enforced:
1. Unknown licenses cannot automatically become TRAINING_ALLOWED.
2. Missing provenance cannot become provenance_verified=True.
3. Non-commercial datasets (CC BY-NC) cannot be marked training_eligibility=TRAINING_ALLOWED.
4. Ambiguous / no-license sources must be marked human_review_required=True.
5. Existing manifest information must remain intact after audit field additions.
6. The dataset_eligibility.json summary must be internally consistent.
"""
import json
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST_DIR = ROOT / "data" / "manifests"
REPORTS_DIR = ROOT / "data" / "reports"

MANIFESTS = {
    "rcaeval": MANIFEST_DIR / "rcaeval.manifest.json",
    "danluu": MANIFEST_DIR / "danluu-post-mortems.manifest.json",
    "aws": MANIFEST_DIR / "aws-sample-rca-deep-investigations.manifest.json",
    "lemma": MANIFEST_DIR / "lemma-rca-baselines.manifest.json",
}

ELIGIBILITY_JSON = REPORTS_DIR / "dataset_eligibility.json"
AUDIT_REPORT_MD = REPORTS_DIR / "dataset_license_audit.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def manifests():
    result = {}
    for key, path in MANIFESTS.items():
        assert path.exists(), f"Manifest file missing: {path}"
        with open(path, encoding="utf-8") as f:
            result[key] = json.load(f)
    return result


@pytest.fixture(scope="module")
def eligibility():
    assert ELIGIBILITY_JSON.exists(), f"Eligibility JSON missing: {ELIGIBILITY_JSON}"
    with open(ELIGIBILITY_JSON, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def eligibility_by_id(eligibility):
    return {ds["dataset_id"]: ds for ds in eligibility["datasets"]}


# ---------------------------------------------------------------------------
# Rule 1: Unknown licenses cannot automatically become TRAINING_ALLOWED
# ---------------------------------------------------------------------------

class TestUnknownLicenseCannotBecomeTrainingAllowed:
    def test_danluu_no_license_not_training_allowed(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        training_status = audit.get("training_eligibility", "")
        assert training_status != "TRAINING_ALLOWED", (
            f"danluu has no license file but training_eligibility={training_status!r}. "
            "Unknown license must not automatically become TRAINING_ALLOWED."
        )

    def test_danluu_no_license_requires_human_review(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        assert audit.get("human_review_required") is True, (
            "danluu has no license -- human_review_required must be True."
        )

    def test_danluu_no_license_not_rag_allowed(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        rag_status = audit.get("rag_eligibility", "")
        assert rag_status != "RAG_ALLOWED", (
            f"danluu has no license file but rag_eligibility={rag_status!r}. "
            "Unknown license must not automatically become RAG_ALLOWED."
        )

    def test_danluu_license_name_not_fabricated(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        license_name = audit.get("license_name", "")
        assert license_name in ("NONE", "UNKNOWN", ""), (
            f"danluu has no license file -- license_name should be NONE or UNKNOWN, "
            f"got: {license_name!r}"
        )

    def test_danluu_license_not_verified(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        assert audit.get("license_verified") is False, (
            "danluu has no LICENSE file -- license_verified must be False."
        )

    def test_eligibility_danluu_not_training_allowed(self, eligibility_by_id):
        ds = eligibility_by_id.get("danluu_post_mortems", {})
        status = ds.get("eligibility", {}).get("training_eligibility", "")
        assert status != "TRAINING_ALLOWED", (
            f"dataset_eligibility.json marks danluu as {status!r} -- must not be TRAINING_ALLOWED."
        )


# ---------------------------------------------------------------------------
# Rule 2: Missing provenance cannot become provenance_verified=True
# ---------------------------------------------------------------------------

class TestMissingProvenanceCannotBeVerified:
    def test_all_manifests_have_provenance_field(self, manifests):
        for key, manifest in manifests.items():
            assert "provenance" in manifest, f"Manifest {key!r} missing required 'provenance' field."
            assert len(manifest["provenance"]) > 10, (
                f"Manifest {key!r} has suspiciously short provenance."
            )

    def test_all_audit_blocks_have_provenance_verified(self, manifests):
        for key, manifest in manifests.items():
            audit = manifest.get("audit", {})
            assert "provenance_verified" in audit, (
                f"Manifest {key!r} audit block missing 'provenance_verified' field."
            )

    def test_provenance_verified_is_boolean(self, manifests):
        for key, manifest in manifests.items():
            pv = manifest.get("audit", {}).get("provenance_verified")
            assert isinstance(pv, bool), (
                f"Manifest {key!r}: provenance_verified must be bool, got {type(pv).__name__!r}."
            )

    def test_lemma_raw_data_not_marked_downloaded(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        assert audit.get("raw_data_downloaded") is False, (
            "LEMMA-RCA raw data was not downloaded -- raw_data_downloaded must be False."
        )


# ---------------------------------------------------------------------------
# Rule 3: Non-commercial datasets are not marked unrestricted for training
# ---------------------------------------------------------------------------

class TestNonCommercialDatasetsNotMarkedUnrestricted:
    def test_lemma_cc_bync_not_training_allowed(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        status = audit.get("training_eligibility", "")
        assert status != "TRAINING_ALLOWED", (
            f"LEMMA-RCA is CC BY-NC 4.0 but training_eligibility={status!r}. "
            "Non-commercial license must not produce TRAINING_ALLOWED."
        )

    def test_lemma_cc_bync_not_rag_allowed(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        status = audit.get("rag_eligibility", "")
        assert status != "RAG_ALLOWED", (
            f"LEMMA-RCA is CC BY-NC 4.0 but rag_eligibility={status!r}. "
            "Non-commercial license must not produce RAG_ALLOWED."
        )

    def test_lemma_cc_bync_license_confirmed(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        license_name = audit.get("license_name", "")
        assert "CC BY-NC" in license_name or "CC-BY-NC" in license_name, (
            f"LEMMA-RCA license_name should contain 'CC BY-NC', got: {license_name!r}"
        )

    def test_lemma_attribution_required(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        assert audit.get("attribution_required") is True, (
            "LEMMA-RCA CC BY-NC 4.0 requires attribution -- attribution_required must be True."
        )

    def test_eligibility_lemma_not_in_training_allowed(self, eligibility):
        summary = eligibility.get("summary", {})
        training_allowed = summary.get("training_allowed", [])
        assert "lemma_rca_baselines" not in training_allowed, (
            "lemma_rca_baselines appears in training_allowed -- CC BY-NC 4.0 prohibits this."
        )

    def test_eligibility_lemma_not_in_rag_allowed(self, eligibility):
        summary = eligibility.get("summary", {})
        rag_allowed = summary.get("rag_allowed", [])
        assert "lemma_rca_baselines" not in rag_allowed, (
            "lemma_rca_baselines appears in rag_allowed -- CC BY-NC 4.0 prohibits this."
        )


# ---------------------------------------------------------------------------
# Rule 4: Ambiguous sources require human review
# ---------------------------------------------------------------------------

class TestAmbiguousSourcesRequireHumanReview:
    def test_danluu_requires_human_review(self, manifests):
        audit = manifests["danluu"].get("audit", {})
        assert audit.get("human_review_required") is True, (
            "danluu has no license file -- human_review_required must be True."
        )

    def test_lemma_requires_human_review(self, manifests):
        audit = manifests["lemma"].get("audit", {})
        assert audit.get("human_review_required") is True, (
            "LEMMA-RCA has CC BY-NC 4.0 -- commercial use ambiguity requires human_review_required=True."
        )

    def test_cleared_datasets_do_not_require_human_review(self, manifests):
        for key in ("rcaeval", "aws"):
            audit = manifests[key].get("audit", {})
            assert audit.get("human_review_required") is False, (
                f"Dataset {key!r} has a clear permissive license but human_review_required="
                f"{audit.get('human_review_required')!r}. Should be False."
            )

    def test_eligibility_human_review_list_contains_danluu_and_lemma(self, eligibility):
        summary = eligibility.get("summary", {})
        hr_list = summary.get("human_review_required", [])
        assert "danluu_post_mortems" in hr_list, (
            "danluu_post_mortems must be in human_review_required list."
        )
        assert "lemma_rca_baselines" in hr_list, (
            "lemma_rca_baselines must be in human_review_required list."
        )


# ---------------------------------------------------------------------------
# Rule 5: Existing manifest information remains intact
# ---------------------------------------------------------------------------

class TestExistingManifestInformationIntact:
    REQUIRED_BASE_FIELDS = [
        "dataset_name", "license", "provenance", "processing_status", "sanitization_status"
    ]

    def test_all_manifests_have_required_base_fields(self, manifests):
        for key, manifest in manifests.items():
            for field in self.REQUIRED_BASE_FIELDS:
                assert field in manifest, (
                    f"Manifest {key!r} is missing required base field {field!r} after audit update."
                )

    def test_rcaeval_base_fields_unchanged(self, manifests):
        m = manifests["rcaeval"]
        assert m["dataset_name"] == "RCAEval"
        assert m["source_url"] == "https://github.com/phamquiluan/RCAEval"
        assert m["record_count"] == 735
        assert m["processing_status"] == "extracted"
        assert m["sanitization_status"] == "unverified"
        assert "MIT" in m["license"]

    def test_danluu_base_fields_unchanged(self, manifests):
        m = manifests["danluu"]
        assert m["dataset_name"] == "danluu-post-mortems"
        assert m["source_url"] == "https://github.com/danluu/post-mortems"
        assert m["processing_status"] == "extracted"
        assert m["sanitization_status"] == "unverified"
        assert m["original_size_bytes"] == 39456

    def test_aws_base_fields_unchanged(self, manifests):
        m = manifests["aws"]
        assert m["dataset_name"] == "aws-sample-rca-deep-investigations"
        assert m["source_url"] == "https://github.com/aws-samples/sample-rca-deep-investigations"
        assert m["processing_status"] == "extracted"
        assert m["sanitization_status"] == "unverified"
        assert m["original_size_bytes"] == 571350
        assert "MIT-0" in m["license"] or "MIT No Attribution" in m["license"]

    def test_lemma_base_fields_unchanged(self, manifests):
        m = manifests["lemma"]
        assert m["dataset_name"] == "LEMMA-RCA-baselines"
        assert m["source_url"] == "https://github.com/KnowledgeDiscovery/rca_baselines"
        assert m["processing_status"] == "extracted"
        assert m["sanitization_status"] == "unverified"
        assert m["original_size_bytes"] == 1792968
        assert "CC BY-NC" in m["license"]

    def test_checksums_preserved_in_manifests(self, manifests):
        rcaeval_checksums = manifests["rcaeval"].get("checksum", {})
        assert "RCAEval-1.7.0.zip" in rcaeval_checksums
        assert "C9F68B97E955220F9BDAD0E6C28BA083E96A6A0CB7610395307FE42925AE42AA" in (
            rcaeval_checksums["RCAEval-1.7.0.zip"]
        )
        danluu_checksums = manifests["danluu"].get("checksum", {})
        assert "danluu-post-mortems-master.zip" in danluu_checksums
        aws_checksums = manifests["aws"].get("checksum", {})
        assert "aws-sample-rca-deep-investigations-main.zip" in aws_checksums
        lemma_checksums = manifests["lemma"].get("checksum", {})
        assert "lemma-rca-baselines-main.zip" in lemma_checksums

    def test_manifests_are_valid_json(self):
        for name, path in MANIFESTS.items():
            assert path.exists(), f"Manifest file {path} does not exist."
            try:
                with open(path, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Manifest {name!r} is invalid JSON: {e}")

    def test_eligibility_json_is_valid(self):
        assert ELIGIBILITY_JSON.exists(), f"Eligibility JSON missing: {ELIGIBILITY_JSON}"
        try:
            with open(ELIGIBILITY_JSON, encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            pytest.fail(f"dataset_eligibility.json is invalid JSON: {e}")

    def test_audit_report_exists(self):
        assert AUDIT_REPORT_MD.exists(), f"Audit report missing: {AUDIT_REPORT_MD}"
        content = AUDIT_REPORT_MD.read_text(encoding="utf-8")
        assert len(content) > 1000, "Audit report appears suspiciously short."


# ---------------------------------------------------------------------------
# Rule 6: Eligibility JSON internal consistency
# ---------------------------------------------------------------------------

class TestEligibilityJsonConsistency:
    EXPECTED_DATASET_IDS = {
        "rcaeval", "danluu_post_mortems", "aws_sample_rca", "lemma_rca_baselines"
    }

    def test_all_expected_datasets_present(self, eligibility_by_id):
        for ds_id in self.EXPECTED_DATASET_IDS:
            assert ds_id in eligibility_by_id, (
                f"Dataset {ds_id!r} missing from dataset_eligibility.json."
            )

    def test_training_allowed_datasets_are_correct(self, eligibility):
        summary = eligibility.get("summary", {})
        allowed = set(summary.get("training_allowed", []))
        assert "rcaeval" in allowed, "RCAEval (MIT) should be in training_allowed."
        assert "aws_sample_rca" in allowed, "AWS Sample RCA (MIT-0) should be in training_allowed."
        assert "lemma_rca_baselines" not in allowed, "LEMMA (CC BY-NC) must not be in training_allowed."
        assert "danluu_post_mortems" not in allowed, "danluu (no license) must not be in training_allowed."

    def test_rag_allowed_datasets_are_correct(self, eligibility):
        summary = eligibility.get("summary", {})
        allowed = set(summary.get("rag_allowed", []))
        assert "rcaeval" in allowed, "RCAEval (MIT) should be in rag_allowed."
        assert "aws_sample_rca" in allowed, "AWS Sample RCA (MIT-0) should be in rag_allowed."
        assert "lemma_rca_baselines" not in allowed, "LEMMA (CC BY-NC) must not be in rag_allowed."
        assert "danluu_post_mortems" not in allowed, "danluu (no license) must not be in rag_allowed."

    def test_total_datasets_count(self, eligibility):
        summary = eligibility.get("summary", {})
        assert summary.get("total_datasets_audited") == 4, "Expected 4 total datasets audited."

    def test_eligibility_status_values_are_valid(self, eligibility_by_id):
        valid_training = {
            "TRAINING_ALLOWED", "TRAINING_ALLOWED_WITH_ATTRIBUTION",
            "TRAINING_REQUIRES_HUMAN_REVIEW", "TRAINING_NOT_ALLOWED", "UNKNOWN",
        }
        valid_rag = {
            "RAG_ALLOWED", "RAG_ALLOWED_WITH_ATTRIBUTION",
            "RAG_REQUIRES_HUMAN_REVIEW", "RAG_NOT_ALLOWED", "UNKNOWN",
        }
        for ds_id, ds in eligibility_by_id.items():
            elig = ds.get("eligibility", {})
            t_status = elig.get("training_eligibility", "")
            r_status = elig.get("rag_eligibility", "")
            assert t_status in valid_training, (
                f"Dataset {ds_id!r} has invalid training_eligibility: {t_status!r}."
            )
            assert r_status in valid_rag, (
                f"Dataset {ds_id!r} has invalid rag_eligibility: {r_status!r}."
            )

    def test_checksum_verified_for_all_datasets(self, eligibility_by_id):
        for ds_id, ds in eligibility_by_id.items():
            flags = ds.get("audit_flags", {})
            assert flags.get("checksum_verified") is True, (
                f"Dataset {ds_id!r} does not have checksum_verified=True in audit_flags."
            )

    def test_rcaeval_requires_attribution(self, eligibility_by_id):
        ds = eligibility_by_id.get("rcaeval", {})
        elig = ds.get("eligibility", {})
        assert elig.get("attribution_required") is True, (
            "RCAEval (MIT license) requires attribution -- attribution_required must be True."
        )

    def test_aws_does_not_require_attribution(self, eligibility_by_id):
        ds = eligibility_by_id.get("aws_sample_rca", {})
        elig = ds.get("eligibility", {})
        assert elig.get("attribution_required") is False, (
            "AWS Sample RCA (MIT-0) does not require attribution -- attribution_required must be False."
        )
