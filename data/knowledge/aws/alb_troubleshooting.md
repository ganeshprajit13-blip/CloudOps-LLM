# Application Load Balancer (ALB) & Health Check Troubleshooting Guide

*Project-Created Authoritative Troubleshooting Knowledge*

## Application Load Balancer (ALB) Architecture
An ALB distributes incoming traffic across target groups consisting of EC2 instances, containers, or IP addresses.

## Distinguishing ALB vs EC2 vs Application Failures

### 1. HTTP 502 Bad Gateway
- **Meaning**: The load balancer received an invalid response or reset from the target instance.
- **Root Causes**:
  - Web application server (e.g. Nginx, Gunicorn, Node.js) crashed or is not listening on the registered target port.
  - Target instance closed TCP connection unexpectedly (TCP RST or connection refused).
  - Target returned malformed HTTP headers.
- **Diagnostic Action**: Inspect application log files on EC2 instances (`/var/log/nginx/error.log`, systemd journalctl) and check if target process is listening (`netstat -tuln` or `ss -tulpn`).

### 2. HTTP 504 Gateway Timeout
- **Meaning**: ALB established connection to target, but target did not respond before the ALB idle timeout expired (default 60 seconds).
- **Root Causes**: Database query lock, slow external API call, high CPU utilization on target backend.

### 3. Unhealthy Target Group Targets
- **Symptom**: Target state shows `Unhealthy` in Target Group console.
- **Diagnostic Flow**:
  1. **Health Check Path**: Verify HTTP health check path (e.g. `/health`, `/api/health`). If target returns 404 or 500, health check fails.
  2. **Health Check Port**: Ensure health check port matches the application port.
  3. **Security Group Rules**: Ensure ALB Security Group allows outbound traffic to target instances, and target EC2 Security Group allows inbound traffic from ALB Security Group on the health check port.
  4. **Matcher Status Code**: Verify expected HTTP response codes (e.g., `200` vs `200-299`).
