# AWS EC2 Instance Creation & Launch Guide

## What is an Amazon EC2 Instance?
Amazon Elastic Compute Cloud (Amazon EC2) provides scalable computing capacity in the AWS Cloud. Launching an EC2 instance allows you to deploy virtual servers without upfront hardware investments.

## Step-by-Step Guide to Create and Launch an EC2 Instance

### Step 1: Open the AWS EC2 Console
1. Sign in to the AWS Management Console.
2. Navigate to the **EC2 Dashboard** and click **Launch Instance**.

### Step 2: Name and Select an Amazon Machine Image (AMI)
1. Enter a descriptive Name tag for your instance (e.g., `web-server-prod`).
2. Choose an **AMI** (operating system template), such as Amazon Linux 2023, Ubuntu Server 22.04 LTS, or Windows Server 2022.

### Step 3: Select Instance Type
1. Choose an instance type based on CPU, memory, and networking requirements:
   - `t2.micro` or `t3.micro` for general-purpose/free-tier testing.
   - `c5` or `c6i` series for compute-intensive workloads.
   - `m5` or `m6i` series for balanced memory and CPU.

### Step 4: Configure Key Pair for SSH / RDP Access
1. Select an existing key pair or click **Create new key pair**.
2. For Linux instances (SSH), download the `.pem` or `.ppk` private key file.
3. For Windows instances (RDP), use the key pair to decrypt the Administrator password.

### Step 5: Network Settings (VPC, Subnet, and Public IP)
1. Select your target **VPC** (Virtual Private Cloud).
2. Select the target **Subnet** (Public Subnet if public internet access is required, or Private Subnet for internal application tiers).
3. Set **Auto-assign Public IP** to *Enable* if the instance is in a public subnet and requires direct inbound/outbound internet connectivity.

### Step 6: Configure Security Group (Firewall Rules)
1. Choose an existing Security Group or create a new one.
2. Add inbound firewall rules:
   - **SSH (Port 22)**: Allow from your specific IP address for Linux management.
   - **HTTP (Port 80) / HTTPS (Port 443)**: Allow from `0.0.0.0/0` if hosting a public web server.
   - **RDP (Port 3389)**: Allow from your specific IP address for Windows remote desktop access.

### Step 7: Configure Storage (EBS Volumes)
1. Set the root volume size (e.g., 8 GB for Linux, 30 GB for Windows).
2. Select volume type (e.g., General Purpose SSD `gp3` or `gp2`).
3. Add additional EBS data volumes if required.

### Step 8: Advanced Details & IAM Role
1. (Optional) Attach an **IAM Role** (e.g., `AmazonSSMManagedInstanceCore`) to enable AWS Systems Manager (SSM) Session Manager without opening SSH/RDP ports.
2. Add user data shell scripts for automated post-launch bootstrap configuration.

### Step 9: Review and Launch
1. Review summary settings and click **Launch Instance**.
2. Monitor status checks in the EC2 Console until state transitions to `running` with `2/2 checks passed`.

### Step 10: Connecting to the EC2 Instance
- **Linux via SSH**: `ssh -i key.pem ec2-user@<Public-IP>`
- **Linux via AWS SSM**: Connect directly via AWS Console or CLI using `aws ssm start-session`.
- **Windows via RDP**: Connect using Remote Desktop Client to `<Public-IP>:3389`.

> **CloudOps Advisory Disclaimer**: The CloudOps Support Agent provides technical guidance and step-by-step procedures for AWS resource management. It does **not** automatically execute or launch AWS resources on your behalf.
