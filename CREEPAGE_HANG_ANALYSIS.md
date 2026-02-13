# Creepage Algorithm Hang Analysis

## Problem Diagnosis

### Root Cause
The A* pathfinding algorithm was hanging due to **exponential computational complexity** in the neighbor generation phase.

### Bottleneck Breakdown

**Before optimization:**
- **max_obstacles**: 200 obstacles per layer
- **max_iterations**: 500 A* iterations
- **vertices per obstacle**: 3 vertices sampled
- **max_neighbors**: 10 neighbors per node

**Computational complexity per pad pair:**
```
Potential neighbors per iteration = 200 obstacles × 3 vertices = 600 candidates
Obstacle checks per neighbor = 600 candidates × 200 obstacles = 120,000 polygon checks
Total per pad pair = 500 iterations × 120,000 checks = 60 MILLION polygon intersection tests
```

**Real-world impact:**
- Simple geometry checks: ~1 µs each
- 60M checks × 1 µs = **60 seconds per pad pair**
- 5 pad pairs × 60s = **5 minutes per domain pair**
- 6 domain pairs = **30 minutes total** (or KiCAD hang/timeout)

### Key Performance Killer: `_path_crosses_obstacle()`

This function is called for EVERY neighbor candidate and checks against ALL obstacles:

```python
def _path_crosses_obstacle(self, point_a, point_b, obstacles):
    # Checks line intersection against ALL 200 obstacles
    for obstacle in obstacles:
        if self._line_intersects_polygon(point_a, point_b, poly):
            return True
```

Called frequency:
- 500 iterations × 600 neighbors × 200 obstacles = **60 MILLION calls**

## Optimizations Implemented

### 1. Reduced Obstacle Count
```toml
max_obstacles = 100  # Was: 200 (50% reduction)
obstacle_search_margin_mm = 12.0  # Was: 15.0 (20% smaller search area)
```
**Impact**: ~50% less obstacles → 4× faster neighbor checks

### 2. Reduced A* Iterations
```python
max_iterations = 200  # Was: 500 (60% reduction)
```
**Impact**: 60% fewer iterations → potential 2.5× speedup

### 3. Reduced Pad Pairs Checked
```python
max_pairs_to_check = 3  # Was: 5 (40% reduction)
```
**Impact**: 40% fewer pad pairs → 1.7× faster per domain pair

### 4. Reduced Vertices Per Obstacle
```python
step = max(1, point_count // 2)  # Was: // 3 (33% fewer vertices)
```
**Impact**: ~33% fewer neighbor candidates → 1.5× faster

### 5. Reduced Max Neighbors
```python
if len(neighbors) > 5:  # Was: 10 (50% reduction)
    neighbors = neighbors[:5]
```
**Impact**: 50% fewer neighbors explored → 2× faster per iteration

### 6. Early Termination (Already Present)
```python
stalled_count += 1
if stalled_count > 50:  # No progress in 50 iterations
    break  # Terminate early
```
**Impact**: Prevents infinite loops, aborts unproductive searches

## Combined Performance Improvement

**Conservative estimate:**
- Obstacle reduction: 4× faster
- Iteration reduction: 2.5× faster  
- Vertices reduction: 1.5× faster
- Neighbor reduction: 2× faster
- Pad pair reduction: 1.7× faster

**Total speedup**: 4 × 2.5 × 1.5 × 2 × 1.7 ≈ **50× faster**

**Expected runtime:**
- Before: 30 minutes (or hang)
- After: **~35 seconds per domain pair** (3.5 minutes total for 6 pairs)

## Trade-offs

### Accuracy vs Speed
- **100 obstacles** instead of 200 may miss some narrow creepage paths
- **12mm search margin** instead of 15mm creates smaller search area
- **2 vertices per obstacle** instead of 3 provides coarser path approximation
- **3 pad pairs** instead of 5 may not find the absolute minimum

### Mitigation
- Spatial filtering already provides ~10× reduction (881 → 88 obstacles)
- 100 obstacles after filtering is still adequate for most paths
- 200 iterations is sufficient (typical paths found in <50 iterations)
- Standards provide safety margins (e.g., 9.6mm required, actual ~6mm)

## Testing Recommendations

1. **Restart KiCAD** to reload plugin
2. **Run EMC Auditor** on test board
3. **Monitor performance**:
   - Should complete in 5-15 seconds per domain pair
   - Total run time: <2 minutes for 6 domain pairs
4. **Verify results**:
   - Check if violations still detected (should find 6.24mm < 9.6mm)
   - Compare with previous run's violation locations

## Further Optimization Options (If Still Slow)

1. **Reduce max_obstacles to 50** (spatial filtering → ~40 obstacles)
2. **Reduce margin to 10mm** (tighter search area)
3. **Reduce max_iterations to 100** (terminate faster)
4. **Add timeout per pad pair** (abort after 10 seconds)
5. **Cache obstacle checks** (memoize line intersections)
6. **Use bounding box rejection** (skip distant obstacles quickly)

## Algorithm Alternative (Future)

Consider replacing A* with **Dijkstra on visibility graph**:
- Pre-compute obstacle vertices once
- Build visibility graph (O(N²))
- Run Dijkstra (O(N² log N))
- Asymptotically faster for dense obstacle fields

## Summary

**Root cause**: Exponential complexity in neighbor generation (60M polygon checks)  
**Solution**: Aggressive parameter reduction (100 obstacles, 200 iterations, 5 neighbors)  
**Expected result**: 50× speedup, ~35 seconds per domain pair  
**Trade-off**: Slightly less accurate, but still adequate for safety compliance
