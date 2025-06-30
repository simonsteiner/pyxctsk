# pg_path_opt.py
import numpy as np
from scipy.optimize import minimize_scalar, brentq
from geographiclib.geodesic import Geodesic
from collections import namedtuple

# Define data structures for points and gates
Point = namedtuple("Point", ["lat", "lon"])
Gate = namedtuple("Gate", ["type", "center", "radius"])


class GeodesicTools:
    """A collection of helper methods for geodesic calculations on the WGS84 ellipsoid."""

    def __init__(self, geod: Geodesic = Geodesic.WGS84):
        self.geod = geod

    def get_distance(self, p1: Point, p2: Point) -> float:
        """Calculates the geodesic distance between two points."""
        return self.geod.Inverse(p1.lat, p1.lon, p2.lat, p2.lon)["s12"]

    def get_point_on_azimuth(self, p: Point, azimuth: float, distance: float) -> Point:
        """Calculates a point at a given azimuth and distance from another point."""
        g = self.geod.Direct(p.lat, p.lon, azimuth, distance)
        return Point(g["lat2"], g["lon2"])

    def _get_path_length(self, points: list[Point]) -> float:
        """Calculates the total length of a path defined by a sequence of points."""
        if not points or len(points) < 2:
            return 0.0
        total_dist = 0.0
        for i in range(len(points) - 1):
            total_dist += self.get_distance(points[i], points[i + 1])
        return total_dist

    def _find_pcp_reflection_point(
        self, p_prev: Point, p_next: Point, gate: Gate
    ) -> Point:
        """
        Solves the Point-Circle-Point (PCP) problem for the reflection case.
        Finds a point 'p' on the gate's circumference that minimizes dist(p_prev, p) + dist(p, p_next).
        This is a 1D minimization problem over the angle on the circle.
        """

        def objective_func(azimuth: float) -> float:
            # Candidate point on the circle boundary
            p_on_circle = self.get_point_on_azimuth(gate.center, azimuth, gate.radius)
            # Total distance from p_prev -> p_on_circle -> p_next
            return self.get_distance(p_prev, p_on_circle) + self.get_distance(
                p_next, p_on_circle
            )

        # Minimize the objective function over all possible azimuths [0, 360)
        result = minimize_scalar(objective_func, bounds=(0, 360), method="bounded")
        optimal_azimuth = result.x

        return self.get_point_on_azimuth(gate.center, optimal_azimuth, gate.radius)

    def _find_intersection_point(
        self, p_prev: Point, p_next: Point, gate: Gate
    ) -> Point:
        """
        Solves the "crossing situation" by finding the intersection of the geodesic
        p_prev -> p_next and the gate's circle that is closer to p_prev.
        """
        geodesic_line = self.geod.Inverse(
            p_prev.lat, p_prev.lon, p_next.lat, p_next.lon
        )
        azi1 = geodesic_line["azi1"]

        # Define a function whose root is the intersection distance
        def objective_func(dist_from_prev: float) -> float:
            # Point on the geodesic at a certain distance from p_prev
            p_on_geodesic = self.get_point_on_azimuth(p_prev, azi1, dist_from_prev)
            # Its distance to the gate's center minus the radius
            return self.get_distance(p_on_geodesic, gate.center) - gate.radius

        # Find the point of closest approach on the geodesic to the circle center
        # This helps establish a search bracket for the root-finding algorithm
        def closest_approach_objective(dist_from_prev: float) -> float:
            p_on_geodesic = self.get_point_on_azimuth(p_prev, azi1, dist_from_prev)
            return self.get_distance(p_on_geodesic, gate.center)

        res = minimize_scalar(closest_approach_objective)
        s_closest = res.x

        # The two intersection points are on either side of the closest point.
        # We find the one closer to p_prev (smaller s value).
        s_root = brentq(objective_func, a=0, b=s_closest)

        return self.get_point_on_azimuth(p_prev, azi1, s_root)

    def _get_optimal_point(self, p_prev: Point, p_next: Point, gate: Gate) -> Point:
        """
        Determines if the problem is a "crossing" or "reflection" case and solves for
        the optimal point on the gate's circumference. This function is an adaptation
        of Algorithm 1 (GetoptPi) from the source paper. [cite: 78]
        """
        # A point is inside if its distance to the center is less than the radius.
        prev_is_inside = self.get_distance(p_prev, gate.center) < gate.radius
        next_is_inside = self.get_distance(p_next, gate.center) < gate.radius

        # As per the paper's geometric analysis (Theorem 1), if one point is inside and
        # the other is outside, it is always a crossing situation. [cite: 53]
        if prev_is_inside != next_is_inside:
            return self._find_intersection_point(p_prev, p_next, gate)

        # If both points are inside the circle, it is always a reflection situation. [cite: 54]
        if prev_is_inside and next_is_inside:
            return self._find_pcp_reflection_point(p_prev, p_next, gate)

        # If both points are outside, we must determine if the geodesic crosses the circle.
        # Find the point of closest approach of the geodesic p_prev->p_next to the gate center.
        geodesic_line = self.geod.Inverse(
            p_prev.lat, p_prev.lon, p_next.lat, p_next.lon
        )
        azi1 = geodesic_line["azi1"]

        def closest_approach_dist(dist_from_prev: float) -> float:
            p_on_geodesic = self.get_point_on_azimuth(p_prev, azi1, dist_from_prev)
            return self.get_distance(p_on_geodesic, gate.center)

        res = minimize_scalar(
            closest_approach_dist, bounds=(0, geodesic_line["s12"]), method="bounded"
        )
        min_dist_to_center = res.fun

        # If the minimum distance from the geodesic to the center is less than the radius,
        # the path intersects the circle (crossing situation). [cite: 43]
        if min_dist_to_center <= gate.radius:
            return self._find_intersection_point(p_prev, p_next, gate)
        # Otherwise, it's a reflection situation. [cite: 38]
        else:
            return self._find_pcp_reflection_point(p_prev, p_next, gate)


def optimize_path(
    gates: list[Gate],
    geod: Geodesic = Geodesic.WGS84,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> tuple[list[tuple], float]:
    """
    Computes the shortest feasible flight path for a paragliding task.

    This function implements the Odd-Even alternating optimization scheme described
    in "An Efficient Algorithm for Touring n Circles", adapted for the WGS84 ellipsoid. [cite: 1]

    Args:
        gates: An ordered list of Gate objects defining the course.
        geod: An instance of geographiclib.geodesic.Geodesic (default: WGS84).
        max_iter: The maximum number of optimization iterations.
        tol: The convergence tolerance on path length change (in meters).

    Returns:
        A tuple containing:
        - route: A list of (lat, lon) tuples for the optimal contact points.
        - length: The total geodesic distance of the optimized path in meters.
    """
    n = len(gates)
    if n < 2:
        return ([], 0.0)

    tools = GeodesicTools(geod)

    # --- Initialization Step ---
    # Per the paper, we start with an initial path. [cite: 71, 97]
    # A simple greedy initialization is used: each point is the one on its gate's
    # boundary closest to the previous point in the sequence.
    route_points = [Point(0, 0)] * n

    # First point is on gate 0, closest to the center of gate 1.
    g = geod.Inverse(
        gates[0].center.lat,
        gates[0].center.lon,
        gates[1].center.lat,
        gates[1].center.lon,
    )
    route_points[0] = tools.get_point_on_azimuth(
        gates[0].center, g["azi1"], gates[0].radius
    )

    for i in range(1, n):
        g = geod.Inverse(
            gates[i].center.lat,
            gates[i].center.lon,
            route_points[i - 1].lat,
            route_points[i - 1].lon,
        )
        route_points[i] = tools.get_point_on_azimuth(
            gates[i].center, g["azi1"], gates[i].radius
        )

    last_len = tools._get_path_length(route_points)

    # --- Iteration Step ---
    # The algorithm iterates until the change in path length is below the tolerance
    # or the max number of iterations is reached. [cite: 75, 89]
    for _ in range(max_iter):
        # --- Update Odd-indexed Gates (1, 3, 5, ...) ---
        # The contact points on even circles are fixed, and we find the optimal
        # points on the odd circles. [cite: 72]
        for i in range(1, n, 2):
            if i + 1 < n:
                route_points[i] = tools._get_optimal_point(
                    route_points[i - 1], route_points[i + 1], gates[i]
                )

        # --- Update Even-indexed Gates (0, 2, 4, ...) ---
        # The contact points on odd circles are now fixed, and we find the optimal
        # points on the even circles. [cite: 73]
        for i in range(0, n, 2):
            if i == 0:
                if n > 1:  # The first point is only influenced by the next point
                    g = geod.Inverse(
                        gates[i].center.lat,
                        gates[i].center.lon,
                        route_points[i + 1].lat,
                        route_points[i + 1].lon,
                    )
                    route_points[i] = tools.get_point_on_azimuth(
                        gates[i].center, g["azi1"], gates[i].radius
                    )
            elif i == n - 1:  # The last point is only influenced by the previous point
                g = geod.Inverse(
                    gates[i].center.lat,
                    gates[i].center.lon,
                    route_points[i - 1].lat,
                    route_points[i - 1].lon,
                )
                route_points[i] = tools.get_point_on_azimuth(
                    gates[i].center, g["azi1"], gates[i].radius
                )
            else:
                route_points[i] = tools._get_optimal_point(
                    route_points[i - 1], route_points[i + 1], gates[i]
                )

        current_len = tools._get_path_length(route_points)

        # Check for convergence
        if abs(last_len - current_len) < tol:
            break
        last_len = current_len

    # Format output
    final_route_tuples = [(p.lat, p.lon) for p in route_points]
    return final_route_tuples, last_len


# Example Usage from the prompt:
if __name__ == "__main__":
    # Define gates (center lat/lon in degrees; radii in metres)
    # The center points are defined as Point objects for type consistency.
    takeoff = Gate("circle", center=Point(46.521, 6.565), radius=1000)
    sss = Gate("circle", center=Point(46.530, 6.600), radius=2000)
    tp1 = Gate("circle", center=Point(46.540, 6.650), radius=2000)
    ess = Gate("circle", center=Point(46.550, 6.700), radius=3000)
    ess2 = Gate("circle", center=Point(46.560, 6.750), radius=2000)
    stp1 = Gate("circle", center=Point(46.570, 6.700), radius=2000)  # safety
    stp2 = Gate("circle", center=Point(46.580, 6.650), radius=2000)  # safety
    goal = Gate("circle", center=Point(46.590, 6.600), radius=1000)

    gates = [takeoff, sss, tp1, ess, ess2, stp1, stp2, goal]

    # Optimize on WGS84
    geod_wgs84 = Geodesic.WGS84
    route, length = optimize_path(gates, geod_wgs84, max_iter=100, tol=1e-6)

    print("Optimized Route (Lat, Lon):")
    for i, (lat, lon) in enumerate(route):
        print(f"  Gate {i}: ({lat:.6f}, {lon:.6f})")

    print(f"\nTotal geodesic distance: {length:.2f} m")
