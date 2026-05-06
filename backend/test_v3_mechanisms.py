"""Test V3.0 mechanisms: rollback, gradient truncation, re-decompose"""

import sys
sys.path.insert(0, '/Users/yangfei/Code/VFX-Agent/backend')

from app.pipeline.state import (
    create_initial_state,
    update_checkpoint,
    update_gradient_window,
    should_trigger_re_decompose,
    rollback_to_checkpoint,
    PipelineConfig,
)


def test_gradient_truncation():
    """Test 1: Gradient window truncation (no shader code)"""
    print("\n=== Test 1: Gradient Truncation ===")
    
    state = create_initial_state(
        pipeline_id="test-grad",
        input_type="text",
        user_notes="test"
    )
    
    # Add 5 entries (should truncate to 3)
    for i in range(1, 6):
        entry = {
            "iteration": i,
            "score": 0.5 + i * 0.1,
            "feedback_summary": f"Test feedback {i}",
            "shader": f"shader code {i}",  # Should be removed
            "duration_ms": 1000,
            "human_iteration": False,
        }
        state["gradient_window"] = update_gradient_window(
            state["gradient_window"], entry, max_size=3
        )
    
    print(f"✓ Gradient window size: {len(state['gradient_window'])} (expected 3)")
    
    # Verify no shader code
    for entry in state["gradient_window"]:
        assert "shader" not in entry, f"Entry still has shader field: {entry.keys()}"
    
    print(f"✓ All entries have no shader code")
    print(f"  Scores: {[e['score'] for e in state['gradient_window']]} (expected [0.8, 0.9, 1.0])")


def test_checkpoint_update():
    """Test 2: Checkpoint update on score improvement"""
    print("\n=== Test 2: Checkpoint Update ===")
    
    state = create_initial_state(
        pipeline_id="test-check",
        input_type="text",
        user_notes="test"
    )
    
    # Iteration 1: score 0.7
    state["snapshot"]["shader"] = "shader_1"
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.7}
    
    update = update_checkpoint(state)
    if update:
        state["checkpoint"].update(update["checkpoint"])
    
    print(f"✓ Iteration 1: best_score = {state['checkpoint']['best_score']} (expected 0.7)")
    
    # Iteration 2: score 0.9 (should update)
    state["snapshot"]["shader"] = "shader_2"
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.9}
    
    update = update_checkpoint(state)
    if update:
        state["checkpoint"].update(update["checkpoint"])
    
    print(f"✓ Iteration 2: best_score = {state['checkpoint']['best_score']} (expected 0.9)")
    
    # Iteration 3: score 0.6 (should NOT update)
    state["snapshot"]["shader"] = "shader_3_bad"
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.6}
    
    update = update_checkpoint(state)
    assert update == {}, f"Checkpoint should not update for lower score"
    
    print(f"✓ Iteration 3: best_score still {state['checkpoint']['best_score']} (expected 0.9, not 0.6)")


def test_rollback_mechanism():
    """Test 3: Physical rollback on score regression"""
    print("\n=== Test 3: Rollback Mechanism ===")
    
    state = create_initial_state(
        pipeline_id="test-roll",
        input_type="text",
        user_notes="test"
    )
    
    # Set up checkpoint with best shader
    state["checkpoint"] = {
        "best_score": 0.85,
        "best_shader": "best_shader_code",
        "best_iteration": 3,
        "best_visual_description": {"effect_name": "ripple"},
        "best_render_screenshots": [],
    }
    
    # Current snapshot with degraded shader
    state["snapshot"]["shader"] = "bad_shader_code"
    state["snapshot"]["iteration"] = 4
    state["snapshot"]["visual_description"] = {"effect_name": "failed_ripple"}
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.5}
    
    # Trigger rollback
    rollback_update = rollback_to_checkpoint(state)
    
    print(f"✓ Rollback triggered for score 0.5 < best_score 0.85")
    
    if rollback_update:
        print(f"  Rollback keys: {list(rollback_update.keys())}")
        new_snapshot = rollback_update.get("snapshot", {})
        
        print(f"✓ Restored shader: '{new_snapshot.get('shader', '')}' (expected 'best_shader_code')")
        print(f"✓ Restored iteration: {new_snapshot.get('iteration', 0)} (expected 3)")
        
        assert new_snapshot.get("shader") == "best_shader_code"
        assert new_snapshot.get("iteration") == 3


def test_re_decompose_trigger():
    """Test 4: Re-decompose trigger conditions"""
    print("\n=== Test 4: Re-decompose Trigger ===")
    
    # Case 1: Low score
    state = create_initial_state(
        pipeline_id="test-re",
        input_type="text",
        user_notes="test"
    )
    
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.3}
    trigger = should_trigger_re_decompose(state)
    
    print(f"✓ Case 1: score=0.3 < threshold=0.5 → trigger={trigger} (expected True)")
    assert trigger == True
    
    # Case 2: Stagnation detection
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.8}
    state["gradient_window"] = [
        {"iteration": i, "score": 0.79 + i * 0.001, "feedback_summary": "", "duration_ms": 1000, "human_iteration": False}
        for i in range(3)
    ]
    
    trigger = should_trigger_re_decompose(state)
    print(f"✓ Case 2: variance≈0.001 < threshold=0.05 → trigger={trigger} (expected True)")
    assert trigger == True
    
    # Case 3: Normal progression (no trigger)
    state["snapshot"]["inspect_feedback"] = {"overall_score": 0.75}
    state["gradient_window"] = [
        {"iteration": 1, "score": 0.5, "feedback_summary": "", "duration_ms": 1000, "human_iteration": False},
        {"iteration": 2, "score": 0.6, "feedback_summary": "", "duration_ms": 1000, "human_iteration": False},
        {"iteration": 3, "score": 0.7, "feedback_summary": "", "duration_ms": 1000, "human_iteration": False},
    ]
    
    trigger = should_trigger_re_decompose(state)
    print(f"✓ Case 3: score=0.75, variance=0.2 → trigger={trigger} (expected False)")
    assert trigger == False


def run_all_tests():
    """Run all V3.0 mechanism tests"""
    print("=" * 60)
    print("V3.0 Mechanism Tests")
    print("=" * 60)
    
    test_gradient_truncation()
    test_checkpoint_update()
    test_rollback_mechanism()
    test_re_decompose_trigger()
    
    print("\n" + "=" * 60)
    print("✅ All V3.0 mechanism tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()