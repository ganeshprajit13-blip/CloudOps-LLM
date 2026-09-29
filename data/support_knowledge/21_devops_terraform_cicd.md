# Terraform and CI/CD — Infrastructure as Code and DevOps Pipelines

## 1. What is Terraform?

**Terraform** is an open-source Infrastructure as Code (IaC) tool by HashiCorp that lets you define and provision cloud infrastructure using a declarative configuration language (HCL — HashiCorp Configuration Language).

With Terraform, you describe the desired state of your infrastructure in `.tf` files and Terraform calculates and applies the changes needed to reach that state.

---

## 2. Why Use Terraform?

- **Repeatability**: Deploy identical environments (dev/staging/prod) from the same code
- **Version control**: Infrastructure changes tracked in Git just like application code
- **Multi-cloud**: Supports AWS, Azure, GCP, Kubernetes, and 1000+ providers
- **State management**: Tracks deployed resource state in a `terraform.tfstate` file
- **Plan before apply**: Preview changes before they affect real infrastructure

---

## 3. Terraform Core Concepts

| Concept | Description |
| :--- | :--- |
| **Provider** | Plugin for a platform (e.g., `hashicorp/aws`) |
| **Resource** | Infrastructure component to manage (e.g., `aws_instance`, `aws_security_group`) |
| **Data Source** | Read existing infrastructure without managing it |
| **Variable** | Input parameter to make configs reusable |
| **Output** | Values exported after apply (e.g., instance IP) |
| **State** | `terraform.tfstate` — records current deployed state |
| **Module** | Reusable group of resources (e.g., VPC module) |
| **Backend** | Where state is stored (local or remote, e.g., S3 + DynamoDB lock) |

---

## 4. Terraform Workflow

```bash
terraform init          # Download providers and modules
terraform plan          # Preview changes (no modification)
terraform apply         # Apply changes to real infrastructure
terraform destroy       # Tear down all managed resources
terraform fmt           # Format .tf files
terraform validate      # Validate configuration syntax
```

---

## 5. Example Terraform AWS EC2

```hcl
provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "web" {
  ami           = "ami-0c02fb55956c7d316"   # Amazon Linux 2023
  instance_type = "t3.micro"
  key_name      = "my-key-pair"

  vpc_security_group_ids = [aws_security_group.web_sg.id]
  subnet_id              = "subnet-0abc1234"

  tags = {
    Name = "web-server-prod"
  }
}
```

---

## 6. What is CI/CD?

**CI/CD (Continuous Integration / Continuous Delivery)** is a DevOps practice of automating the software development lifecycle:

- **Continuous Integration (CI)**: Automatically build, test, and validate code on every commit
- **Continuous Delivery (CD)**: Automatically deploy tested code to staging/production environments

### Common CI/CD Tools
| Tool | Type | Use |
| :--- | :--- | :--- |
| GitHub Actions | Cloud-native | CI/CD in GitHub repos |
| GitLab CI | Built-in | GitLab repository pipelines |
| Jenkins | Self-hosted | Legacy and enterprise CI |
| AWS CodePipeline | AWS-native | End-to-end AWS CI/CD |
| AWS CodeBuild | AWS-native | Managed build service |
| AWS CodeDeploy | AWS-native | EC2/Lambda deployment |
| CircleCI | Cloud SaaS | Fast CI/CD pipelines |

---

## 7. Example GitHub Actions CI/CD Pipeline

```yaml
name: Deploy to AWS EC2

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -t my-app .
      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS ...
          docker push $ECR_REGISTRY/my-app:latest
      - name: Deploy to EC2 via SSM
        run: aws ssm send-command --document-name "AWS-RunShellScript" ...
```

---

## 8. Terraform State Management Best Practices

- Store state remotely in **S3** with **DynamoDB locking** (prevents concurrent apply conflicts)
- Never commit `terraform.tfstate` to Git (contains secrets)
- Use **Terraform workspaces** for environment isolation (dev/staging/prod)
- Use **Terraform Cloud** or **Atlantis** for team collaboration with plan/apply approvals

---

## 9. Common Terraform/CI/CD Mistakes

- Running `terraform apply` in production without `terraform plan` review
- Storing secrets in `.tf` files — use AWS Secrets Manager or environment variables
- Not using remote state — state conflicts in team environments
- CI/CD pipeline not running tests before deployment
- Hardcoding AWS region or account IDs — use variables for reusability
