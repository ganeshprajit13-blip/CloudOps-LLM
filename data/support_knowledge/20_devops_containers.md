# Docker and Kubernetes — Containers and Container Orchestration

## 1. What is Docker?

**Docker** is an open-source platform for building, packaging, and running applications in **containers**. A container is a lightweight, portable, isolated unit that packages application code together with its dependencies, runtime, libraries, and configuration.

### Why Use Docker?
- **Consistency**: "Works on my machine" problems eliminated — container runs the same everywhere
- **Isolation**: Each container runs in its own isolated namespace
- **Speed**: Containers start in milliseconds (vs minutes for VMs)
- **Portability**: Run on local laptop, on-premises server, or AWS EC2/ECS/EKS

---

## 2. Docker Core Concepts

| Concept | Description |
| :--- | :--- |
| **Image** | Read-only template with application + dependencies (built from Dockerfile) |
| **Container** | Running instance of an image |
| **Dockerfile** | Text file with instructions to build an image (FROM, RUN, COPY, EXPOSE, CMD) |
| **Docker Hub** | Public registry for Docker images |
| **Amazon ECR** | AWS private Docker image registry (Elastic Container Registry) |
| **Docker Compose** | Tool for defining multi-container applications |
| **Volume** | Persistent storage for containers |
| **Network** | Container-to-container communication |

---

## 3. Example Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Common commands:
```bash
docker build -t my-app:latest .
docker run -p 8000:8000 my-app:latest
docker ps                         # List running containers
docker logs <container-id>        # View container logs
docker exec -it <id> /bin/bash    # Enter container shell
```

---

## 4. What is Kubernetes?

**Kubernetes (K8s)** is an open-source container orchestration platform that automates deploying, scaling, and managing containerized applications across a cluster of nodes.

### Why Kubernetes?
- Automatically restarts failed containers
- Load balances traffic across container replicas
- Scales containers up/down based on demand
- Rolls out updates with zero downtime

---

## 5. Kubernetes Core Concepts

| Concept | Description |
| :--- | :--- |
| **Pod** | Smallest deployable unit — one or more containers sharing network/storage |
| **Deployment** | Declarative configuration for running Pods with scaling and update strategy |
| **Service** | Stable network endpoint exposing Pods (ClusterIP, NodePort, LoadBalancer) |
| **Namespace** | Virtual cluster isolation within a K8s cluster |
| **ConfigMap** | External configuration for containers |
| **Secret** | Sensitive data (passwords, tokens) for containers |
| **Ingress** | HTTP/HTTPS routing rules for external access |
| **Node** | Worker machine (EC2 instance in AWS) running Pods |
| **Control Plane** | Master components (API server, scheduler, etcd) |

---

## 6. AWS Kubernetes Services

| Service | Description |
| :--- | :--- |
| **Amazon EKS** | Managed Kubernetes service — AWS manages the control plane |
| **Amazon ECS** | AWS-native container orchestration (simpler than Kubernetes) |
| **AWS Fargate** | Serverless containers — no EC2 nodes to manage |
| **Amazon ECR** | Managed Docker image registry |

---

## 7. Docker vs Kubernetes

| Aspect | Docker | Kubernetes |
| :--- | :--- | :--- |
| Purpose | Build and run containers | Orchestrate containers at scale |
| Use case | Single host, development | Production, multi-node clusters |
| Scaling | Manual | Automatic (HPA) |
| Self-healing | No | Yes (restarts failed pods) |
| Complexity | Simple | Complex |

Docker builds and packages containers. Kubernetes runs and orchestrates them at scale.

---

## 8. Common Docker/Kubernetes Mistakes

- Not using `.dockerignore` — unnecessarily large images
- Running containers as root — security risk
- Not setting resource limits on Pods — noisy neighbor problem in Kubernetes
- Using `latest` tag in production — non-deterministic deployments
- Not configuring Pod readiness probes — unhealthy Pods receive traffic
