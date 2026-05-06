#!/usr/bin/env python3
"""Direct Generate Agent test - runs independently"""

import sys
import time
import json
sys.path.insert(0, '/Users/yangfei/Code/VFX-Agent/backend')

from app.pipeline.state import create_initial_state
from app.agents.generate import GenerateAgent

print("=== Direct Generate Agent Test ===")

state = create_initial_state(
    pipeline_id="test-direct-final",
    input_type="text",
    user_notes="gradient"
)

state["snapshot"]["visual_description"] = {
    "effect_name": "gradient",
    "visual_identity": {"summary": "A simple gradient"},
    "shape_definition": {"description": "none"},
    "color_definition": {"description": "left to right gradient"},
    "animation_definition": {"description": "static"},
    "background_definition": {"description": "white"}
}

agent = GenerateAgent()

print("Calling Generate Agent...")
print("httpx timeout now: 120s connect, 120s read")
start = time.time()

try:
    result = agent.run(state, return_raw=True)
    duration = time.time() - start
    
    print(f"\n✅ Completed in {duration:.2f}s")
    shader = result.get("shader", "")
    print(f"   Shader: {len(shader)} chars")
    
    usage = result.get("usage", {})
    print(f"   Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
    print(f"   Completion tokens: {usage.get('completion_tokens', 'N/A')}")
    print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
    
    if shader:
        print(f"\n--- Shader Preview ---")
        print(shader[:200])
    
    # Save result
    with open("test_result.json", "w") as f:
        json.dump({
            "duration": duration,
            "shader_length": len(shader),
            "shader_preview": shader[:500] if shader else "",
            "usage": usage,
        }, f, indent=2)
    
    print("\n✅ Result saved to test_result.json")
    
except Exception as e:
    duration = time.time() - start
    print(f"\n❌ Failed after {duration:.2f}s")
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()
    
    # Save error
    with open("test_error.json", "w") as f:
        json.dump({
            "duration": duration,
            "error": str(e),
        }, f, indent=2)

print("\n=== Test Complete ===")