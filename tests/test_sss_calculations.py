"""Tests for SSS (Start Speed Section) calculations."""

from unittest.mock import Mock, patch

from pyxctsk.sss_calculations import (
    _find_sss_turnpoint,
    _get_first_tp_after_sss_point,
    calculate_optimal_sss_entry_point,
    calculate_sss_info,
)
from pyxctsk.turnpoint import TaskTurnpoint


class TestCalculateOptimalSSSEntryPoint:
    """Test the calculate_optimal_sss_entry_point function."""

    def test_calculate_optimal_entry_point_basic(self):
        """Test basic optimal SSS entry point calculation."""
        # Create a mock SSS turnpoint
        sss_turnpoint = TaskTurnpoint(46.5, 8.0, 400.0)
        takeoff_center = (46.0, 8.0)
        first_tp_after_sss = (47.0, 8.0)

        entry_point = calculate_optimal_sss_entry_point(
            sss_turnpoint, takeoff_center, first_tp_after_sss
        )

        # Entry point should be a valid coordinate tuple
        assert isinstance(entry_point, tuple)
        assert len(entry_point) == 2
        assert isinstance(entry_point[0], float)
        assert isinstance(entry_point[1], float)

    def test_calculate_optimal_entry_point_custom_angle_step(self):
        """Test optimal SSS entry point with custom angle step."""
        sss_turnpoint = TaskTurnpoint(46.5, 8.0, 400.0)
        takeoff_center = (46.0, 8.0)
        first_tp_after_sss = (47.0, 8.0)

        entry_point = calculate_optimal_sss_entry_point(
            sss_turnpoint, takeoff_center, first_tp_after_sss, angle_step=45
        )

        # Should still return a valid point
        assert isinstance(entry_point, tuple)
        assert len(entry_point) == 2

    def test_calculate_optimal_entry_point_collinear(self):
        """Test optimal entry point when points are collinear."""
        sss_turnpoint = TaskTurnpoint(46.5, 8.0, 400.0)
        takeoff_center = (46.0, 8.0)  # South of SSS
        first_tp_after_sss = (47.0, 8.0)  # North of SSS

        entry_point = calculate_optimal_sss_entry_point(
            sss_turnpoint, takeoff_center, first_tp_after_sss
        )

        # Entry point should be close to the direct line
        assert isinstance(entry_point, tuple)
        assert len(entry_point) == 2
        # Should have same longitude as the line is north-south
        assert abs(entry_point[1] - 8.0) < 0.01

    def test_calculate_optimal_entry_point_90_degree(self):
        """Test optimal entry point with 90-degree approach."""
        sss_turnpoint = TaskTurnpoint(46.5, 8.0, 400.0)
        takeoff_center = (46.5, 7.5)  # West of SSS
        first_tp_after_sss = (46.5, 8.5)  # East of SSS

        entry_point = calculate_optimal_sss_entry_point(
            sss_turnpoint, takeoff_center, first_tp_after_sss
        )

        # Should be valid point
        assert isinstance(entry_point, tuple)
        assert len(entry_point) == 2

    def test_calculate_optimal_entry_point_zero_radius(self):
        """Test optimal entry point with zero radius SSS."""
        sss_turnpoint = TaskTurnpoint(46.5, 8.0, 0.0)
        takeoff_center = (46.0, 8.0)
        first_tp_after_sss = (47.0, 8.0)

        entry_point = calculate_optimal_sss_entry_point(
            sss_turnpoint, takeoff_center, first_tp_after_sss
        )

        # Should return the center point for zero radius
        assert entry_point == sss_turnpoint.center


class TestFindSSSTP:
    """Test the _find_sss_turnpoint function."""

    def test_find_sss_turnpoint_found(self):
        """Test finding SSS turnpoint when present."""
        # Create mock turnpoints
        mock_tp1 = Mock()
        mock_tp1.type = Mock()
        mock_tp1.type.value = "TAKEOFF"

        mock_tp2 = Mock()
        mock_tp2.type = Mock()
        mock_tp2.type.value = "SSS"

        mock_tp3 = Mock()
        mock_tp3.type = Mock()
        mock_tp3.type.value = "ESS"

        turnpoints = [mock_tp1, mock_tp2, mock_tp3]

        result = _find_sss_turnpoint(turnpoints)

        assert result is not None
        assert result[0] == 1  # Index
        assert result[1] == mock_tp2  # Turnpoint

    def test_find_sss_turnpoint_not_found(self):
        """Test finding SSS turnpoint when not present."""
        # Create mock turnpoints without SSS
        mock_tp1 = Mock()
        mock_tp1.type = Mock()
        mock_tp1.type.value = "TAKEOFF"

        mock_tp2 = Mock()
        mock_tp2.type = Mock()
        mock_tp2.type.value = "ESS"

        turnpoints = [mock_tp1, mock_tp2]

        result = _find_sss_turnpoint(turnpoints)

        assert result is None

    def test_find_sss_turnpoint_no_type_attribute(self):
        """Test finding SSS turnpoint when turnpoint has no type."""
        mock_tp1 = Mock()
        del mock_tp1.type  # Remove type attribute

        turnpoints = [mock_tp1]

        result = _find_sss_turnpoint(turnpoints)

        assert result is None

    def test_find_sss_turnpoint_none_type(self):
        """Test finding SSS turnpoint when type is None."""
        mock_tp1 = Mock()
        mock_tp1.type = None

        turnpoints = [mock_tp1]

        result = _find_sss_turnpoint(turnpoints)

        assert result is None

    def test_find_sss_turnpoint_empty_list(self):
        """Test finding SSS turnpoint in empty list."""
        result = _find_sss_turnpoint([])
        assert result is None


class TestGetFirstTPAfterSSS:
    """Test the _get_first_tp_after_sss_point function."""

    def test_get_first_tp_after_sss_with_route(self):
        """Test getting first TP after SSS with route coordinates."""
        # Create mock turnpoints
        mock_tp1 = Mock()
        mock_tp1.waypoint = Mock()
        mock_tp1.waypoint.lat = 46.0
        mock_tp1.waypoint.lon = 8.0

        mock_tp2 = Mock()
        mock_tp2.waypoint = Mock()
        mock_tp2.waypoint.lat = 46.5
        mock_tp2.waypoint.lon = 8.0

        mock_tp3 = Mock()
        mock_tp3.waypoint = Mock()
        mock_tp3.waypoint.lat = 47.0
        mock_tp3.waypoint.lon = 8.0

        turnpoints = [mock_tp1, mock_tp2, mock_tp3]
        sss_index = 1  # mock_tp2 is SSS
        route_coordinates = [(46.0, 8.0), (47.0, 8.0), (47.5, 8.0)]

        result = _get_first_tp_after_sss_point(turnpoints, sss_index, route_coordinates)

        assert result is not None
        tp_dict, route_point = result

        # Check turnpoint dict
        assert tp_dict["lat"] == 47.0
        assert tp_dict["lon"] == 8.0

        # Check route point (should be route_coordinates[1])
        assert route_point == (47.0, 8.0)

    def test_get_first_tp_after_sss_no_route(self):
        """Test getting first TP after SSS without route coordinates."""
        mock_tp1 = Mock()
        mock_tp1.waypoint = Mock()
        mock_tp1.waypoint.lat = 46.0
        mock_tp1.waypoint.lon = 8.0

        mock_tp2 = Mock()
        mock_tp2.waypoint = Mock()
        mock_tp2.waypoint.lat = 47.0
        mock_tp2.waypoint.lon = 8.0

        turnpoints = [mock_tp1, mock_tp2]
        sss_index = 0  # mock_tp1 is SSS
        route_coordinates = []  # Empty route

        result = _get_first_tp_after_sss_point(turnpoints, sss_index, route_coordinates)

        assert result is not None
        tp_dict, route_point = result

        # Check turnpoint dict
        assert tp_dict["lat"] == 47.0
        assert tp_dict["lon"] == 8.0

        # Check route point (should fallback to center)
        assert route_point == (47.0, 8.0)

    def test_get_first_tp_after_sss_single_route_point(self):
        """Test getting first TP after SSS with single route point."""
        mock_tp1 = Mock()
        mock_tp1.waypoint = Mock()
        mock_tp1.waypoint.lat = 46.0
        mock_tp1.waypoint.lon = 8.0

        mock_tp2 = Mock()
        mock_tp2.waypoint = Mock()
        mock_tp2.waypoint.lat = 47.0
        mock_tp2.waypoint.lon = 8.0

        turnpoints = [mock_tp1, mock_tp2]
        sss_index = 0
        route_coordinates = [(46.0, 8.0)]  # Only one point

        result = _get_first_tp_after_sss_point(turnpoints, sss_index, route_coordinates)

        assert result is not None
        tp_dict, route_point = result

        # Should fallback to center coordinates
        assert route_point == (47.0, 8.0)

    def test_get_first_tp_after_sss_no_next_tp(self):
        """Test getting first TP after SSS when SSS is last turnpoint."""
        mock_tp1 = Mock()
        mock_tp1.waypoint = Mock()
        mock_tp1.waypoint.lat = 46.0
        mock_tp1.waypoint.lon = 8.0

        turnpoints = [mock_tp1]
        sss_index = 0  # SSS is the only/last turnpoint
        route_coordinates = [(46.0, 8.0)]

        result = _get_first_tp_after_sss_point(turnpoints, sss_index, route_coordinates)

        assert result is None

    def test_get_first_tp_after_sss_out_of_bounds(self):
        """Test getting first TP after SSS with out of bounds index."""
        mock_tp1 = Mock()
        mock_tp1.waypoint = Mock()
        mock_tp1.waypoint.lat = 46.0
        mock_tp1.waypoint.lon = 8.0

        turnpoints = [mock_tp1]
        sss_index = 5  # Out of bounds
        route_coordinates = [(46.0, 8.0)]

        result = _get_first_tp_after_sss_point(turnpoints, sss_index, route_coordinates)

        assert result is None


class TestCalculateSSSInfo:
    """Test the calculate_sss_info function."""

    def test_calculate_sss_info_basic(self):
        """Test basic SSS info calculation."""
        # Create mock turnpoints
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0
        mock_takeoff.type = Mock()
        mock_takeoff.type.value = "TAKEOFF"

        mock_sss = Mock()
        mock_sss.waypoint = Mock()
        mock_sss.waypoint.lat = 46.5
        mock_sss.waypoint.lon = 8.0
        mock_sss.radius = 400
        mock_sss.type = Mock()
        mock_sss.type.value = "SSS"

        mock_tp = Mock()
        mock_tp.waypoint = Mock()
        mock_tp.waypoint.lat = 47.0
        mock_tp.waypoint.lon = 8.0
        mock_tp.type = Mock()
        mock_tp.type.value = "ESS"

        turnpoints = [mock_takeoff, mock_sss, mock_tp]
        route_coordinates = [(46.0, 8.0), (47.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is not None
        assert "sss_center" in result
        assert "optimal_entry_point" in result
        assert "first_tp_after_sss" in result
        assert "takeoff_center" in result

        # Check SSS center
        assert result["sss_center"]["lat"] == 46.5
        assert result["sss_center"]["lon"] == 8.0
        assert result["sss_center"]["radius"] == 400

        # Check takeoff center
        assert result["takeoff_center"]["lat"] == 46.0
        assert result["takeoff_center"]["lon"] == 8.0

        # Check first TP after SSS
        assert result["first_tp_after_sss"]["lat"] == 47.0
        assert result["first_tp_after_sss"]["lon"] == 8.0

    def test_calculate_sss_info_custom_angle_step(self):
        """Test SSS info calculation with custom angle step."""
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0

        mock_sss = Mock()
        mock_sss.waypoint = Mock()
        mock_sss.waypoint.lat = 46.5
        mock_sss.waypoint.lon = 8.0
        mock_sss.radius = 400
        mock_sss.type = Mock()
        mock_sss.type.value = "SSS"

        mock_tp = Mock()
        mock_tp.waypoint = Mock()
        mock_tp.waypoint.lat = 47.0
        mock_tp.waypoint.lon = 8.0

        turnpoints = [mock_takeoff, mock_sss, mock_tp]
        route_coordinates = [(46.0, 8.0), (47.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates, angle_step=45)

        assert result is not None
        assert "optimal_entry_point" in result

    def test_calculate_sss_info_no_sss(self):
        """Test SSS info calculation when no SSS turnpoint."""
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0
        mock_takeoff.type = Mock()
        mock_takeoff.type.value = "TAKEOFF"

        mock_tp = Mock()
        mock_tp.waypoint = Mock()
        mock_tp.waypoint.lat = 47.0
        mock_tp.waypoint.lon = 8.0
        mock_tp.type = Mock()
        mock_tp.type.value = "ESS"

        turnpoints = [mock_takeoff, mock_tp]
        route_coordinates = [(46.0, 8.0), (47.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is None

    def test_calculate_sss_info_empty_turnpoints(self):
        """Test SSS info calculation with empty turnpoints."""
        result = calculate_sss_info([], [])
        assert result is None

    def test_calculate_sss_info_insufficient_turnpoints(self):
        """Test SSS info calculation with insufficient turnpoints."""
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0

        turnpoints = [mock_takeoff]  # Only one turnpoint
        route_coordinates = [(46.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is None

    def test_calculate_sss_info_no_tp_after_sss(self):
        """Test SSS info calculation when no turnpoint after SSS."""
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0

        mock_sss = Mock()
        mock_sss.waypoint = Mock()
        mock_sss.waypoint.lat = 46.5
        mock_sss.waypoint.lon = 8.0
        mock_sss.radius = 400
        mock_sss.type = Mock()
        mock_sss.type.value = "SSS"

        turnpoints = [mock_takeoff, mock_sss]  # SSS is last turnpoint
        route_coordinates = [(46.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is None

    @patch("pyxctsk.sss_calculations.calculate_optimal_sss_entry_point")
    def test_calculate_sss_info_integration(self, mock_calc_optimal):
        """Test SSS info calculation integration with optimization function."""
        # Mock the optimization function to return a known point
        mock_calc_optimal.return_value = (46.4, 8.0)

        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0

        mock_sss = Mock()
        mock_sss.waypoint = Mock()
        mock_sss.waypoint.lat = 46.5
        mock_sss.waypoint.lon = 8.0
        mock_sss.radius = 400
        mock_sss.type = Mock()
        mock_sss.type.value = "SSS"

        mock_tp = Mock()
        mock_tp.waypoint = Mock()
        mock_tp.waypoint.lat = 47.0
        mock_tp.waypoint.lon = 8.0

        turnpoints = [mock_takeoff, mock_sss, mock_tp]
        route_coordinates = [(46.0, 8.0), (47.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is not None
        assert result["optimal_entry_point"]["lat"] == 46.4
        assert result["optimal_entry_point"]["lon"] == 8.0

        # Verify the optimization function was called with correct parameters
        mock_calc_optimal.assert_called_once()

    def test_calculate_sss_info_multiple_sss(self):
        """Test SSS info calculation with multiple SSS turnpoints (should find first)."""
        mock_takeoff = Mock()
        mock_takeoff.waypoint = Mock()
        mock_takeoff.waypoint.lat = 46.0
        mock_takeoff.waypoint.lon = 8.0

        mock_sss1 = Mock()
        mock_sss1.waypoint = Mock()
        mock_sss1.waypoint.lat = 46.3
        mock_sss1.waypoint.lon = 8.0
        mock_sss1.radius = 300
        mock_sss1.type = Mock()
        mock_sss1.type.value = "SSS"

        mock_sss2 = Mock()
        mock_sss2.waypoint = Mock()
        mock_sss2.waypoint.lat = 46.7
        mock_sss2.waypoint.lon = 8.0
        mock_sss2.radius = 500
        mock_sss2.type = Mock()
        mock_sss2.type.value = "SSS"

        mock_tp = Mock()
        mock_tp.waypoint = Mock()
        mock_tp.waypoint.lat = 47.0
        mock_tp.waypoint.lon = 8.0

        turnpoints = [mock_takeoff, mock_sss1, mock_sss2, mock_tp]
        route_coordinates = [(46.0, 8.0), (47.0, 8.0)]

        result = calculate_sss_info(turnpoints, route_coordinates)

        assert result is not None
        # Should use the first SSS turnpoint found
        assert result["sss_center"]["lat"] == 46.3
        assert result["sss_center"]["radius"] == 300
