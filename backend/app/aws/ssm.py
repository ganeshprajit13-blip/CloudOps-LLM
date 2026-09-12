import json
import time
from typing import Any, Dict, List, Optional
from botocore.exceptions import ClientError
from app.aws.client import get_ssm_client
from app.core.logging import logger

# Strictly read-only PowerShell commands for Windows host diagnostics
READONLY_POWERSHELL_DIAGNOSTICS = """
$services = Get-Service -Name W3SVC, WAS, IISADMIN, Spooler -ErrorAction SilentlyContinue | Select-Object Name, DisplayName, @{Name="Status"; Expression={$_.Status.ToString()}}, @{Name="StartType"; Expression={$_.StartType.ToString()}}
$ports = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 80, 443, 8080, 22, 3389 } | Select-Object LocalAddress, LocalPort, @{Name="State"; Expression={$_.State.ToString()}}, OwningProcess
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue | Select-Object Caption, Version, @{Name="LastBootUpTime"; Expression={$_.LastBootUpTime.ToString()}}, TotalVisibleMemorySize, FreePhysicalMemory

[PSCustomObject]@{
    Services = @($services)
    ListeningPorts = @($ports)
    SystemInfo = $os
} | ConvertTo-Json -Depth 4 -Compress
"""


def _parse_powershell_output(output_str: str) -> Dict[str, Any]:
    """Safely extracts JSON payload from PowerShell output."""
    if not output_str or not isinstance(output_str, str):
        return {}
    
    cleaned = output_str.strip()
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_sub = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(json_sub)
        except Exception:
            pass
    return {}


def get_windows_host_telemetry(
    instance_ids: Optional[List[str]] = None,
    region: Optional[str] = None,
    timeout_seconds: int = 15,
) -> List[Dict[str, Any]]:
    """
    Collects read-only Windows host-level telemetry (services, listening ports, OS health) via AWS SSM.
    Strictly read-only; executes zero state modification commands.
    """
    logger.info(f"Starting read-only Windows host telemetry collection via SSM for instances: {instance_ids}")
    client = get_ssm_client(region)
    telemetry_records: List[Dict[str, Any]] = []

    target_instances = instance_ids or []
    if not target_instances:
        # If no explicit instances passed, discover managed instances
        try:
            resp = client.describe_instance_information(MaxResults=50)
            target_instances = [
                info.get("InstanceId")
                for info in resp.get("InstanceInformationList", [])
                if info.get("InstanceId")
            ]
        except ClientError as e:
            logger.warning(f"SSM describe_instance_information failed or unauthorized: {e}")
            target_instances = []

    if not target_instances:
        logger.info("No SSM target instances specified or discoverable for host telemetry collection.")
        return []

    for inst_id in target_instances:
        record: Dict[str, Any] = {
            "instance_id": inst_id,
            "platform": "windows",
            "collection_method": "ssm_run_command",
            "services": [],
            "listening_ports": [],
            "system_info": {},
            "error": None,
        }

        # Strategy 1: SSM Run Command (AWS-RunPowerShellScript)
        try:
            logger.debug(f"[SSM] Sending read-only PowerShell command to instance {inst_id} via AWS-RunPowerShellScript")
            cmd_resp = client.send_command(
                InstanceIds=[inst_id],
                DocumentName="AWS-RunPowerShellScript",
                Parameters={"commands": [READONLY_POWERSHELL_DIAGNOSTICS.strip()]},
                Comment="CloudOps Read-Only Host Telemetry Diagnostics",
                TimeoutSeconds=max(30, timeout_seconds),
            )
            cmd_id = cmd_resp.get("Command", {}).get("CommandId")
            logger.debug(f"[SSM] SendCommand initiated successfully. CommandId={cmd_id} for instance {inst_id}")

            if cmd_id:
                inv_resp = None
                max_attempts = max(30, int(timeout_seconds * 2))
                for attempt in range(max_attempts):
                    time.sleep(0.5)

                    try:
                        inv_resp = client.get_command_invocation(
                            CommandId=cmd_id,
                            InstanceId=inst_id,
                        )
                        inv_status = inv_resp.get("Status")
                        logger.debug(f"[SSM] Poll attempt {attempt + 1}/{max_attempts} for CommandId={cmd_id}: Status={inv_status}")
                        if inv_status in ["Success", "Failed", "Cancelled", "TimedOut"]:
                            break
                    except ClientError as ce:
                        err_code = ce.response.get("Error", {}).get("Code", "")
                        logger.debug(f"[SSM] Poll attempt {attempt + 1}/{max_attempts} caught ClientError ({err_code})")
                        if err_code == "InvocationDoesNotExist" and attempt < max_attempts - 1:
                            continue
                        raise

                if inv_resp and inv_resp.get("Status") == "Success":
                    output_content = inv_resp.get("StandardOutputContent", "")
                    logger.debug(f"[SSM] CommandId={cmd_id} succeeded. StandardOutputContent length={len(output_content)} chars")
                    parsed = _parse_powershell_output(output_content)

                    raw_services = parsed.get("Services", []) or parsed.get("services", [])
                    if isinstance(raw_services, dict):
                        raw_services = [raw_services]
                    for svc in raw_services:
                        if isinstance(svc, dict):
                            record["services"].append({
                                "name": svc.get("Name") or svc.get("name") or "unknown",
                                "display_name": svc.get("DisplayName") or svc.get("display_name") or svc.get("Name", ""),
                                "status": svc.get("Status") or svc.get("status") or "Unknown",
                                "start_type": svc.get("StartType") or svc.get("start_type") or "Unknown",
                            })

                    raw_ports = parsed.get("ListeningPorts", []) or parsed.get("listening_ports", [])
                    if isinstance(raw_ports, dict):
                        raw_ports = [raw_ports]
                    for p in raw_ports:
                        if isinstance(p, dict):
                            record["listening_ports"].append({
                                "port": p.get("LocalPort") or p.get("port"),
                                "local_address": p.get("LocalAddress") or p.get("local_address"),
                                "state": p.get("State") or p.get("state") or "Listen",
                                "owning_process": p.get("OwningProcess") or p.get("owning_process"),
                            })

                    sys_info = parsed.get("SystemInfo", {}) or parsed.get("system_info", {})
                    if isinstance(sys_info, dict):
                        record["system_info"] = {
                            "os_name": sys_info.get("Caption") or sys_info.get("os_name"),
                            "os_version": sys_info.get("Version") or sys_info.get("os_version"),
                            "last_boot_time": str(sys_info.get("LastBootUpTime") or sys_info.get("last_boot_time") or ""),
                            "total_memory_kb": sys_info.get("TotalVisibleMemorySize") or sys_info.get("total_memory_kb"),
                            "free_memory_kb": sys_info.get("FreePhysicalMemory") or sys_info.get("free_memory_kb"),
                        }

                    logger.debug(f"[SSM] Successfully parsed {len(record['services'])} services and {len(record['listening_ports'])} listening ports for {inst_id}")
                    telemetry_records.append(record)
                    continue
                elif inv_resp and inv_resp.get("Status") != "Success":
                    err_msg = inv_resp.get("StandardErrorContent", "") or f"Command ended with status {inv_resp.get('Status')}"
                    logger.warning(f"[SSM] Run Command ended with non-success status '{inv_resp.get('Status')}' on {inst_id}: {err_msg}")
                    record["error"] = f"SSM Run Command status: {inv_resp.get('Status')}"
        except ClientError as ce:
            err_code = ce.response.get("Error", {}).get("Code", "")
            err_msg = ce.response.get("Error", {}).get("Message", str(ce))
            logger.info(f"[SSM] Run Command unavailable for {inst_id} ({err_code}): {err_msg}")
            record["error"] = f"SSM Run Command ClientError ({err_code}): {err_msg}"
        except Exception as ex:
            logger.warning(f"[SSM] Run Command diagnostic failed for {inst_id}: {ex}")
            record["error"] = f"SSM Run Command exception: {str(ex)}"



        # Strategy 2: SSM Inventory fallback (AWS:Service)
        try:
            inv_entries = client.list_inventory_entries(
                InstanceId=inst_id,
                TypeName="AWS:Service",
            )
            record["collection_method"] = "ssm_inventory"
            for entry in inv_entries.get("Entries", []):
                svc_name = entry.get("Name", "")
                if any(k.lower() in svc_name.lower() for k in ["w3svc", "was", "iis", "spooler"]):
                    record["services"].append({
                        "name": svc_name,
                        "display_name": entry.get("DisplayName", svc_name),
                        "status": entry.get("Status", "Unknown"),
                        "start_type": entry.get("StartMode", entry.get("StartType", "Unknown")),
                    })
            telemetry_records.append(record)
            continue
        except ClientError as ce:
            logger.debug(f"SSM Inventory fallback failed for {inst_id}: {ce}")
        except Exception as ex:
            logger.debug(f"SSM Inventory fallback exception for {inst_id}: {ex}")

        # Fallback record
        record["error"] = "SSM host telemetry unavailable or not configured for instance"
        telemetry_records.append(record)

    logger.info(f"Windows host telemetry collection completed: {len(telemetry_records)} host records obtained.")
    return telemetry_records
