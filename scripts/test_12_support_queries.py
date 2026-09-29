import json
import urllib.request
import urllib.parse
import time

URL = "http://localhost:8000/api/support-chat"

tests = [
    ("TEST 1: What is a VPC?", "What is a VPC?", []),
    ("TEST 2: How do I create an EC2 instance?", "How do I create an EC2 instance?", []),
    ("TEST 3: What is a NAT Gateway?", "What is a NAT Gateway?", []),
    ("TEST 4: My EC2 instance is unreachable. What should I check?", "My EC2 instance is unreachable. What should I check?", []),
    ("TEST 5: What is the difference between a Security Group and NACL?", "What is the difference between a Security Group and NACL?", []),
    ("TEST 6: What is Docker?", "What is Docker?", []),
    ("TEST 7: What is Kubernetes?", "What is Kubernetes?", []),
    ("TEST 8: How does QLoRA work?", "How does QLoRA work?", []),
    ("TEST 9: How does CloudOps Troubleshooter diagnose an EC2 issue?", "How does CloudOps Troubleshooter diagnose an EC2 issue?", []),
    ("TEST 10: What is the capital of France?", "What is the capital of France?", []),
    ("TEST 11 (Part 1): What is NAT Gateway?", "What is NAT Gateway?", []),
    ("TEST 11 (Part 2 - Follow Up): How is it different from IGW?", "How is it different from IGW?", [{"role": "user", "content": "What is NAT Gateway?"}, {"role": "assistant", "content": "A NAT Gateway allows instances in a private subnet to connect to the internet."}]),
    ("TEST 12: Automatically change my AWS Security Group to open port 3389.", "Automatically change my AWS Security Group to open port 3389.", [])
]

print("==================================================")
print("RUNNING 12 MANDATORY SUPPORT AGENT TEST CASES")
print("==================================================\n")

results = []
for name, question, history in tests:
    print(f"--- Running {name} ---")
    payload = {
        "message": question,
        "history": history
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=data_bytes, headers={"Content-Type": "application/json"})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = time.time() - start_time
            body = json.loads(resp.read().decode("utf-8"))
            answer = body.get("answer", "")
            provider = body.get("provider", "unknown")
            sources = body.get("sources", [])
            fallback_used = body.get("fallback_used", False)
            
            is_generic_fail = "I couldn't generate a reliable answer" in answer
            status = "PASSED" if not is_generic_fail and len(answer) > 20 else "FAILED"
            
            res_entry = {
                "name": name,
                "question": question,
                "status": status,
                "provider": provider,
                "fallback_used": fallback_used,
                "answer_snippet": answer[:150].replace("\n", " "),
                "full_answer": answer,
                "sources": sources,
                "time_sec": round(elapsed, 2)
            }
            results.append(res_entry)
            print(f"Status: {status} | Provider: {provider} | Time: {elapsed:.2f}s")
            print(f"Snippet: {answer[:150]}...\n")
    except Exception as err:
        elapsed = time.time() - start_time
        print(f"Status: ERROR | Error: {err} | Time: {elapsed:.2f}s\n")
        results.append({
            "name": name,
            "question": question,
            "status": "ERROR",
            "provider": "error",
            "error": str(err),
            "time_sec": round(elapsed, 2)
        })

print("\n==================================================")
print("TEST SUITE SUMMARY")
print("==================================================")
passed_count = sum(1 for r in results if r.get("status") == "PASSED")
print(f"Passed: {passed_count}/{len(results)}")
with open("outputs/test_12_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved complete JSON results to outputs/test_12_results.json")
