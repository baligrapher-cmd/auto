
import json
import os
import re

def simulate_capture(post_data, existing_meta):
    changed = False
    is_tree = False
    is_loc = False

    if "tree_id" in post_data:
        match = re.search(r'name="tree_id"\s*\r\n\r\n(\d+)', post_data)
        if match and match.group(1) != "0":
            tree_id = match.group(1)
            is_tree = True
            changed = True
    
    if "location_id" in post_data:
        match = re.search(r'name="location_id"\s*\r\n\r\n(\d+)', post_data)
        if match and match.group(1) != "0":
            location_id = match.group(1)
            is_loc = True
            changed = True

    if changed:
        if is_tree:
            existing_meta["tree_id"] = tree_id
            existing_meta.pop("location_id", None)
        if is_loc:
            existing_meta["location_id"] = location_id
            existing_meta.pop("tree_id", None)
    
    return changed, existing_meta

# Test Case 1: Initial capture of Tree
print("Test 1: Capture Tree")
meta = {}
post = 'name="tree_id"\r\n\r\n12345'
_, meta = simulate_capture(post, meta)
print(f"Result: {meta}") # Expected: {'tree_id': '12345'}

# Test Case 2: Switch to Location
print("\nTest 2: Switch to Location")
post = 'name="location_id"\r\n\r\n67890'
_, meta = simulate_capture(post, meta)
print(f"Result: {meta}") # Expected: {'location_id': '67890'} (tree_id should be gone)

# Test Case 3: Switch back to Tree
print("\nTest 3: Switch back to Tree")
post = 'name="tree_id"\r\n\r\n55555'
_, meta = simulate_capture(post, meta)
print(f"Result: {meta}") # Expected: {'tree_id': '55555'} (location_id should be gone)

# Test Case 4: Ignore "0" ID
print("\nTest 4: Ignore '0' ID")
post = 'name="location_id"\r\n\r\n0'
changed, meta = simulate_capture(post, meta)
print(f"Changed: {changed}, Result: {meta}") # Expected: Changed: False, Result: {'tree_id': '55555'}
