# AWS DNS and Route 53

## 1. What is DNS?

**DNS (Domain Name System)** is the internet's system for translating human-readable domain names (e.g., `www.example.com`) into machine-readable IP addresses (e.g., `54.210.12.34`) that computers use to route network traffic.

DNS resolution happens automatically when you type a URL in a browser or make an API call using a hostname.

### DNS Resolution Steps
1. Browser checks local cache
2. Queries local DNS resolver (ISP or configured DNS server)
3. Resolver queries Root Name Servers → TLD Name Servers (e.g., `.com`)
4. TLD directs to Authoritative Name Server for `example.com`
5. Authoritative NS returns the IP address
6. Browser connects to the IP

---

## 2. Common DNS Record Types

| Record | Purpose | Example |
| :--- | :--- | :--- |
| A | Maps domain to IPv4 address | `api.example.com → 54.210.12.34` |
| AAAA | Maps domain to IPv6 address | `api.example.com → 2001:db8::1` |
| CNAME | Alias to another domain name | `www.example.com → example.com` |
| MX | Mail server records | `example.com → mail.example.com` |
| TXT | Text verification records | SPF, DKIM, domain verification |
| NS | Name server for the zone | `example.com → ns1.awsdns-01.com` |
| SOA | Start of Authority | Zone metadata |

---

## 3. What is Amazon Route 53?

**Amazon Route 53** is AWS's scalable, highly available DNS web service. It provides:
- **Domain registration** — Register new domain names
- **DNS routing** — Host DNS zones and manage records
- **Health checks** — Monitor endpoint health and route traffic accordingly
- **Traffic policies** — Latency-based, geolocation, failover, weighted routing

---

## 4. Route 53 Routing Policies

| Policy | Use Case |
| :--- | :--- |
| Simple | Single resource, no health checks |
| Weighted | A/B testing, traffic splitting |
| Latency-based | Route to lowest-latency AWS region |
| Failover | Active-passive failover using health checks |
| Geolocation | Route based on user's geographic location |
| Multivalue Answer | Returns multiple IPs for basic load balancing |

---

## 5. VPC DNS Settings

Each VPC has two DNS settings that must both be enabled for EC2 hostname resolution to work:

- **Enable DNS hostnames**: Assigns public DNS hostnames (e.g., `ec2-54-210-12-34.compute-1.amazonaws.com`) to EC2 instances with public IPs
- **Enable DNS resolution**: Allows instances in the VPC to use the AWS-provided DNS resolver at `169.254.169.253`

Without these enabled, EC2 instances may not resolve AWS service endpoints correctly.

---

## 6. Private Hosted Zones

A **Private Hosted Zone** in Route 53 allows you to create DNS records that are only resolvable from within specific VPCs. Useful for:
- Internal microservice routing (e.g., `db.internal → 10.0.10.5`)
- Cross-account internal DNS without exposing to the public internet

---

## 7. Common DNS Issues

- DNS record pointing to old IP after EC2 replacement (dynamic IP vs Elastic IP)
- CNAME chain too long — exceeds browser limits
- TTL too high — DNS changes propagate slowly after IP changes
- Route 53 health check failing — traffic not routed to healthy instance
- VPC DNS settings disabled — EC2 cannot resolve service endpoints
- Missing `public DNS hostname` on EC2 — VPC DNS hostname setting not enabled
