import json
import urllib.request
import urllib.parse

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post(path, body):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("\n" + "="*70)
print("1. VERIFY /api/cloud/resources")
print("="*70)
res = get("/api/cloud/resources")
print(f"Region: {res.get('region')}")
print(f"Resources count: {len(res.get('resources', []))}")
for r in res.get("resources", []):
    print(f"  - Resource ID: {r.get('resource_id')} | Name: {r.get('name')} | Label: {r.get('display_label')}")

target_id = "i-07243bdf548e18f5b"

print("\n" + "="*70)
print(f"2. VERIFY /api/cloud/context?resource_id={target_id}")
print("="*70)
ctx = get(f"/api/cloud/context?resource_id={target_id}")
resources = ctx.get("resources", {})
ec2_list = resources.get("ec2", [])
sg_list = resources.get("security_groups", [])
vpc_info = resources.get("vpc", {})
rt_list = vpc_info.get("route_tables", [])
signals = ctx.get("signals", [])

print(f"Retained EC2 Instances ({len(ec2_list)}):")
for inst in ec2_list:
    print(f"  - ID: {inst.get('instance_id')}, VPC: {inst.get('vpc_id')}, Subnet: {inst.get('subnet_id')}")

print(f"Retained Security Groups ({len(sg_list)}):")
for sg in sg_list:
    print(f"  - ID: {sg.get('group_id')} ({sg.get('name')})")

print(f"Retained Route Tables ({len(rt_list)}):")
for rt in rt_list:
    print(f"  - ID: {rt.get('route_table_id')} (VPC: {rt.get('vpc_id')})")

print(f"Signals ({len(signals)}):")
for s in signals:
    print(f"  - Type: {s.get('type')} | Resource: {s.get('resource_id')} | Desc: {s.get('description')}")

print("\n" + "="*70)
print(f"3. VERIFY /api/cloud/signals?resource_id={target_id}")
print("="*70)
sig = get(f"/api/cloud/signals?resource_id={target_id}")
print(f"Returned signals count: {len(sig)}")
for s in sig:
    print(f"  - [{s.get('severity', '').upper()}] {s.get('type')} on {s.get('resource_id')}: {s.get('description')}")

print("\n" + "="*70)
print(f"4. VERIFY /api/analyze with resource_id={target_id}")
print("="*70)
analysis_payload = {
    "question": "Why is my website unreachable over HTTPS on port 443?",
    "resource_id": target_id,
    "collect_live_data": True
}
diag = post("/api/analyze", analysis_payload)
print(f"Problem: {diag.get('problem')}")
print(f"Probable Root Cause: {diag.get('probable_root_cause')}")
print("Evidence:")
for e in diag.get("evidence", []):
    print(f"  - {e}")
print(f"Recommendation: {diag.get('recommendation')}")
print(f"Confidence: {diag.get('confidence')}")

print("\n" + "="*70)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
print("="*70)
