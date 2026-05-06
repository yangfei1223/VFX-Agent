"""Monitor Pipeline execution"""

import requests
import json
import time
import sys

pipeline_id = sys.argv[1] if len(sys.argv) > 1 else None

if not pipeline_id:
    print("Usage: python monitor_pipeline.py <pipeline_id>")
    sys.exit(1)

print(f"Monitoring Pipeline: {pipeline_id}")
print("=" * 60)

for i in range(40):
    try:
        r = requests.get(f"http://localhost:8000/pipeline/status/{pipeline_id}")
        data = r.json()
        
        status = data.get("status", "unknown")
        phase = data.get("current_phase", "none")
        iteration = data.get("snapshot", {}).get("iteration", 0)
        shader_len = len(data.get("snapshot", {}).get("shader", ""))
        passed = data.get("passed", False)
        
        print(f"[{i+1}] status={status} phase={phase} iter={iteration} shader={shader_len} passed={passed}")
        
        if status != "running":
            print("=" * 60)
            print(f"Pipeline finished with status: {status}")
            
            # Show final details
            if shader_len > 0:
                shader = data.get("snapshot", {}).get("shader", "")
                print(f"\nShader preview (first 200 chars):")
                print(shader[:200])
            
            checkpoint = data.get("checkpoint", {})
            print(f"\nCheckpoint:")
            print(f"  best_score: {checkpoint.get('best_score', 0)}")
            print(f"  best_iteration: {checkpoint.get('best_iteration', 0)}")
            
            if data.get("error"):
                print(f"\nError: {data['error']}")
            
            break
        
        time.sleep(3)
        
    except Exception as e:
        print(f"[{i+1}] Error: {e}")
        time.sleep(3)