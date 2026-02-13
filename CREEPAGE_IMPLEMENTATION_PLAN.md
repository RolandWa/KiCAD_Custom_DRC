# Creepage Distance Implementation Plan

**Purpose:** Design document for implementing IEC60664-1/IPC2221 creepage distance checking  
**Status:** Planning Phase  
**Complexity:** High (estimated 800-1200 lines, 20-40 hours)  
**Last Updated:** February 13, 2026

---

## Executive Summary

**Creepage** is the minimum surface path distance along the PCB between conductors at different voltages. Unlike clearance (straight-line air gap), creepage must follow the PCB surface and avoid crossing other copper features.

**Key Challenge:** This is a 2D pathfinding problem on a complex surface with obstacles, slots, and multiple layers.

---

## Algorithm Overview

### Recommended Approach: A* Pathfinding

**Why A*?**
- Optimal path finding (guaranteed shortest path)
- Efficient with good heuristic (Euclidean distance)
- Well-established algorithm with known performance
- Can handle complex obstacle avoidance

**Alternative Considered:**
- **Dijkstra's**: Slower than A* (no heuristic)
- **Wavefront expansion**: Simpler but less efficient
- **Visibility graph**: Good for polygons, complex to implement
- **RRT (Rapidly-exploring Random Tree)**: Probabilistic, not guaranteed optimal

**Verdict:** A* is the best balance of optimality, performance, and implementation complexity.

---

## Implementation Phases

### Phase 1: Foundation (200-300 lines, 5-8 hours)

**Goal:** Build obstacle map and basic pathfinding structure

```python
def _calculate_creepage(self, domain_a, domain_b):
    """
    Calculate minimum surface path between two voltage domains.
    """
    # 1. Get all pads/features for each domain
    features_a = self._get_features_for_domain(domain_a)
    features_b = self._get_features_for_domain(domain_b)
    
    # 2. Build obstacle map (all copper except domain A and B)
    obstacle_map = self._build_obstacle_map(domain_a, domain_b)
    
    # 3. Find shortest creepage path between any features
    min_creepage = float('inf')
    best_path = None
    
    for feature_a in features_a:
        for feature_b in features_b:
            path = self._astar_surface_path(
                start=feature_a.position,
                goal=feature_b.position,
                obstacles=obstacle_map
            )
            
            if path and path.length < min_creepage:
                min_creepage = path.length
                best_path = path
    
    return (min_creepage, best_path)
```

**Key Functions to Implement:**

1. **`_build_obstacle_map(exclude_domains)`**
   - Collect all copper shapes on each layer
   - Use `TransformShapeToPolygon()` to get polygon representations
   - Create spatial index (quadtree or grid) for fast collision detection
   - Exclude copper belonging to the two domains being checked

2. **`_get_features_for_domain(domain_name)`**
   - Return all pads/traces in this voltage domain
   - Filter by net patterns or net class
   - Include edge points (polygon vertices) for starting A*

3. **`_astar_surface_path(start, goal, obstacles)`**
   - Classic A* with Euclidean heuristic
   - Node = position on PCB (x, y coordinate)
   - Edge = straight line between nodes (if not crossing obstacle)
   - Return path as list of waypoints + total length

---

### Phase 2: Obstacle Detection (150-200 lines, 4-6 hours)

**Goal:** Accurate collision detection for path validation

```python
def _path_crosses_obstacle(self, point_a, point_b, obstacles):
    """
    Check if straight line from point_a to point_b crosses any obstacle.
    
    Uses line-polygon intersection detection.
    """
    # Fast rejection: bounding box check
    if not self._bounding_boxes_overlap(point_a, point_b, obstacles):
        return False
    
    # Detailed check: line segment vs polygon edges
    line = LineSegment(point_a, point_b)
    
    for obstacle in obstacles:
        if obstacle.intersects(line):
            return True
    
    return False
```

**Collision Detection Methods:**

1. **Line-Segment Intersection:**
   ```python
   def _segments_intersect(seg1_start, seg1_end, seg2_start, seg2_end):
       """
       Check if two line segments intersect.
       Uses cross-product method (CCW test).
       """
       # Implementation: classic computational geometry algorithm
   ```

2. **Point-in-Polygon Test:**
   ```python
   def _point_inside_polygon(point, polygon):
       """
       Ray casting algorithm to check if point is inside polygon.
       """
       # Cast ray from point to infinity, count edge crossings
       # Odd count = inside, even count = outside
   ```

3. **Spatial Indexing:**
   ```python
   class QuadTree:
       """
       Spatial index for fast obstacle queries.
       Divides board into quadrants for O(log n) lookup.
       """
   ```

---

### Phase 3: A* Pathfinding Core (250-350 lines, 8-12 hours)

**Goal:** Implement A* algorithm with PCB-specific optimizations

```python
def _astar_surface_path(self, start, goal, obstacles, layer):
    """
    A* pathfinding on PCB surface.
    
    Args:
        start: pcbnew.VECTOR2I, starting position
        goal: pcbnew.VECTOR2I, goal position
        obstacles: list of SHAPE_POLY_SET, copper to avoid
        layer: pcbnew layer ID
    
    Returns:
        Path object with waypoints and length, or None if no path exists
    """
    import heapq  # Priority queue for open set
    
    # Initialize A* data structures
    open_set = []  # Priority queue: (f_score, node)
    closed_set = set()  # Already evaluated nodes
    
    came_from = {}  # For path reconstruction
    g_score = {start: 0}  # Cost from start to node
    f_score = {start: self._heuristic(start, goal)}  # Estimated total cost
    
    heapq.heappush(open_set, (f_score[start], start))
    
    while open_set:
        current_f, current = heapq.heappop(open_set)
        
        # Goal reached
        if self._distance(current, goal) < 0.01:  # 0.01mm tolerance
            return self._reconstruct_path(came_from, current, start)
        
        closed_set.add(current)
        
        # Explore neighbors
        for neighbor in self._get_neighbor_nodes(current, goal, obstacles):
            if neighbor in closed_set:
                continue
            
            # Calculate tentative g_score
            tentative_g = g_score[current] + self._distance(current, neighbor)
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                # This path to neighbor is better
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal)
                
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
    
    # No path found
    return None


def _get_neighbor_nodes(self, current, goal, obstacles):
    """
    Generate candidate neighbor nodes for A* expansion.
    
    Strategy: Generate nodes along obstacle edges (visibility graph approach)
    """
    neighbors = []
    
    # 1. Add goal node (always try direct path)
    if not self._path_crosses_obstacle(current, goal, obstacles):
        neighbors.append(goal)
    
    # 2. Add obstacle corner vertices (can route around them)
    for obstacle in obstacles:
        for vertex in obstacle.COutline(0).GetPoints():
            vertex_pos = pcbnew.VECTOR2I(vertex.x, vertex.y)
            
            # Only add if path is clear
            if not self._path_crosses_obstacle(current, vertex_pos, obstacles):
                neighbors.append(vertex_pos)
    
    return neighbors


def _heuristic(self, node, goal):
    """
    A* heuristic: Euclidean distance (admissible, guarantees optimality).
    """
    dx = node.x - goal.x
    dy = node.y - goal.y
    return math.sqrt(dx**2 + dy**2) / 1e6  # Convert to mm


def _reconstruct_path(self, came_from, current, start):
    """
    Reconstruct path from A* came_from map.
    """
    path_nodes = [current]
    while current in came_from:
        current = came_from[current]
        path_nodes.append(current)
    path_nodes.reverse()
    
    # Calculate total length
    total_length = 0
    for i in range(len(path_nodes) - 1):
        segment_length = self._distance(path_nodes[i], path_nodes[i+1])
        total_length += segment_length
    
    return Path(nodes=path_nodes, length=pcbnew.ToMM(total_length))
```

**Performance Optimization:**

1. **Limit neighbor expansion:** Only test obstacle vertices + goal (not arbitrary grid points)
2. **Spatial pruning:** Skip obstacles far from current path segment
3. **Early termination:** Stop if path significantly longer than clearance (likely not shorter)
4. **Layer-specific checking:** Only check obstacles on same layer

---

### Phase 4: Slot/Cutout Detection (150-200 lines, 4-6 hours)

**Goal:** Detect when path crosses board edge (infinite creepage)

```python
def _path_crosses_board_edge(self, path, board):
    """
    Check if creepage path crosses a slot, cutout, or board edge.
    
    If true, creepage is INFINITE (path is broken).
    """
    board_outline = self._get_board_outline(board)
    
    for i in range(len(path.nodes) - 1):
        segment = LineSegment(path.nodes[i], path.nodes[i+1])
        
        # Check if segment crosses board edge (exits outline)
        if self._segment_leaves_board(segment, board_outline):
            return True
        
        # Check if segment crosses internal slot/cutout
        for cutout in self._get_board_cutouts(board):
            if segment.intersects(cutout):
                return True
    
    return False


def _get_board_outline(self, board):
    """
    Extract board outline polygon from Edge.Cuts layer.
    """
    edge_cuts = board.GetLayerID("Edge.Cuts")
    outline_segments = []
    
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == edge_cuts:
            # Collect segments, arcs, circles from Edge.Cuts
            outline_segments.append(drawing)
    
    # Construct polygon from connected segments
    return self._build_polygon_from_segments(outline_segments)


def _get_board_cutouts(self, board):
    """
    Find internal slots and cutouts (closed contours on Edge.Cuts).
    """
    # Similar to _get_board_outline, but find all closed polygons
    # Main outline is largest, rest are cutouts
    pass
```

**Edge Cases:**
- Multiple board outlines (panelization)
- Non-closed cutouts (manufacturing error, should warn)
- Curved edges (arcs) - need arc-line intersection
- Slots smaller than creepage distance (ignore if path doesn't cross)

---

### Phase 5: Multi-Layer Handling (100-150 lines, 3-5 hours)

**Goal:** Calculate creepage across vias and layer transitions

```python
def _calculate_creepage_multilayer(self, feature_a, feature_b):
    """
    Handle creepage when features are on different layers.
    
    Creepage path: Surface on layer A → via barrel → surface on layer B
    """
    layer_a = feature_a.GetLayer()
    layer_b = feature_b.GetLayer()
    
    if layer_a == layer_b:
        # Same layer: simple 2D pathfinding
        return self._astar_surface_path(feature_a.pos, feature_b.pos, obstacles, layer_a)
    
    # Different layers: find path through vias
    min_creepage = float('inf')
    best_path = None
    
    # Find all vias that could bridge the layers
    candidate_vias = self._find_vias_between_layers(layer_a, layer_b)
    
    for via in candidate_vias:
        # Path: feature_a → via (layer A) → via barrel → via (layer B) → feature_b
        path_to_via = self._astar_surface_path(feature_a.pos, via.pos, obstacles, layer_a)
        path_from_via = self._astar_surface_path(via.pos, feature_b.pos, obstacles, layer_b)
        
        if path_to_via and path_from_via:
            via_barrel_length = self._calculate_via_barrel_creepage(via, layer_a, layer_b)
            total_creepage = path_to_via.length + via_barrel_length + path_from_via.length
            
            if total_creepage < min_creepage:
                min_creepage = total_creepage
                best_path = self._combine_paths(path_to_via, via, path_from_via)
    
    return (min_creepage, best_path)


def _calculate_via_barrel_creepage(self, via, layer_a, layer_b):
    """
    Creepage along via barrel (cylinder surface).
    
    Simplified: Use via barrel height × π (wrap around)
    Conservative: Most standards allow vertical via transition at drill diameter
    """
    layer_height_a = self._get_layer_height(layer_a)
    layer_height_b = self._get_layer_height(layer_b)
    via_height = abs(layer_height_a - layer_height_b)
    
    # IPC2221: Via barrel creepage ≈ via drill diameter (conservative)
    via_drill = via.GetDrill()
    return pcbnew.ToMM(via_drill)
```

**Layer Stack Considerations:**
- External layers (F.Cu, B.Cu): Full creepage required
- Internal layers (In1.Cu, etc.): Shorter creepage (protected by substrate)
- Buried vias: May have better creepage than through-hole vias
- Blind vias: Connect subset of layers

---

### Phase 6: Visualization & Reporting (100-150 lines, 2-4 hours)

**Goal:** Draw creepage path on PCB for debugging/review

```python
def _draw_creepage_path(self, path, layer, color):
    """
    Draw creepage path as polyline on PCB.
    """
    for i in range(len(path.nodes) - 1):
        start = path.nodes[i]
        end = path.nodes[i+1]
        
        # Draw line segment
        self.draw_arrow(self.board, start, end, "", layer, group=None)
    
    # Annotate with distance
    midpoint = path.nodes[len(path.nodes) // 2]
    label = f"Creepage: {path.length:.2f}mm"
    self.draw_marker(self.board, midpoint, label, layer, group=None)


def _create_creepage_violation_marker(self, domain_a, domain_b, actual_mm, required_mm, path):
    """
    Draw violation marker for insufficient creepage.
    """
    msg = f"CREEPAGE: {actual_mm:.2f}mm < {required_mm:.2f}mm\n{domain_a} ↔ {domain_b}"
    
    # Draw at path midpoint
    midpoint = path.nodes[len(path.nodes) // 2]
    self.draw_marker(self.board, midpoint, msg, self.marker_layer, group)
    
    # Draw entire path in red
    self._draw_creepage_path(path, self.marker_layer, color="red")
```

---

## KiCAD Python API Reference

### Essential Classes/Functions

1. **SHAPE_POLY_SET** - Polygon representation
   ```python
   poly = pcbnew.SHAPE_POLY_SET()
   pad.TransformShapeToPolygon(poly, layer, maxError, errorLoc)
   outline = poly.COutline(0)  # Get first contour
   points = outline.GetPoints()  # List of VECTOR2I
   ```

2. **VECTOR2I** - 2D point (internal units: nanometers)
   ```python
   p = pcbnew.VECTOR2I(x, y)
   distance = (p1 - p2).EuclideanNorm()
   distance_mm = pcbnew.ToMM(distance)
   ```

3. **Board Iteration:**
   ```python
   for pad in board.GetPads():
       net = pad.GetNetname()
       layer = pad.GetLayer()
       pos = pad.GetPosition()
   
   for track in board.GetTracks():
       if track.Type() == pcbnew.PCB_VIA_T:
           via = track
   
   for zone in board.Zones():
       if zone.IsOnLayer(layer):
           # Copper pour on this layer
   ```

4. **Layer Functions:**
   ```python
   layer_id = board.GetLayerID("F.Cu")
   layer_name = board.GetLayerName(layer_id)
   is_copper = board.IsLayerEnabled(layer_id) and board.IsCopperLayer(layer_id)
   ```

---

## Performance Considerations

### Expected Complexity

**Worst Case:**
- N pads in domain A
- M pads in domain B
- O obstacles on PCB
- A* complexity: O(O log O) per path query

**Total:** O(N × M × O log O)

For typical board:
- 100 mains pads × 200 SELV pads = 20,000 path queries
- 5,000 obstacles (traces, pads, pours)
- Each A*: ~50ms
- Total: 20,000 × 50ms = **1000 seconds (16 minutes)** ❌ TOO SLOW

### Optimizations Required

1. **Spatial Pruning:** Only check closest pad pairs (within 2× required creepage)
   - Reduces from N×M to ~100 pairs
   - New total: 100 × 50ms = **5 seconds** ✅

2. **Fast Rejection:** If clearance > required creepage, skip creepage check
   - Creepage ≥ clearance always (surface path longer than air gap)
   - Reduces checks by ~80%
   - New total: 20 × 50ms = **1 second** ✅

3. **Obstacle Simplification:** Merge nearby copper shapes into single polygons
   - Reduces obstacle count from 5,000 to 500
   - A* complexity drops 10×
   - New total: **0.1 seconds per check** ✅

4. **Caching:** Reuse obstacle map for multiple checks on same layer
   - Build once: 2 seconds
   - Reuse: 1000 times
   - Amortized cost: 0.002 seconds per check ✅

5. **Early Exit:** Stop A* if path length > 2× required creepage
   - No point finding 10mm path if 3mm is required
   - Reduces failed searches by 90%

---

## Configuration Integration

### New TOML Settings

```toml
[clearance_creepage]

# Enable creepage checking (Phase 2 implementation)
check_creepage = true

# Creepage algorithm parameters
creepage_algorithm = "astar"  # Options: "astar", "dijkstra", "simplepath"
creepage_max_iterations = 10000  # A* iteration limit (prevent infinite loops)
creepage_node_spacing_mm = 0.5  # Grid resolution for uniform sampling (if used)
creepage_obstacle_clearance_mm = 0.1  # Margin around obstacles (avoid edge clipping)

# Visualization options
draw_creepage_paths = false  # Draw all creepage paths (debug mode)
draw_violations_only = true  # Only draw paths that violate requirements
creepage_path_color = "blue"  # Color for valid paths
creepage_violation_color = "red"  # Color for violations

# Performance tuning
creepage_spatial_grid_size_mm = 5.0  # Quad-tree cell size
creepage_max_obstacle_count = 5000  # Cache up to N obstacles per layer
creepage_fast_rejection_factor = 2.0  # If clearance > factor × required, skip creepage
```

### Required Creepage Tables

Already exist in current `emc_rules.toml`:
- `[[clearance_creepage.iec60664_creepage_table]]` - 12 tables (material × pollution)
- Interpolation and lookup reuse existing `_interpolate_clearance_table()` logic

---

## Testing Strategy

### Unit Tests

1. **Test obstacle detection:**
   ```python
   def test_line_crosses_obstacle():
       obstacle = Rectangle(0, 0, 10, 10)
       line = Line((-5, 5), (15, 5))
       assert path_crosses_obstacle(line, [obstacle]) == True
   ```

2. **Test A* finds optimal path:**
   ```python
   def test_astar_optimal():
       # U-shaped obstacle
       path = astar(start=(0,0), goal=(10,0), obstacles=[...])
       assert path.length == 20.0  # Must go around, not through
   ```

3. **Test slot detection:**
   ```python
   def test_path_crosses_slot():
       slot = Rectangle(5, 0, 6, 10)  # Vertical slot
       path = Line(0, 0, 10, 0)
       assert path_crosses_board_edge(path, board_with_slots) == True
   ```

### Integration Tests

Use real PCB design (existing test board):
1. Load board with known mains/SELV domains
2. Run creepage check
3. Verify expected violations found (manual inspection)
4. Verify performance < 10 seconds for 100-pad board

---

## Risk Assessment

### High Risk

❌ **Performance:** A* could be too slow for large boards (10,000+ pads)
   - Mitigation: Implement spatial pruning first
   - Fallback: Offer "fast mode" that checks only closest pairs

❌ **Slots/Cutouts:** Complex board edge detection (curved slots, non-closed contours)
   - Mitigation: Warn user if Edge.Cuts layer is malformed
   - Fallback: Assume no slots for first implementation

### Medium Risk

⚠️ **Multi-layer:** Via barrel creepage calculation may not match all standards
   - Mitigation: Make calculation configurable (IEC vs IPC)
   - Document assumptions clearly

⚠️ **Obstacle simplification:** Merging shapes could miss narrow gaps
   - Mitigation: Set minimum gap width threshold (0.5mm)

### Low Risk

✅ **Algorithm correctness:** A* is well-established
✅ **API availability:** KiCAD provides all needed polygon operations
✅ **Configuration:** Can reuse existing tables and structure

---

## Development Timeline

| Phase | Description | Lines | Hours | Dependencies |
|-------|-------------|-------|-------|--------------|
| 1 | Foundation & structure | 200-300 | 5-8 | None |
| 2 | Obstacle detection | 150-200 | 4-6 | Phase 1 |
| 3 | A* pathfinding core | 250-350 | 8-12 | Phase 1, 2 |
| 4 | Slot/cutout detection | 150-200 | 4-6 | Phase 3 |
| 5 | Multi-layer handling | 100-150 | 3-5 | Phase 3 |
| 6 | Visualization | 100-150 | 2-4 | Phase 3 |
| **TOTAL** | **Complete implementation** | **950-1350** | **26-41** | - |

**Buffer for debugging/testing:** +20% = 31-49 hours total

---

## Alternative Approaches

### Option A: Simplified Heuristic (FAST BUT APPROXIMATE)

Instead of true pathfinding, use conservative approximation:

```python
def calculate_creepage_approximate(pad_a, pad_b):
    """
    Approximate creepage = clearance × path_complexity_factor
    
    If obstacles between pads:
        factor = 1.5 (path must go around)
    Else:
        factor = 1.0 (straight line)
    """
    clearance = calculate_clearance(pad_a, pad_b)
    
    obstacles_between = count_obstacles_in_line(pad_a, pad_b)
    if obstacles_between > 0:
        factor = 1.5  # Conservative approximation
    else:
        factor = 1.0
    
    return clearance * factor
```

**Pros:**
- Very fast (1000× faster than A*)
- Simple implementation (50 lines)
- Conservative (always overestimates creepage)

**Cons:**
- Not accurate (could miss violations)
- Cannot visualize actual path
- Not IEC60664-1 compliant (requires shortest surface path)

**Verdict:** Only use for initial quick-check, not for certification.

---

### Option B: Manual Annotation (USER-DRIVEN)

Let user manually specify creepage-critical areas:

```toml
[[clearance_creepage.critical_creepage_zones]]
name = "Mains Isolation Barrier"
domain_a = "MAINS_L"
domain_b = "EXTRA_LOW_VOLTAGE"
override_creepage_mm = 8.0  # User manually verified this is sufficient
```

**Pros:**
- No algorithm needed
- User has full control
- Suitable for certification (engineer review)

**Cons:**
- Manual work required
- Error-prone (user could miss violations)
- Not scalable to large boards

**Verdict:** Good complement to automated checking, not replacement.

---

## Recommendation

### Implementation Strategy

**Phase 1 (MVP - 10 hours):** Foundation + obstacle detection
- Get something working end-to-end
- Test on simple board (no slots, single layer)
- Measure performance baseline

**Phase 2 (Core - 20 hours):** A* pathfinding + optimizations
- Implement full algorithm
- Add spatial pruning and fast rejection
- Achieve <10s performance on real boards

**Phase 3 (Complete - 10 hours):** Slots + multi-layer + visualization
- Handle edge cases
- Polish reporting
- User testing and feedback

**Total Estimate:** 40 hours (1 week full-time)

---

## References

### Algorithm Resources

- **A* Pathfinding:** [Red Blob Games Tutorial](https://www.redblobgames.com/pathfinding/a-star/introduction.html)
- **Line-Polygon Intersection:** Computational Geometry (O'Rourke, 1998)
- **Visibility Graphs:** [Algorithm Implementation](https://en.wikipedia.org/wiki/Visibility_graph)

### Standards

- **IEC60664-1:2020** - Insulation coordination (Annex F: Tables)
- **IPC2221B:2018** - Generic Standard on Printed Board Design (Section 6)

### KiCAD API

- **Python Scripting:** [KiCAD Documentation](https://docs.kicad.org/doxygen-python/)
- **SHAPE_POLY_SET:** Polygon manipulation class
- **pcbnew Module:** Python bindings for PCB board access

---

## Next Steps

1. **Review this plan** - Get feedback on approach and timeline
2. **Prototype Phase 1** - Implement foundation to validate API usage
3. **Performance benchmark** - Test A* on real board to confirm estimates
4. **Iterate** - Adjust algorithm based on real-world performance
5. **Full implementation** - Complete all phases
6. **User testing** - Validate with safety-critical designs

---

**Questions? Concerns? Ready to start?**
