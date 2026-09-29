# Common CloudOps FAQs & Platform Operations

## 1. Frequently Asked Questions
- **Q: Why does the first diagnosis request take longer?**
  - **A**: The first request pre-warms the Qwen model weights and PyTorch CUDA context into GPU VRAM. Subsequent requests execute significantly faster. Pre-warming can be enabled on startup with `EAGER_MODEL_LOAD=1`.

- **Q: What happens if Hugging Face or external API is offline?**
  - **A**: CloudOps is configured with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` using locally cached model weights (`Qwen/Qwen2.5-3B-Instruct`). If external APIs are unavailable, local synthesis fallbacks take over gracefully.

- **Q: How are credentials and API keys secured?**
  - **A**: All Groq API keys and AWS credentials are read server-side from environment variables (`GROQ_API_KEY`, `AWS_ACCESS_KEY_ID`). They are **never** exposed to client-side responses or logs.

- **Q: Does CloudOps make changes to my AWS environment?**
  - **A**: No. All AWS API queries performed by CloudOps are strictly read-only (`DescribeInstances`, `GetMetricData`, `LookupEvents`). CloudOps never mutates, restarts, or deletes AWS resources.

- **Q: How are confidence scores calculated?**
  - **A**: Confidence scores (0.0 to 1.0) reflect telemetry signal clarity and factual grounding. Scores above 0.85 indicate direct empirical proof (e.g. Security Group missing Port 80 rule), while lower scores indicate partial evidence.
