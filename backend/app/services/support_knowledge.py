import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

logger = logging.getLogger("cloudops.services.support_knowledge")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PERSIST_DIR = str(PROJECT_ROOT / "storage" / "chroma_support")
COLLECTION_NAME = "cloudops_support"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_support_collection = None
_embedder_model = None

# ============================================================
# COMPREHENSIVE AWS & CloudOps Terminology Alias Map
# Order matters: longer patterns first to avoid partial matches
# ============================================================
AWS_ALIAS_MAP = {
    # Typo corrections (common misspellings)
    r"\binstnace\b": "instance",
    r"\binstanc\b": "instance",
    r"\binstaces\b": "instances",
    r"\bsecurty\b": "security",
    r"\bsecutiry\b": "security",
    r"\bgateway\b": "gateway",
    r"\bgatway\b": "gateway",
    r"\bgetway\b": "gateway",
    r"\bgateway\b": "gateway",
    r"\bcloudwatc\b": "CloudWatch",
    r"\bcloudwach\b": "CloudWatch",
    r"\bclodwatch\b": "CloudWatch",
    r"\bcloudtral\b": "CloudTrail",
    r"\bcloudtrai\b": "CloudTrail",
    r"\bunrechable\b": "unreachable",
    r"\bunreacheable\b": "unreachable",
    r"\bterraform\b": "Terraform",
    r"\bkubernates\b": "Kubernetes",
    r"\bkuberentes\b": "Kubernetes",
    r"\bdocker\b": "Docker",
    # AWS Service Abbreviations
    r"\bnacl\b": "NACL Network Access Control List subnet",
    r"\bnacls\b": "NACLs Network Access Control Lists subnets",
    r"\bnat gateway\b": "NAT Gateway private subnet outbound internet",
    r"\bnat\b": "NAT Gateway private subnet outbound",
    r"\bigw\b": "Internet Gateway IGW VPC public subnet internet",
    r"\bsg\b": "Security Group firewall inbound rules",
    r"\bsgs\b": "Security Groups firewalls",
    r"\bvpc\b": "VPC Virtual Private Cloud network",
    r"\brdp\b": "RDP Remote Desktop Protocol Windows port 3389",
    r"\biam\b": "IAM Identity Access Management role policy user",
    r"\bssm\b": "AWS Systems Manager SSM Session Manager",
    r"\balb\b": "Application Load Balancer ALB",
    r"\belb\b": "Elastic Load Balancer ELB",
    r"\basg\b": "Auto Scaling Group ASG",
    r"\bs3\b": "Amazon S3 Simple Storage Service bucket",
    r"\brds\b": "Amazon RDS Relational Database Service",
    r"\bami\b": "AMI Amazon Machine Image EC2 template",
    r"\bebs\b": "EBS Elastic Block Store volume storage",
    r"\bec2\b": "EC2 Amazon Elastic Compute Cloud instance",
    r"\bcw\b": "CloudWatch metrics monitoring",
    r"\bct\b": "CloudTrail audit API activity",
    r"\bk8s\b": "Kubernetes container orchestration",
    r"\bcicd\b": "CI/CD Continuous Integration Continuous Delivery pipeline",
    r"\bci/cd\b": "CI/CD Continuous Integration Continuous Delivery pipeline",
    r"\biac\b": "Infrastructure as Code Terraform",
    r"\btcp\b": "TCP protocol network port",
    r"\bhttp\b": "HTTP HyperText Transfer Protocol port 80 web",
    r"\bhttps\b": "HTTPS HTTP Secure TLS port 443 web encrypted",
    r"\bssh\b": "SSH Secure Shell port 22 Linux remote access",
    r"\bdns\b": "DNS Domain Name System name resolution Route 53",
    # Informal queries
    r"\bvhai\b": "why",
    r"\bwhai\b": "why",
    r"\bwat\b": "what",
    r"\bwt\b": "what",
    r"\btoo\b": "to",
    r"\bwhys\b": "why",
    r"\bvs\b": "versus comparison difference between",
}


def _get_embedder():
    global _embedder_model
    if _embedder_model is not None:
        return _embedder_model
    try:
        from sentence_transformers import SentenceTransformer
        try:
            _embedder_model = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=True)
        except Exception:
            _embedder_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        return _embedder_model
    except Exception as e:
        logger.error(f"Failed to load embedding model '{EMBEDDING_MODEL_NAME}': {e}")
        return None


def _init_support_collection():
    global _support_collection
    if _support_collection is not None:
        return _support_collection

    try:
        import chromadb
        from chromadb.config import Settings

        os.makedirs(PERSIST_DIR, exist_ok=True)
        client = chromadb.PersistentClient(
            path=PERSIST_DIR,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

        _support_collection = collection
        logger.info(f"Connected to ChromaDB collection '{COLLECTION_NAME}' at '{PERSIST_DIR}'. Total chunks: {collection.count()}")
        return _support_collection

    except Exception as e:
        logger.error(f"Support knowledge base initialization failed: {e}")
        return None


def normalize_support_query(query: str) -> str:
    """
    Comprehensive query normalizer:
    1. Lowercase & strip.
    2. Correct common typos.
    3. Expand AWS abbreviations to full terms for embedding quality.
    4. Handle short single-word queries by expanding them.
    NOTE: Does NOT wholesale replace entire query — preserves user intent.
    """
    if not query:
        return ""

    normalized = query.strip()

    # Apply alias map with word-boundary regex
    for pattern, replacement in AWS_ALIAS_MAP.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    # Handle very short single-token queries (1-2 words) — expand to full question form
    tokens = normalized.split()
    if len(tokens) <= 2:
        lower = normalized.lower()
        if "vpc" in lower or "virtual private cloud" in lower:
            normalized = "What is a VPC Virtual Private Cloud network?"
        elif "nat gateway" in lower or "nat" in lower:
            normalized = "What is a NAT Gateway private subnet outbound internet?"
        elif "igw" in lower or "internet gateway" in lower:
            normalized = "What is an Internet Gateway VPC public subnet?"
        elif "rdp" in lower or "remote desktop" in lower:
            normalized = "What is RDP Remote Desktop Protocol Windows port 3389?"
        elif "iam" in lower or "identity access" in lower:
            normalized = "What is IAM Identity Access Management role policy?"
        elif "dns" in lower or "domain name" in lower:
            normalized = "What is DNS Domain Name System Route 53?"
        elif "subnet" in lower:
            normalized = "What is a subnet public private VPC network?"
        elif "ec2" in lower or "elastic compute" in lower:
            normalized = "What is EC2 Amazon Elastic Compute Cloud instance?"
        elif "cloudwatch" in lower:
            normalized = "What is CloudWatch metrics monitoring alarms?"
        elif "cloudtrail" in lower:
            normalized = "What is CloudTrail audit API activity change tracking?"
        elif "nacl" in lower or "network access control" in lower:
            normalized = "What is a NACL Network Access Control List subnet?"
        elif "docker" in lower:
            normalized = "What is Docker container image build run?"
        elif "kubernetes" in lower or "k8s" in lower:
            normalized = "What is Kubernetes container orchestration pods?"
        elif "terraform" in lower:
            normalized = "What is Terraform Infrastructure as Code IaC?"
        elif "qlora" in lower:
            normalized = "What is QLoRA quantized low rank adaptation fine-tuning?"
        elif "rag" in lower:
            normalized = "What is RAG retrieval augmented generation vector?"

    logger.info(f"Original Query: '{query}' -> Normalized: '{normalized}'")
    return normalized


def classify_query_intent(query: str) -> str:
    """
    Fine-grained entity-aware intent classification.
    Returns primary intent + entity for targeted retrieval boosting.
    """
    q_lower = query.lower().strip()

    # 1. Greetings
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "hi there", "greetings", "hey there", "good afternoon"]
    if q_lower in greetings or any(q_lower == g for g in greetings):
        return "GREETING"

    # 2. Out of scope
    out_of_scope_keywords = [
        "capital of france", "capital of", "recipe", "cook", "weather",
        "football", "soccer", "movie", "president", "who wrote", "tell a joke",
        "what is love", "stock price", "cryptocurrency", "bitcoin", "nba", "nfl"
    ]
    if any(k in q_lower for k in out_of_scope_keywords):
        return "OUT_OF_SCOPE"

    # 3. Advisory guardrails
    guardrail_keywords = [
        "automatically fix", "auto remediation", "auto restart", "modify my security group",
        "delete my ec2", "restart my instance", "automatically modify", "auto modify",
        "modify my aws security group", "can you modify", "open port for me", "execute change",
        "run remediation", "make changes to my", "fix it for me", "just fix", "apply the fix"
    ]
    if any(k in q_lower for k in guardrail_keywords):
        return "GUARDRAILS"

    # 4. Fine-grained entity intents (specific beats general)

    # Windows / RDP
    if any(k in q_lower for k in ["rdp", "remote desktop", "3389", "windows ec2", "windows instance", "mstsc"]):
        return "RDP_WINDOWS"

    # EC2 Creation
    if (any(k in q_lower for k in ["create", "launch", "setup", "make", "spin up", "provision", "start"]) and
            any(k in q_lower for k in ["ec2", "instance", "virtual machine", "vm"])):
        return "EC2_CREATION"

    # IAM
    if any(k in q_lower for k in ["iam", "identity access", "iam role", "iam user", "iam policy", "trust policy", "least privilege", "instance profile", "permission boundary"]):
        return "IAM"

    # DNS / Route53
    if any(k in q_lower for k in ["dns", "domain name system", "route 53", "route53", "hosted zone", "cname", "a record", "name server", "nslookup", "dig "]):
        return "DNS"

    # VPC
    if any(k in q_lower for k in ["vpc", "virtual private cloud"]) and not any(k in q_lower for k in ["subnet", "route table", "nacl"]):
        return "VPC"

    # Subnets
    if any(k in q_lower for k in ["subnet", "public subnet", "private subnet", "cidr", "availability zone", "az "]):
        return "SUBNET"

    # Route Tables
    if any(k in q_lower for k in ["route table", "routing table", "route entry", "0.0.0.0/0"]):
        return "ROUTE_TABLE"

    # NACL comparison with SG
    if "nacl" in q_lower and ("security group" in q_lower or "sg" in q_lower or "difference" in q_lower or "versus" in q_lower or "vs" in q_lower):
        return "NACL_VS_SG"

    # NACL standalone
    if any(k in q_lower for k in ["nacl", "network access control list", "network acl"]):
        return "NACL"

    # NAT Gateway
    if any(k in q_lower for k in ["nat gateway", "nat "]) and "internet gateway" not in q_lower:
        return "NAT_GATEWAY"

    # Internet Gateway
    if any(k in q_lower for k in ["internet gateway", "igw"]):
        return "INTERNET_GATEWAY"

    # Security Group (not NACL comparison)
    if any(k in q_lower for k in ["security group", "inbound rule", "outbound rule", "sg rule", "firewall rule", "port 80", "port 443", "port 22", "port 3389"]):
        return "SECURITY_GROUP"

    # EC2 troubleshooting / unreachable
    if any(k in q_lower for k in ["unreachable", "cannot reach", "not reachable", "website down", "website unreachable", "instance unreachable"]):
        return "EC2_UNREACHABLE"

    # High CPU
    if any(k in q_lower for k in ["high cpu", "cpu spike", "cpu 100", "cpu utilization", "cpu usage", "cpuutilization"]):
        return "HIGH_CPU"

    # IIS
    if any(k in q_lower for k in ["iis", "w3svc", "internet information services", "iis stopped", "iis crash"]):
        return "IIS"

    # Docker
    if any(k in q_lower for k in ["docker", "container", "dockerfile", "docker image", "docker compose", "ecr", "containerize"]):
        return "DOCKER"

    # Kubernetes
    if any(k in q_lower for k in ["kubernetes", "k8s", "kubectl", "pod ", "deployment yaml", "eks", "helm"]):
        return "KUBERNETES"

    # Terraform
    if any(k in q_lower for k in ["terraform", "hcl", "infrastructure as code", "iac", "terraform plan", "terraform apply", "tfstate"]):
        return "TERRAFORM"

    # CI/CD
    if any(k in q_lower for k in ["ci/cd", "cicd", "continuous integration", "continuous delivery", "github actions", "jenkins", "pipeline", "codepipeline"]):
        return "CICD"

    # CloudWatch
    if any(k in q_lower for k in ["cloudwatch", "cw metric", "cpu alarm", "alarm", "metric", "log group", "cloudwatch logs", "monitoring"]):
        return "CLOUDWATCH"

    # CloudTrail
    if any(k in q_lower for k in ["cloudtrail", "audit log", "who changed", "api activity", "who deleted", "event history", "lookup events"]):
        return "CLOUDTRAIL"

    # QLoRA / LoRA
    if any(k in q_lower for k in ["qlora", "lora", "quantization", "bitsandbytes", "4-bit", "nf4", "adapter", "peft"]):
        return "QLORA"

    # RAG
    if any(k in q_lower for k in ["rag", "retrieval augmented", "vector store", "chromadb", "embedding", "sentence transformer", "knowledge base retrieval"]):
        return "RAG"

    # LLM / Transformer
    if any(k in q_lower for k in ["qwen", "qwen2.5", "transformer", "large language model", "llm", "language model", "attention mechanism", "fine-tun"]):
        return "LLM"

    # General EC2
    if any(k in q_lower for k in ["ec2", "instance", "ami", "key pair", "ebs", "elastic compute", "instance type", "t2", "t3", "m5"]):
        return "EC2"

    # Troubleshooting (general)
    if any(k in q_lower for k in ["troubleshoot", "error", "502", "503", "404", "check", "diagnose", "blocked", "not working", "failed"]):
        return "TROUBLESHOOTING"

    # CloudOps Product
    if any(k in q_lower for k in ["cloudops", "confidence score", "diagnosis", "troubleshooter", "support agent", "probable root cause", "evidence", "6-field"]):
        return "PRODUCT"

    # AWS General
    if any(k in q_lower for k in ["aws", "amazon web services", "region", "availability zone", "s3", "rds", "lambda", "load balancer", "alb", "ssm"]):
        return "AWS"

    return "GENERAL_TECHNICAL"


def query_support_knowledge(query: str, top_k: int = 4, min_score: float = 0.30) -> Tuple[List[Dict[str, Any]], str]:
    """
    Enhanced Entity-Aware Hybrid Support RAG Retrieval:
    1. Normalizes query & classifies fine-grained intent.
    2. Retrieves candidate pool (top 15) from ChromaDB.
    3. Applies comprehensive entity-aware scoring:
       final = 0.55 * semantic + 0.25 * entity_boost + 0.20 * keyword_boost
    4. Enforces minimum score threshold & deduplicates by document title.
    5. Returns top top_k chunks + intent string.
    """
    if not query or not query.strip():
        return [], "UNKNOWN"

    intent = classify_query_intent(query)
    logger.info(f"Query: '{query}' -> Intent: '{intent}'")

    if intent in ["GREETING", "OUT_OF_SCOPE"]:
        return [], intent

    collection = _init_support_collection()
    if collection is None or collection.count() == 0:
        logger.warning(f"Support ChromaDB collection '{COLLECTION_NAME}' is empty or unavailable.")
        return [], intent

    embedder = _get_embedder()
    if embedder is None:
        logger.error("Embedding service unavailable for Support RAG retrieval.")
        return [], intent

    # Normalize query for embedding quality
    norm_query = normalize_support_query(query)

    try:
        query_vector = embedder.encode(norm_query, convert_to_numpy=True, normalize_embeddings=True).tolist()

        # Retrieve larger candidate pool
        candidate_count = min(15, collection.count())
        res = collection.query(
            query_embeddings=[query_vector],
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"]
        )

        candidates = []
        if res and res.get("documents") and res["documents"][0]:
            docs = res["documents"][0]
            metas = res["metadatas"][0]
            dists = res["distances"][0] if res.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                semantic_score = max(0.0, min(1.0, 1.0 - float(dist)))
                doc_title = (meta.get("document_title") or meta.get("title") or
                             meta.get("source", "Support Document"))
                category = meta.get("category", "general")
                doc_lower = f"{doc_title} {doc}".lower()
                q_lower = norm_query.lower()
                orig_lower = query.lower()

                # ================================================================
                # ENTITY-AWARE SCORING: semantic + entity + keyword boosts
                # ================================================================
                entity_boost = 0.0
                keyword_boost = 0.0

                # --- VPC ---
                if any(k in orig_lower for k in ["vpc", "virtual private cloud"]):
                    if "virtual private cloud" in doc_lower or "vpc" in doc_lower[:200]:
                        entity_boost += 0.45
                    if "nacl" in doc_lower and "vpc" not in doc_lower[:100]:
                        entity_boost -= 0.20  # SG/NACL doc, not VPC-focused

                # --- Subnet ---
                if any(k in orig_lower for k in ["subnet", "public subnet", "private subnet"]):
                    if "subnet" in doc_lower and ("route table" in doc_lower or "cidr" in doc_lower):
                        entity_boost += 0.40
                    if "nacl" in doc_lower and "subnet" not in doc_title.lower():
                        entity_boost -= 0.15

                # --- Route Table ---
                if any(k in orig_lower for k in ["route table", "routing table"]):
                    if "route table" in doc_lower:
                        entity_boost += 0.40

                # --- NACL ---
                if any(k in orig_lower for k in ["nacl", "network access control"]):
                    if "nacl" in doc_lower or "network access control" in doc_lower:
                        entity_boost += 0.40
                    else:
                        entity_boost -= 0.30

                # --- NAT Gateway ---
                if any(k in orig_lower for k in ["nat gateway", "nat "]):
                    if "nat gateway" in doc_lower:
                        entity_boost += 0.40
                    elif "ec2 instance" in orig_lower:
                        entity_boost -= 0.10  # don't boost NAT for general EC2 Q

                # --- Internet Gateway ---
                if any(k in orig_lower for k in ["internet gateway", "igw"]):
                    if "internet gateway" in doc_lower or "igw" in doc_lower:
                        entity_boost += 0.40

                # --- Security Group ---
                if any(k in orig_lower for k in ["security group", "inbound rule", "sg rule"]):
                    if "security group" in doc_lower:
                        entity_boost += 0.35
                    # "who changed SG" should boost CloudTrail, not NACL
                    if "who changed" in orig_lower or "who modified" in orig_lower:
                        if "cloudtrail" in doc_lower:
                            entity_boost += 0.50
                        elif "security group" in doc_lower and "cloudtrail" not in doc_lower:
                            entity_boost -= 0.20

                # --- CloudTrail specific ---
                if any(k in orig_lower for k in ["cloudtrail", "who changed", "who deleted", "audit log", "api activity", "authorizesecuritygroup"]):
                    if "cloudtrail" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.20

                # --- CloudWatch ---
                if any(k in orig_lower for k in ["cloudwatch", "metric", "alarm", "cpuutilization", "cpu alarm"]):
                    if "cloudwatch" in doc_lower:
                        entity_boost += 0.40

                # --- IAM ---
                if any(k in orig_lower for k in ["iam", "identity access", "iam role", "iam user", "iam policy"]):
                    if "iam" in doc_lower or "identity and access management" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.30  # strong penalty for IAM query hitting non-IAM doc

                # --- DNS ---
                if any(k in orig_lower for k in ["dns", "domain name system", "route 53", "route53", "hosted zone"]):
                    if "dns" in doc_lower or "route 53" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.25

                # --- RDP / Windows ---
                if any(k in orig_lower for k in ["rdp", "remote desktop", "3389", "windows ec2", "windows instance"]):
                    if "rdp" in doc_lower or "remote desktop" in doc_lower or "3389" in doc_lower:
                        entity_boost += 0.55
                    else:
                        entity_boost -= 0.30

                # --- IIS ---
                if any(k in orig_lower for k in ["iis", "w3svc", "internet information services"]):
                    if "iis" in doc_lower or "w3svc" in doc_lower:
                        entity_boost += 0.55
                    else:
                        entity_boost -= 0.20

                # --- Docker ---
                if any(k in orig_lower for k in ["docker", "container", "dockerfile"]):
                    if "docker" in doc_lower or "container" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.20

                # --- Kubernetes ---
                if any(k in orig_lower for k in ["kubernetes", "k8s", "kubectl", "pod "]):
                    if "kubernetes" in doc_lower or "k8s" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.20

                # --- Terraform ---
                if any(k in orig_lower for k in ["terraform", "infrastructure as code", "iac", "hcl"]):
                    if "terraform" in doc_lower:
                        entity_boost += 0.50
                    else:
                        entity_boost -= 0.20

                # --- CI/CD ---
                if any(k in orig_lower for k in ["ci/cd", "cicd", "continuous integration", "github actions", "jenkins"]):
                    if "ci/cd" in doc_lower or "cicd" in doc_lower or "github actions" in doc_lower or "pipeline" in doc_lower:
                        entity_boost += 0.45

                # --- QLoRA ---
                if any(k in orig_lower for k in ["qlora", "lora", "quantization", "4-bit", "nf4"]):
                    if "qlora" in doc_lower or "lora" in doc_lower:
                        entity_boost += 0.45

                # --- RAG ---
                if any(k in orig_lower for k in ["rag", "retrieval augmented", "chromadb", "vector store"]):
                    if "rag" in doc_lower or "chromadb" in doc_lower or "retrieval" in doc_lower:
                        entity_boost += 0.40

                # --- EC2 Unreachable ---
                if any(k in orig_lower for k in ["unreachable", "not reachable", "website down", "cannot reach"]):
                    if "unreachable" in doc_lower or "troubleshooting" in doc_lower:
                        entity_boost += 0.35

                # --- High CPU ---
                if any(k in orig_lower for k in ["high cpu", "cpu spike", "cpu 100", "cpu usage"]):
                    if "cpu" in doc_lower and ("utilization" in doc_lower or "troubleshoot" in doc_lower):
                        entity_boost += 0.35

                # --- EC2 Creation ---
                if ("create" in orig_lower or "launch" in orig_lower) and "ec2" in orig_lower:
                    if "creation" in doc_lower or "launch guide" in doc_lower:
                        entity_boost += 0.40
                    if "nat gateway" in doc_lower and "ec2 creation" not in doc_lower:
                        entity_boost -= 0.40

                # --- AMI ---
                if "ami" in orig_lower or "amazon machine image" in orig_lower:
                    if "ami" in doc_lower or "amazon machine image" in doc_lower:
                        entity_boost += 0.35

                # --- Port-specific keyword boosts ---
                if "port 80" in orig_lower and "port 80" in doc_lower:
                    keyword_boost += 0.25
                if "port 443" in orig_lower and "port 443" in doc_lower:
                    keyword_boost += 0.25
                if "port 3389" in orig_lower and "3389" in doc_lower:
                    keyword_boost += 0.30
                if "port 22" in orig_lower and "port 22" in doc_lower:
                    keyword_boost += 0.20

                # Final composite score
                final_score = round(
                    min(1.0, max(0.0,
                        0.55 * semantic_score +
                        0.25 * max(0.0, min(1.0, entity_boost)) +
                        0.20 * max(0.0, min(1.0, keyword_boost))
                    )), 4
                )

                # Entity fallback: if strong entity match, allow through even if score low
                has_strong_entity = (
                    ("iam" in orig_lower and ("iam" in doc_lower or "identity and access" in doc_lower)) or
                    ("dns" in orig_lower and "dns" in doc_lower) or
                    ("rdp" in orig_lower and ("rdp" in doc_lower or "3389" in doc_lower)) or
                    ("docker" in orig_lower and "docker" in doc_lower) or
                    ("terraform" in orig_lower and "terraform" in doc_lower) or
                    ("kubernetes" in orig_lower and "kubernetes" in doc_lower)
                )

                effective_min = 0.20 if has_strong_entity else min_score
                raw_score = max(final_score, semantic_score * 0.55)

                if raw_score >= effective_min or has_strong_entity:
                    candidates.append({
                        "title": doc_title,
                        "category": category,
                        "content": doc,
                        "score": raw_score,
                        "relevance": raw_score,
                        "source": meta.get("source", "")
                    })

        # Sort by score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)

        # Deduplicate by document title
        seen_titles = set()
        deduped_results = []
        for item in candidates:
            title_key = item["title"].lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduped_results.append(item)
            if len(deduped_results) >= top_k:
                break

        logger.info(
            f"Retrieval done: {len(deduped_results)} chunks. "
            f"Top score: {deduped_results[0]['score'] if deduped_results else 'N/A'}"
        )
        return deduped_results, intent

    except Exception as e:
        logger.error(f"Failed to query support knowledge base '{COLLECTION_NAME}': {e}")
        return [], intent
