# Networking Basics — TCP/IP, Ports, and Protocols

## 1. TCP/IP Networking Model

**TCP/IP** is the fundamental networking protocol suite used by the internet and virtually all modern networks. It defines how data is packaged, addressed, transmitted, routed, and received.

### Key Layers
| Layer | Name | Examples |
| :--- | :--- | :--- |
| 4 | Application | HTTP, HTTPS, SSH, RDP, DNS, FTP |
| 3 | Transport | TCP, UDP |
| 2 | Internet | IP (IPv4, IPv6), ICMP |
| 1 | Network Access | Ethernet, Wi-Fi |

---

## 2. TCP vs UDP

| Feature | TCP | UDP |
| :--- | :--- | :--- |
| Connection | Connection-oriented (3-way handshake) | Connectionless |
| Reliability | Guaranteed delivery, ordered | No guarantee, may drop packets |
| Speed | Slower (overhead for reliability) | Faster (low overhead) |
| Use cases | HTTP/HTTPS, SSH, RDP, databases | DNS, video streaming, gaming |
| Error checking | Yes (retransmit lost packets) | Minimal |

---

## 3. Common Network Ports

| Port | Protocol | Service |
| :--- | :--- | :--- |
| 22 | TCP | SSH — Secure Shell (Linux admin) |
| 80 | TCP | HTTP — Web traffic (unencrypted) |
| 443 | TCP | HTTPS — Web traffic (TLS encrypted) |
| 3389 | TCP | RDP — Windows Remote Desktop |
| 3306 | TCP | MySQL database |
| 5432 | TCP | PostgreSQL database |
| 6379 | TCP | Redis cache |
| 27017 | TCP | MongoDB database |
| 8080 | TCP | HTTP alternate / app servers |
| 53 | TCP/UDP | DNS name resolution |
| 25 | TCP | SMTP email (outbound) |
| 443 | TCP | HTTPS (also used by many APIs) |
| 1024-65535 | TCP | Ephemeral ports (return traffic) |

---

## 4. Port 80 — HTTP

Port 80 is the default port for **HTTP (HyperText Transfer Protocol)** — unencrypted web traffic.

In AWS Security Groups:
- Open TCP port 80 inbound from `0.0.0.0/0` for public web access
- If port 80 is blocked, users get connection timeout when accessing your website

In CloudOps: `missing_port_80_rule` signal = Security Group missing port 80 inbound rule.

---

## 5. Port 443 — HTTPS

Port 443 is the default port for **HTTPS (HTTP Secure)** — web traffic encrypted with TLS/SSL.

In AWS Security Groups:
- Open TCP port 443 inbound from `0.0.0.0/0` for secure web access
- Requires an SSL/TLS certificate on your web server (e.g., Let's Encrypt, AWS Certificate Manager)
- If port 443 is blocked, browsers show "connection refused" or "SSL_ERROR_RX_RECORD_TOO_LONG"

In CloudOps: `missing_port_443_rule` signal = Security Group missing port 443 inbound rule.

---

## 6. Port 3389 — RDP

Port 3389 is the **RDP (Remote Desktop Protocol)** port for Windows remote desktop access.

In AWS Security Groups:
- Open TCP port 3389 inbound from your specific IP (e.g., `203.0.113.5/32`) for security
- Never open to `0.0.0.0/0` in production — brute-force risk
- If blocked, RDP connection times out entirely

---

## 7. Port 22 — SSH

Port 22 is the **SSH (Secure Shell)** port for command-line access to Linux EC2 instances.

Best practice: Restrict inbound SSH to known IPs or use AWS SSM Session Manager (no port 22 required).

---

## 8. Ephemeral Ports

**Ephemeral ports** (1024-65535) are temporary ports assigned by the OS for outbound connections. When a client connects to port 80 on your server, the server's response goes back to the client's ephemeral port.

In **NACLs** (stateless), you must explicitly allow outbound ephemeral port range (1024-65535) alongside the inbound port rules — otherwise clients cannot receive response traffic. Security Groups handle this automatically (stateful).

---

## 9. CIDR Notation

**CIDR (Classless Inter-Domain Routing)** notation expresses IP ranges:
- `0.0.0.0/0` — All IPv4 addresses (any source)
- `10.0.0.0/8` — All 10.x.x.x addresses (16M IPs)
- `10.0.1.0/24` — 10.0.1.0 through 10.0.1.255 (256 IPs)
- `203.0.113.5/32` — Single specific IP address

The `/number` suffix indicates how many bits are fixed in the prefix — higher number = smaller range.
