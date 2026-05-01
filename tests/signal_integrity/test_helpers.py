"""
Unit tests for signal integrity helper methods.

Tests the helper functions used by stub detection and length matching checks.
"""

import pytest


class TestCalculateTraceLength:
    """Test _calculate_trace_length() helper method."""
    
    def test_empty_net_returns_zero(self, signal_integrity_checker):
        """Empty net should return 0 length."""
        # This would need a mock board with an empty net
        # For now, just verify the method exists and has correct signature
        checker = signal_integrity_checker
        assert hasattr(checker, '_calculate_trace_length')
        assert callable(checker._calculate_trace_length)
    
    def test_calculates_segment_lengths(self, signal_integrity_checker):
        """Should sum all track segment lengths."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_includes_via_heights(self, signal_integrity_checker):
        """Should add vertical via heights to total length."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_handles_string_net_name(self, signal_integrity_checker):
        """Should accept both NETINFO_ITEM and string net names."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")


class TestBuildConnectivityGraph:
    """Test _build_connectivity_graph() helper method."""
    
    def test_empty_net_returns_empty_graph(self, signal_integrity_checker):
        """Empty net should return graph with no nodes/edges."""
        # This would need a mock board with an empty net
        checker = signal_integrity_checker
        assert hasattr(checker, '_build_connectivity_graph')
        assert callable(checker._build_connectivity_graph)
    
    def test_creates_nodes_for_pads(self, signal_integrity_checker):
        """Should create nodes for all pads on net."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_creates_nodes_for_vias(self, signal_integrity_checker):
        """Should create nodes for all vias on net."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_creates_nodes_for_track_endpoints(self, signal_integrity_checker):
        """Should create nodes for track segment endpoints."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_creates_edges_for_tracks(self, signal_integrity_checker):
        """Should create edges connecting track endpoints."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_snaps_coincident_points(self, signal_integrity_checker):
        """Should merge points within 10µm tolerance."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_bidirectional_connections(self, signal_integrity_checker):
        """Graph edges should be bidirectional (undirected graph)."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_handles_string_net_name(self, signal_integrity_checker):
        """Should accept both NETINFO_ITEM and string net names."""
        # TODO: Implement with MockBoard fixture
        pytest.skip("Requires MockBoard fixture implementation")
    
    def test_returns_correct_structure(self, signal_integrity_checker):
        """Should return dict with 'nodes' and 'edges' keys."""
        checker = signal_integrity_checker
        # Test with a mock empty result
        result = checker._build_connectivity_graph("NonExistentNet")
        assert isinstance(result, dict)
        assert 'nodes' in result
        assert 'edges' in result
        assert isinstance(result['nodes'], dict)
        assert isinstance(result['edges'], list)


@pytest.fixture
def signal_integrity_checker(mock_board):
    """Fixture providing a SignalIntegrityChecker instance."""
    import sys
    from pathlib import Path
    
    # Add src directory to path
    src_dir = Path(__file__).parent.parent.parent / 'src'
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    from signal_integrity import SignalIntegrityChecker
    
    # Mock configuration
    config = {
        'critical_net_classes': ['HighSpeed', 'Clock'],
        'max_length_by_netclass': {'HighSpeed': 150.0}
    }
    
    checker = SignalIntegrityChecker(
        board=mock_board,
        marker_layer=0,
        config=config,
        report_lines=[],
        verbose=True,
        auditor=None
    )
    
    # Initialize log function (normally injected during check())
    checker.log = lambda msg, force=False: None
    
    return checker


@pytest.fixture
def mock_board():
    """Mock board for testing."""
    # TODO: Implement proper MockBoard class
    class MockBoard:
        def FindNet(self, net_name):
            """Mock FindNet that returns None for unknown nets."""
            return None
        
        def GetTracks(self):
            """Mock GetTracks that returns empty list."""
            return []
        
        def GetFootprints(self):
            """Mock GetFootprints that returns empty list."""
            return []
    
    return MockBoard()
