# AWS EC2 — Amazon Elastic Compute Cloud Fundamentals

## 1. What is Amazon EC2?

**Amazon EC2 (Elastic Compute Cloud)** is AWS's core virtual machine service that provides resizable, on-demand compute capacity in the cloud. EC2 instances are virtual servers you rent by the second or hour to run any workload — web servers, databases, ML training, data processing, or any custom application.

---

## 2. EC2 Instance Types

EC2 offers hundreds of instance types optimized for different workloads:

| Family | Optimized For | Examples |
| :--- | :--- | :--- |
| General Purpose | Balanced CPU/RAM | t3.micro, t3.medium, m5.large |
| Compute Optimized | CPU-intensive | c5.xlarge, c6g.2xlarge |
| Memory Optimized | RAM-intensive workloads | r5.large, x1e.xlarge |
| Storage Optimized | High I/O, large datasets | i3.large, d2.xlarge |
| GPU | ML training, graphics | p3.2xlarge, g4dn.xlarge |
| Burstable | Variable CPU with credits | t2.micro, t3.micro (Free Tier) |

---

## 3. EC2 Instance States

| State | Description |
| :--- | :--- |
| **pending** | Instance is starting — not yet billable |
| **running** | Instance is active and billable |
| **stopping** | Instance is shutting down (not terminated) |
| **stopped** | Instance is off — storage preserved, not billed for compute |
| **shutting-down** | Instance is being terminated |
| **terminated** | Instance permanently deleted — data lost |

**Note**: A `stopped` instance retains its EBS volumes and can be restarted. A `terminated` instance is permanently deleted.

---

## 4. Amazon Machine Image (AMI)

An **AMI (Amazon Machine Image)** is a template that contains the operating system, application server, and application configuration needed to launch an EC2 instance.

### Types of AMIs
- **AWS-provided AMIs**: Amazon Linux 2023, Ubuntu 22.04 LTS, Windows Server 2022
- **AWS Marketplace AMIs**: Pre-configured commercial or community AMIs
- **Custom AMIs**: Snapshots of your configured EC2 instance for quick redeployment

### Key AMI Properties
- AMIs are region-specific (must copy to other regions for multi-region deployments)
- AMIs reference EBS snapshots for root volume content
- You can create an AMI from a running or stopped instance

---

## 5. Key Pair

An **EC2 Key Pair** consists of a public key stored on the EC2 instance and a private key (`.pem` file) kept by you.

- **Linux instances**: Use the private key for SSH authentication: `ssh -i key.pem ec2-user@<IP>`
- **Windows instances**: Use the private key to decrypt the Administrator password for RDP

The private key cannot be recovered after creation — store it securely.

---

## 6. EBS (Elastic Block Store)

**EBS** is the persistent block storage service for EC2 instances. Each EC2 instance has at least one EBS root volume.

| Volume Type | Use Case | Max IOPS |
| :--- | :--- | :--- |
| gp3 (General Purpose SSD) | Default, balanced | 16,000 IOPS |
| gp2 (General Purpose SSD) | Legacy default | 16,000 IOPS |
| io2 Block Express | High-performance databases | 256,000 IOPS |
| st1 (Throughput HDD) | Sequential large data | 500 MB/s |
| sc1 (Cold HDD) | Infrequent access | 250 MB/s |

---

## 7. EC2 Instance Metadata

EC2 instances can access their own configuration at `http://169.254.169.254/latest/meta-data/`:
- `instance-id` — The EC2 instance ID
- `public-ipv4` — Current public IP address
- `iam/security-credentials/` — Temporary IAM role credentials
- `user-data` — Bootstrap script passed at launch

---

## 8. EC2 Pricing Models

| Model | Description | Best For |
| :--- | :--- | :--- |
| On-Demand | Pay per second, no commitment | Development, unpredictable workloads |
| Reserved | 1 or 3-year commitment, 40-75% discount | Stable production workloads |
| Spot | Bid on spare capacity, 70-90% discount | Fault-tolerant, interruptible workloads |
| Dedicated Host | Physical server for compliance | License compliance, regulatory |

---

## 9. Common EC2 Mistakes

- Stopping instance and losing public IP (use Elastic IP for stable addressing)
- Not using IAM instance profile — hardcoding credentials in application code
- Root volume too small — OS and application fill disk, instance becomes unresponsive
- Wrong instance type — using t2.micro for CPU-intensive workloads causes CPU credit exhaustion
- Not enabling termination protection on critical instances
