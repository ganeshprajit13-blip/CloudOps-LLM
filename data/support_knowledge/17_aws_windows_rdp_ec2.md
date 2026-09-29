# AWS Windows EC2 and RDP (Remote Desktop Protocol)

## 1. What is RDP?

**RDP (Remote Desktop Protocol)** is Microsoft's proprietary protocol for graphical remote desktop access to Windows computers. RDP operates on **TCP port 3389** (and optionally UDP 3389).

On AWS, you connect to a **Windows EC2 instance** using RDP to access the Windows desktop environment, manage IIS, run PowerShell, and perform administrative tasks.

---

## 2. RDP Connection Requirements

To successfully connect to a Windows EC2 instance via RDP, ALL of the following must be true:

1. **EC2 instance state** = `running`
2. **Instance type** must support Windows (e.g., t2.micro, t3.medium)
3. **Security Group inbound rule**: TCP port 3389 allowed from your IP (or `0.0.0.0/0` for testing)
4. **Public IP or Elastic IP** assigned to the instance (for internet access)
5. **Route Table**: Public subnet with `0.0.0.0/0 → igw-xxxxxxxx`
6. **Windows password**: Retrieved using your EC2 key pair private key (.pem file)
7. **NACL**: Allow TCP 3389 inbound and ephemeral ports (1024-65535) outbound

---

## 3. How to Connect to Windows EC2 via RDP

### Step 1: Get the Windows Password
1. In AWS Console, go to EC2 > Instances
2. Select your Windows instance
3. Click **Connect** > **RDP client** tab
4. Click **Get password**
5. Upload your `.pem` private key file
6. Click **Decrypt password** — copy the Administrator password

### Step 2: Download the RDP File or Use Remote Desktop App
- Click **Download remote desktop file** — opens Microsoft Remote Desktop
- Or manually enter: `<Public-IP>:3389` in Remote Desktop Connection

### Step 3: Connect
- Username: `Administrator`
- Password: the decrypted password from Step 1

---

## 4. RDP Troubleshooting Checklist

### Cannot connect at all (connection timeout)?
1. Check Security Group: Is port 3389 open inbound? Is your IP correct?
2. Check instance state: Is it `running`?
3. Check public IP: Does instance have a public IP or Elastic IP?
4. Check route table: Is there a `0.0.0.0/0 → igw-xxx` route in the subnet?
5. Check NACL: Are port 3389 inbound and ephemeral ports outbound allowed?
6. Check Windows Firewall: Is RDP (port 3389) allowed in Windows Firewall rules?

### Connection refused (port 3389 refusing)?
- Windows Remote Desktop Service (TermService) may be stopped
- Check via SSM: `Get-Service TermService`
- Start via SSM: `Start-Service TermService`
- Ensure "Remote Desktop" is enabled in Windows System Properties

### Password incorrect?
- Ensure you used the correct `.pem` private key
- The key must match the key pair used when launching the instance
- Password decryption can take 4-6 minutes after instance launch

---

## 5. RDP in CloudOps

CloudOps detects RDP connectivity issues through:
- `missing_rdp_rule` signal — Security Group missing TCP port 3389 inbound rule
- `stopped_instance` signal — Instance not running
- `missing_igw_route` signal — Route table not routing to internet

The AI Troubleshooter checks all RDP prerequisites automatically and reports specific evidence.

---

## 6. Windows EC2 Key Points

- Windows AMIs include **Windows Server 2019**, **2022**, and **2016**
- Initial Windows password setup requires ~4-6 minutes after first boot
- Windows EC2 instances use **EC2Launch** (Server 2019+) or **EC2Config** (older) for initialization
- **SSM Session Manager** can be used for browser-based PowerShell access without opening port 3389
- **Elastic IP** ensures your IP stays stable across instance stops/starts

---

## 7. Common Windows EC2 / RDP Mistakes

- Security Group missing port 3389 inbound rule — most common cause of RDP failure
- Using wrong private key (.pem) when decrypting password
- Instance in private subnet with no public IP — RDP impossible from internet
- Windows Firewall blocking RDP internally — override via SSM PowerShell
- Connecting to wrong public IP (Elastic IP vs auto-assigned IP differ after stop/start)
