# CloudOps Support Agent Architecture & API Specification

## 1. Support Agent Architecture (`POST /api/support-chat`)
The CloudOps Support Agent provides grounded technical assistance for CloudOps product usage, AWS cloud infrastructure, and the underlying AI/LLM system architecture.

### Processing Pipeline:
1. **User Request**: Client sends POST request to `/api/support-chat` (or `/api/support/chat`) with `{ "message": "...", "history": [...] }`.
2. **Support RAG Retrieval**: System embeds the query using `sentence-transformers/all-MiniLM-L6-v2` and queries the `cloudops_support` collection in ChromaDB (`top_k=4`).
3. **Grounded System Prompt**: Constructs a system prompt containing retrieved Support Knowledge Base documents and strict grounding guardrails.
4. **Session History**: Includes up to 6 recent messages (~3 conversation turns) to maintain context without overloading context windows.
5. **Support Agent Inference**: Executes generation using the Support QLoRA adapter in `outputs/support_agent_adapter/` (or server-side Groq LLM API fallback if configured).
6. **Structured Response Delivery**: Returns `{ "answer": "...", "sources": [ { "title": "...", "category": "...", "relevance": 0.92 } ] }`.

---

## 2. Guardrails & Safety Policy
- **Grounded Responses**: Answers must be derived from the retrieved Support Knowledge Base context and actual CloudOps implementation.
- **No Live AWS Telemetry Claims**: Support Agent does NOT claim to inspect live AWS telemetry unless the user is actively running a diagnosis on the AI Troubleshooter page.
- **No Autonomous Remediation**: Support Agent provides guidance only and does NOT execute AWS infrastructure modifications.
- **Insufficient Context Handling**: If retrieved context does not contain sufficient facts to answer a specific query, the agent clearly states that information is currently unavailable in the knowledge base.
