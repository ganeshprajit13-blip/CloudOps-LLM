import time
import logging
from typing import Dict, Any, Optional, List

from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    DiagnosisSchema,
    RetrievedKnowledgeItem,
)
from app.services.context_builder import ContextBuilder
from app.services.prompt_builder import PromptBuilder
from app.services.diagnosis_validator import DiagnosisValidator

logger = logging.getLogger("cloudops.services.cloudops_analyzer")

class CloudOpsAnalyzer:
    """
    Main intelligence pipeline coordinator:
    AWS Live Data (Phase 2/3) + RAG Knowledge Base (Phase 6) + Qwen LLM (Phase 5) -> Validated Diagnosis.
    """

    def __init__(
        self,
        context_builder: Optional[ContextBuilder] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        validator: Optional[DiagnosisValidator] = None,
        model_runner: Optional[Any] = None,
        rag_query_fn: Optional[Any] = None
    ):
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.validator = validator or DiagnosisValidator()
        self.model_runner = model_runner
        self.rag_query_fn = rag_query_fn

    def _collect_and_normalize_aws_data(self) -> Dict[str, Any]:
        """
        Attempt to collect read-only AWS telemetry via Phase 2/3 services.
        Handles missing credentials or network errors gracefully.
        """
        try:
            from app.services.aws_collector import collect_infrastructure_data
            from app.services.preprocessing import preprocess_cloud_context as normalize_cloud_context

            logger.info("Attempting read-only live AWS infrastructure collection...")
            raw_data = collect_infrastructure_data()
            normalized = normalize_cloud_context(raw_data)
            
            if hasattr(normalized, "dict"):
                return normalized.dict()
            elif hasattr(normalized, "model_dump"):
                return normalized.model_dump()
            elif isinstance(normalized, dict):
                return normalized
            return {}
        except Exception as e:
            logger.warning(f"Live AWS collection failed or skipped: {e}")
            return {}

    def _query_rag(self, query: str, signals: List[Dict[str, Any]]) -> List[RetrievedKnowledgeItem]:
        """
        Execute RAG retrieval via Phase 6 query_knowledge_base interface.
        Formulates an enhanced query using question + signal keywords.
        """
        try:
            if self.rag_query_fn:
                rag_resp = self.rag_query_fn(query)
            else:
                from rag.pipeline import query_knowledge_base
                
                enhanced_query = query
                signal_types = sorted(list(set(s.get("type", "") for s in signals if isinstance(s, dict) and s.get("type"))))
                if signal_types:
                    enhanced_query += " " + " ".join(signal_types)

                rag_resp = query_knowledge_base(query=enhanced_query, top_k=5)

            results = []
            raw_results = getattr(rag_resp, "results", []) or []
            for item in raw_results:
                meta = getattr(item, "metadata", {}) or {}
                results.append(
                    RetrievedKnowledgeItem(
                        source=str(meta.get("source", "unknown")),
                        title=str(meta.get("title", "Untitled")),
                        service=str(meta.get("service", "general")),
                        score=float(getattr(item, "score", 0.0)),
                        text=str(getattr(item, "text", ""))
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"RAG knowledge retrieval failed or skipped: {e}")
            return []

    def _run_model_inference(
        self,
        question: str,
        cloud_context: Dict[str, Any],
        prompt_text: str
    ) -> Dict[str, Any]:
        """
        Execute Phase 5 Qwen model inference.
        Uses model_runner if injected, else calls ModelSingletonManager and generate_diagnosis.
        """
        if self.model_runner:
            return self.model_runner(question, cloud_context, prompt_text)

        try:
            from model.model_loader import ModelSingletonManager
            from model.inference import generate_diagnosis

            model_obj, tok_obj, _, _ = ModelSingletonManager.get_instance()

            return generate_diagnosis(
                model=model_obj,
                tokenizer=tok_obj,
                incident_query=question,
                cloud_context=cloud_context,
                prompt_text=prompt_text,
            )
        except Exception as e:
            logger.error(f"Model inference execution failed: {e}")
            raise RuntimeError(f"CloudOps LLM inference is currently unavailable: {e}") from e

    def analyze(
        self,
        question: str,
        cloud_context: Optional[Dict[str, Any]] = None,
        resource_id: Optional[str] = None,
        collect_live_data: bool = True
    ) -> AnalysisResponse:
        """
        Main CloudOps Intelligence Analysis Entrypoint.
        Coordinates:
        AWS Telemetry -> Context Normalization -> RAG Retrieval -> Prompt Construction -> Model Inference -> Validation.
        """
        start_time = time.time()
        logger.info(f"Starting CloudOps analysis for question: '{question}' (resource_id={resource_id})")

        if not question or not question.strip():
            fallback_dict = self.validator.build_insufficient_evidence_response(
                question="[Empty Query]",
                reason="Question text was empty or blank."
            )
            return AnalysisResponse(
                query=question or "",
                diagnosis=DiagnosisSchema(**fallback_dict),
                retrieved_knowledge=[],
                cloud_signals=[],
                execution_time_seconds=round(time.time() - start_time, 4),
                error="EMPTY_QUERY",
                message="Question string cannot be empty."
            )

        # 1. Acquire Cloud Context (AWS Collection & Preprocessing)
        final_context = dict(cloud_context) if cloud_context else {}
        t_aws_start = time.time()
        if collect_live_data and not final_context:
            collected = self._collect_and_normalize_aws_data()
            if collected:
                final_context = collected
        t_aws = round(time.time() - t_aws_start, 4)

        if resource_id and final_context:
            final_context = self.context_builder.filter_context_by_resource(
                final_context,
                resource_id
            )

        extracted_signals = final_context.get("signals", []) if isinstance(final_context, dict) else []

        # 2. Build Formatted Cloud Context Representation (Preprocessing)
        t_pre_start = time.time()
        formatted_context_text = self.context_builder.build_context_text(
            cloud_context=final_context,
            resource_id=resource_id
        )
        t_pre = round(time.time() - t_pre_start, 4)

        # 3. Retrieve RAG Knowledge
        t_rag_start = time.time()
        retrieved_knowledge = self._query_rag(query=question, signals=extracted_signals)
        t_rag = round(time.time() - t_rag_start, 4)

        # 4. Construct Final Prompt
        prompt_text = self.prompt_builder.build_prompt(
            question=question,
            formatted_context=formatted_context_text,
            retrieved_knowledge=retrieved_knowledge
        )
        logger.info(f"Final prompt text constructed (length: {len(prompt_text)} chars)")

        # 5. Model Inference & Token Generation
        t_gen_start = time.time()
        raw_diagnosis = self._run_model_inference(
            question=question,
            cloud_context=final_context,
            prompt_text=prompt_text
        )
        t_gen_total = round(time.time() - t_gen_start, 4)

        if isinstance(raw_diagnosis, str):
            extracted = self.validator.safe_extract_json(raw_diagnosis)
            raw_diagnosis_dict = extracted if isinstance(extracted, dict) else {}
        elif isinstance(raw_diagnosis, dict):
            raw_diagnosis_dict = raw_diagnosis
        else:
            raw_diagnosis_dict = {}

        t_prompt_prep = float(raw_diagnosis_dict.pop("_prompt_prep_time_seconds", 0.0))
        t_token_gen = float(raw_diagnosis_dict.pop("_token_generation_time_seconds", t_gen_total))
        t_total_inference = float(raw_diagnosis_dict.pop("_total_inference_time_seconds", t_gen_total))

        # Model singleton acquisition load time status
        from model.model_loader import ModelSingletonManager
        t_total_model_init = ModelSingletonManager._model_load_time_seconds
        t_model_init = ModelSingletonManager._base_model_init_time_seconds
        t_tok_init = ModelSingletonManager._tokenizer_init_time_seconds
        t_adapter_load = ModelSingletonManager._adapter_init_time_seconds
        adapter_status = ModelSingletonManager._adapter_status

        # Normalize field aliases and coerce types before validation
        raw_diagnosis_dict = self.validator.normalize_diagnosis_payload(raw_diagnosis_dict)

        # Filter out ungrounded/contradictory evidence items and reconcile with context evidence
        raw_ev = raw_diagnosis_dict.get("evidence", [])
        if isinstance(raw_ev, list):
            valid_ev, rejected = self.validator.validate_and_filter_evidence(raw_ev, final_context)
            if rejected:
                logger.warning(f"Filtered out ungrounded/contradictory evidence items: {rejected}")
            context_evidence = final_context.get("evidence", [])
            if not valid_ev and context_evidence:
                valid_ev = list(context_evidence)
            raw_diagnosis_dict["evidence"] = valid_ev

        # 6. Validate & Sanitize Diagnosis Payload
        is_valid, schema_err = self.validator.validate_schema(raw_diagnosis_dict)
        if not is_valid:
            logger.warning(f"Raw diagnosis failed schema validation: {schema_err}")
            raw_diagnosis_dict = self.validator.build_insufficient_evidence_response(
                question=question,
                reason=f"Model output schema validation failed: {schema_err}"
            )

        sanitized_diagnosis = self.validator.enforce_advisory_safety(raw_diagnosis_dict, cloud_context=final_context)


        rag_texts = [item.text for item in retrieved_knowledge]
        is_grounded, grounding_warnings = self.validator.check_evidence_grounding(
            diagnosis_data=sanitized_diagnosis,
            cloud_context=final_context,
            rag_texts=rag_texts
        )

        if not is_grounded:
            logger.warning(f"Evidence grounding check identified ungrounded claims: {grounding_warnings}")
            sanitized_diagnosis = self.validator.build_insufficient_evidence_response(
                question=question,
                reason=f"Diagnosis claimed unsupported resources or uncollected host state: {'; '.join(grounding_warnings)}"
            )

        try:
            diagnosis_obj = DiagnosisSchema(**sanitized_diagnosis)
        except Exception as err:
            logger.error(f"Failed to instantiate DiagnosisSchema: {err}")
            fallback_dict = self.validator.build_insufficient_evidence_response(
                question=question,
                reason=f"Diagnosis schema instantiation failed: {str(err)}"
            )
            diagnosis_obj = DiagnosisSchema(**fallback_dict)

        exec_duration = round(time.time() - start_time, 4)

        logger.info(
            f"CloudOps Complete Stage Timings Summary:\n"
            f"  - Model Initialization:      {t_model_init}s\n"
            f"  - Tokenizer Initialization:  {t_tok_init}s\n"
            f"  - Adapter Loading:          {t_adapter_load}s (Total Model Load: {t_total_model_init}s, Adapter Status: {adapter_status})\n"
            f"  - AWS Telemetry Collection: {t_aws}s\n"
            f"  - Context Preprocessing:    {t_pre}s\n"
            f"  - RAG Knowledge Retrieval:  {t_rag}s\n"
            f"  - Prompt Preparation:       {t_prompt_prep}s\n"
            f"  - Token Generation:         {t_token_gen}s\n"
            f"  - Total Inference:          {t_total_inference}s\n"
            f"  - Total CloudOps Analysis:  {exec_duration}s"
        )

        return AnalysisResponse(
            query=question,
            diagnosis=diagnosis_obj,
            retrieved_knowledge=retrieved_knowledge,
            cloud_signals=extracted_signals if isinstance(extracted_signals, list) else [],
            execution_time_seconds=exec_duration,
            error=None,
            message=f"Analysis completed successfully in {exec_duration}s. Adapter Status: {adapter_status}"
        )
