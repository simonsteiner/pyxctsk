"""Turnpoint geometry and optimization utilities for XCTrack task calculations.

This module provides:
- The `TaskTurnpoint` class: immutable turnpoint model for paragliding/hang gliding tasks
- Earth-model helpers (WGS84 ellipsoid or FAI sphere, R = 6371 km) shared by the
  distance subsystem
- The planar "GetOptPi" primitive from Ding, Xie & Jiang, "An Efficient Algorithm
  for Touring n Circles" (MATEC Web of Conferences 232, 03027, EITCE 2018): the
  optimal point on a circle between two fixed neighbours, distinguishing the
  *crossing* case (the segment between the neighbours intersects the circle, or
  one neighbour lies inside it) from the *reflection* (point-circle-point) case
- Local Transverse Mercator projection helpers (FAI Sporting Code S7F §7.1.2)
  so point placement happens in a plane centred on the area of interest, with
  results snapped back onto the true cylinder boundary (§7.1.7)
- Distance and geometry utilities for cylinders and goal lines

Intended for use in parsing, generating, and optimizing XCTrack tasks.
"""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, Sequence, runtime_checkable

from pyproj import CRS, Geod, Transformer
from scipy.optimize import fminbound

#: Radius of the FAI sphere earth model in meters (FAI Sporting Code S7F).
FAI_SPHERE_RADIUS_M = 6_371_000.0

# Geodesic engines for the two supported earth models. A sphere with equal
# semi-axes makes pyproj's Karney solver compute exact great-circle distances.
_WGS84_GEOD = Geod(ellps="WGS84")
_FAI_SPHERE_GEOD = Geod(a=FAI_SPHERE_RADIUS_M, b=FAI_SPHERE_RADIUS_M)


def _is_fai_sphere(earth_model: object) -> bool:
    """Return True if the given earth model designates the FAI sphere.

    Args:
        earth_model: An ``EarthModel`` enum member, its string value, or None
            (None means the XCTrack default, WGS84).

    Returns:
        True for the FAI sphere model, False otherwise.
    """
    if earth_model is None:
        return False
    value = getattr(earth_model, "value", earth_model)
    return str(value).upper() == "FAI_SPHERE"


def geod_for_earth_model(earth_model: object = None) -> Geod:
    """Return the geodesic engine for an earth model.

    Args:
        earth_model: An ``EarthModel`` enum member, its string value, or None
            for the WGS84 default.

    Returns:
        A pyproj ``Geod`` on the WGS84 ellipsoid, or on the FAI sphere
        (R = 6 371 000 m) when the FAI sphere model is selected.
    """
    return _FAI_SPHERE_GEOD if _is_fai_sphere(earth_model) else _WGS84_GEOD


def geodesic_distance(
    point1: tuple[float, float],
    point2: tuple[float, float],
    earth_model: object = None,
) -> float:
    """Compute the distance between two (lat, lon) points for an earth model.

    Args:
        point1: (lat, lon) of the first point.
        point2: (lat, lon) of the second point.
        earth_model: Earth model selector (see :func:`geod_for_earth_model`).

    Returns:
        Distance in meters (geodesic on WGS84, great-circle on the FAI sphere).
    """
    g = geod_for_earth_model(earth_model)
    _, _, dist = g.inv(point1[1], point1[0], point2[1], point2[0])
    return float(dist)


def ltm_scale_factor(lat0: float) -> float:
    """Return the LTM scale factor k₀ for a projection centre latitude.

    The one way S7F §7.1.2 says its Localized Transverse Mercator differs from
    UTM in more than centring: "Scaling depends on the centre point's
    latitude". Both of Annex A's reference implementations take the absolute
    latitude first (``double la = abs(refLat)``), so the southern hemisphere
    scales like the northern.

    Args:
        lat0: Latitude of the projection centre in degrees.

    Returns:
        k₀: 0.99994 up to 55°, growing linearly beyond it.
    """
    la = abs(float(lat0))
    if la <= 55.0:
        return 0.99994
    return 0.99994 + ((la - 55.0) / 60.0) * 1.3e-4


@lru_cache(maxsize=128)
def _cached_tm_transformers(
    lat0: float, lon0: float, fai_sphere: bool
) -> tuple[Transformer, Transformer]:
    """Build (and cache) transformers for a local Transverse Mercator plane.

    ``+k_0`` rather than ``+k``: the two are synonyms in PROJ, but the 2026
    edition's own document history records the correction "parameter +k_0
    instead of deprecated +k" against its Annex A sample.
    """
    k0 = ltm_scale_factor(lat0)
    if fai_sphere:
        geo_crs = CRS.from_proj4(f"+proj=longlat +R={FAI_SPHERE_RADIUS_M} +no_defs")
        tm_crs = CRS.from_proj4(
            f"+proj=tmerc +lat_0={lat0} +lon_0={lon0} +k_0={k0} +x_0=0 +y_0=0 "
            f"+R={FAI_SPHERE_RADIUS_M} +units=m +no_defs"
        )
    else:
        geo_crs = CRS.from_epsg(4326)
        tm_crs = CRS.from_proj4(
            f"+proj=tmerc +lat_0={lat0} +lon_0={lon0} +k_0={k0} +x_0=0 +y_0=0 "
            "+ellps=WGS84 +units=m +no_defs"
        )
    to_plane = Transformer.from_crs(geo_crs, tm_crs, always_xy=True)
    to_geo = Transformer.from_crs(tm_crs, geo_crs, always_xy=True)
    return to_plane, to_geo


def local_tm_transformers(
    lat0: float, lon0: float, earth_model: object = None
) -> tuple[Transformer, Transformer]:
    """Return transformers to/from a local Transverse Mercator plane.

    Per FAI Sporting Code S7F §7.1.2, optimal points are placed in a plane
    obtained by a Transverse Mercator projection centred on the area of
    interest, then converted back to geographic coordinates.

    Args:
        lat0: Latitude of the projection centre in degrees.
        lon0: Longitude of the projection centre in degrees.
        earth_model: Earth model selector (see :func:`geod_for_earth_model`).

    Returns:
        ``(to_plane, to_geo)`` transformers; both use (lon, lat) ↔ (x, y)
        axis order (``always_xy``).
    """
    return _cached_tm_transformers(
        float(lat0), float(lon0), _is_fai_sphere(earth_model)
    )


def _segment_circle_intersections(
    p1: tuple[float, float],
    p2: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> list[float]:
    """Find where the planar segment p1→p2 meets a circle boundary.

    Args:
        p1: Segment start (x, y).
        p2: Segment end (x, y).
        center: Circle center (x, y).
        radius: Circle radius (same units as coordinates).

    Returns:
        Sorted parameters ``t`` in [0, 1] (with the point at ``p1 + t*(p2-p1)``)
        where the segment crosses the circle; empty if it does not.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    fx, fy = p1[0] - center[0], p1[1] - center[1]
    a = dx * dx + dy * dy
    if a == 0.0:
        return []
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return []
    sqrt_disc = math.sqrt(disc)
    roots = ((-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a))
    return sorted(t for t in roots if 0.0 <= t <= 1.0)


def _plane_point_at(
    center: tuple[float, float], radius: float, theta: float
) -> tuple[float, float]:
    """Return the boundary point of a planar circle at angle ``theta``."""
    return (center[0] + radius * math.cos(theta), center[1] + radius * math.sin(theta))


def _plane_pcp_point(
    p1: tuple[float, float],
    p2: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    """Solve the reflection (point-circle-point) case in the plane.

    Finds the boundary point minimizing ``|p1 - x| + |x - p2|``. A coarse
    global scan brackets the minimum, then a bounded scalar minimization
    refines it — robust for every endpoint configuration (both neighbours
    outside, or both inside, the circle).

    Args:
        p1: Previous point (x, y).
        p2: Next point (x, y).
        center: Circle center (x, y).
        radius: Circle radius.

    Returns:
        The optimal boundary point (x, y).
    """

    def total(theta: float) -> float:
        x, y = _plane_point_at(center, radius, theta)
        return math.hypot(x - p1[0], y - p1[1]) + math.hypot(x - p2[0], y - p2[1])

    scan = 64
    best_k = min(range(scan), key=lambda k: total(2.0 * math.pi * k / scan))
    lo = 2.0 * math.pi * (best_k - 1) / scan
    hi = 2.0 * math.pi * (best_k + 1) / scan
    theta_opt = float(fminbound(total, lo, hi, xtol=1e-12))
    return _plane_point_at(center, radius, theta_opt)


def plane_optimal_point(
    prev_point: tuple[float, float],
    next_point: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    """Optimal point on a planar circle between two fixed neighbours (GetOptPi).

    Implements Algorithm 1 (GetoptPi) of Ding, Xie & Jiang: if the segment
    between the neighbours crosses the circle boundary — which per their
    Theorem 1 is always the case when exactly one neighbour lies inside the
    circle — the optimal point is the segment-circle intersection (*crossing*
    case, adding no length). Otherwise (both neighbours outside with no
    intersection, or both inside) it is the *reflection* point-circle-point
    solution on the boundary.

    Args:
        prev_point: Previous fixed point (x, y) in the local plane.
        next_point: Next fixed point (x, y) in the local plane.
        center: Circle center (x, y).
        radius: Circle radius in plane units (meters).

    Returns:
        The optimal (x, y) point on the circle boundary (the center for a
        zero-radius circle).
    """
    if radius <= 0.0:
        return center

    d1 = math.hypot(prev_point[0] - center[0], prev_point[1] - center[1])
    d2 = math.hypot(next_point[0] - center[0], next_point[1] - center[1])
    prev_inside = d1 < radius
    next_inside = d2 < radius

    if prev_inside != next_inside:
        # Crossing case: the segment meets the boundary exactly once.
        ts = _segment_circle_intersections(prev_point, next_point, center, radius)
        if ts:
            t = ts[0] if next_inside else ts[-1]
            return (
                prev_point[0] + t * (next_point[0] - prev_point[0]),
                prev_point[1] + t * (next_point[1] - prev_point[1]),
            )
    elif not prev_inside and not next_inside:
        # Both outside: crossing case if the segment passes through the circle.
        ts = _segment_circle_intersections(prev_point, next_point, center, radius)
        if ts:
            t = ts[0]
            return (
                prev_point[0] + t * (next_point[0] - prev_point[0]),
                prev_point[1] + t * (next_point[1] - prev_point[1]),
            )

    # Reflection case (also the numerically-degenerate tangent fallback).
    return _plane_pcp_point(prev_point, next_point, center, radius)


def snap_to_boundary(
    point_lonlat: tuple[float, float],
    center: tuple[float, float],
    radius: float,
    earth_model: object = None,
) -> tuple[float, float]:
    """Snap a point onto a cylinder boundary (ProjectionCorrection, §7.1.7).

    A point placed in the local Transverse Mercator plane does not sit exactly
    at radius ``r`` on the earth model; re-place it at exactly ``r`` along the
    geodesic azimuth from the cylinder center toward it.

    Args:
        point_lonlat: (lon, lat) of the approximate point (transformer axis
            order).
        center: (lat, lon) of the cylinder center.
        radius: Cylinder radius in meters.
        earth_model: Earth model selector (see :func:`geod_for_earth_model`).

    Returns:
        (lat, lon) of the corrected point at exactly ``radius`` meters from
        the center.
    """
    g = geod_for_earth_model(earth_model)
    azimuth, _, _ = g.inv(center[1], center[0], point_lonlat[0], point_lonlat[1])
    lon, lat, _ = g.fwd(center[1], center[0], azimuth, radius)
    return (lat, lon)


def task_area_center(
    points: Sequence[tuple[float, float]],
) -> tuple[float, float]:
    """Return the centre of the area these points occupy (S7F §7.1.6).

    The centre of their bounding box, not their mean: a task with six
    turnpoints clustered at one end and one far away is centred between the
    extremes, so the projection covers the whole of it rather than leaning
    toward wherever the points are dense. The mean is what this used to
    return, and it disagreed with XCTrack's published distance by 72 m on
    ``task_bevo`` where the box centre disagrees by 27 m.

    Longitudes are handled as §7.1.6.1 specifies, which is what makes a task
    straddling the antimeridian work: normalize to (-180, 180], sort, and if
    the largest gap between neighbours exceeds 180° the box is the one that
    wraps *through* that gap rather than the one spanning nearly the globe.
    Averaging longitudes directly would put the centre of a task at ±180° out
    near longitude 0 — half a world from the area of interest.

    Args:
        points: (lat, lon) pairs in degrees — turnpoint centers, or the points
            of an optimized route.

    Returns:
        (lat, lon) of the bounding box's centre, in degrees.

    Raises:
        ValueError: If no points are given; there is no area of interest.
    """
    if not points:
        raise ValueError("a task area needs at least one point")

    lats = [lat for lat, _ in points]
    lat0 = (min(lats) + max(lats)) / 2.0

    lons = sorted(((lon + 180.0) % 360.0) - 180.0 for _, lon in points)
    gaps = [(lons[i] - lons[i - 1], i) for i in range(1, len(lons))]
    widest, at = max(gaps) if gaps else (0.0, 0)
    if widest > 180.0:
        # The box wraps the antimeridian: it runs east from the point after
        # the gap, across ±180°, to the point before it.
        lon0 = ((lons[at] + lons[at - 1] + 360.0) / 2.0) % 360.0
        if lon0 > 180.0:
            lon0 -= 360.0
    else:
        lon0 = (lons[0] + lons[-1]) / 2.0

    return (lat0, lon0)


@runtime_checkable
class TurnpointGeometry(Protocol):
    """The geometry seam the route optimizer depends on.

    Route optimization needs only three things from a turnpoint: where its
    center is, how large its cylinder is, and whether it is a goal line.
    Everything else (goal-line length, geodesic math) is an implementation
    detail behind this interface.

    Depending on this protocol instead of the concrete ``TaskTurnpoint`` lets
    the optimization core be exercised with lightweight fakes and lets new
    turnpoint kinds be added without editing the optimizer.

    Attributes:
        center: (lat, lon) of the turnpoint center.
        radius: Cylinder radius in meters (0 collapses to the center).
        goal_type: None, "CYLINDER", or "LINE".
    """

    center: tuple[float, float]
    radius: float
    goal_type: str | None


@dataclass(frozen=True)
class LocalPlane:
    """The Transverse Mercator plane a route is solved in (S7F §7.1.2).

    The spec places optimal points in a plane "centred on the area of
    interest", which :func:`task_area_center` derives per §7.1.6.
    That policy used to be written twice: the route optimizer projected onto
    the task area, while :meth:`TaskTurnpoint.optimal_point` projected onto a
    plane centred on *that turnpoint*. Same paragraph of the spec, two
    different answers, and the tests aimed at the one the product does not
    use — so a crossing-case fix could go green and ship nothing.

    Making the plane a value the caller passes is what lets both go through
    one solver: the optimizer builds one for the task and reuses it across
    every sweep, and a caller asking about a single turnpoint gets a plane
    around that turnpoint unless it says otherwise.

    Attributes:
        to_plane: Geographic to planar, in (lon, lat) → (x, y) axis order.
        to_geo: The inverse.
    """

    to_plane: Transformer
    to_geo: Transformer

    @classmethod
    def around(
        cls, centers: Sequence[tuple[float, float]], earth_model: object = None
    ) -> "LocalPlane":
        """Return the plane centred on these points' task area (§7.1.6).

        Args:
            centers: (lat, lon) pairs — one turnpoint's, or a whole task's.
            earth_model: Earth model selector (None means WGS84).

        Returns:
            LocalPlane: The projection to solve in.

        Raises:
            ValueError: If no centers are given; there is no area of interest.
        """
        return cls(*local_tm_transformers(*task_area_center(centers), earth_model))

    def xy(self, point: tuple[float, float]) -> tuple[float, float]:
        """Project a (lat, lon) point into the plane.

        Args:
            point: (lat, lon) in degrees.

        Returns:
            (x, y) in meters.
        """
        x, y = self.to_plane.transform(point[1], point[0])
        return (x, y)

    def lon_lat(self, xy: tuple[float, float]) -> tuple[float, float]:
        """Return a planar point in geographic coordinates.

        The axis order is the transformers' own — (lon, lat), not (lat, lon)
        — because that is what :func:`snap_to_boundary` reads and what every
        caller here does with the result next. :meth:`xy` takes the other
        order, as its callers hold turnpoint centers that way.

        Args:
            xy: (x, y) in meters.

        Returns:
            (lon, lat) in degrees.
        """
        lon, lat = self.to_geo.transform(xy[0], xy[1])
        return (lon, lat)


def plane_circle(
    turnpoint: "TurnpointGeometry", plane: LocalPlane
) -> tuple[float, float, float]:
    """Return a turnpoint as the circle the solver sees: (x, y, radius).

    The one place that says what a turnpoint is to the optimizer, including
    the rule that **a LINE goal is a zero-radius circle at the goal center**.
    The goal line is perpendicular to the final approach and centred on the
    goal (S7F §6.2.3.1), so the shortest crossing from any approach is the
    center itself — which is on the line by construction, degenerate approach
    included. That rule was stated twice, once in the optimizer's projection
    and once as a method whose twenty-line docstring stood over
    ``return self.center``.

    Args:
        turnpoint: Anything with a center, a radius and a goal type.
        plane: The plane to project into.

    Returns:
        (x, y, radius) with radius in meters; 0 collapses to the center.
    """
    x, y = plane.xy(turnpoint.center)
    radius = 0.0 if turnpoint.goal_type == "LINE" else float(turnpoint.radius)
    return (x, y, radius)


class TaskTurnpoint:
    """Turnpoint class for distance calculations."""

    def __init__(
        self,
        lat: float,
        lon: float,
        radius: float = 0,
        goal_type: str | None = None,
        earth_model: object = None,
    ):
        """Initialize a task turnpoint.

        Args:
            lat (float): Latitude in degrees.
            lon (float): Longitude in degrees.
            radius (float): Cylinder radius in meters.
            goal_type (Optional[str]): Type of goal (None, "CYLINDER", or "LINE").
            earth_model: Earth model the turnpoint's task uses (``EarthModel``
                member, its string value, or None for the WGS84 default).
        """
        self.center = (lat, lon)
        self.radius = radius
        self.goal_type = goal_type
        self.earth_model = earth_model

    def optimal_point(
        self,
        prev_point: tuple[float, float],
        next_point: tuple[float, float],
        plane: LocalPlane | None = None,
    ) -> tuple[float, float]:
        """Find the optimal point on this turnpoint's cylinder or goal line.

        The point is placed with the exact planar GetOptPi solution (crossing
        vs. reflection case per Ding, Xie & Jiang) in a local Transverse
        Mercator plane, then snapped back onto the true cylinder boundary at
        radius ``r`` on the selected earth model.

        Args:
            prev_point (Tuple[float, float]): (lat, lon) of previous point in route.
            next_point (Tuple[float, float]): (lat, lon) of next point in route.
            plane: The plane to solve in. Defaults to one centred on this
                turnpoint. Pass the task's own plane — the one
                :func:`~pyxctsk.distance.route_optimization.calculate_iteratively_refined_route`
                builds — to get the answer the route optimizer would give:
                the projection is the only thing the two ever differed by.

        Returns:
            Tuple[float, float]: (lat, lon) of optimal point on cylinder perimeter or goal line.
        """
        if plane is None:
            plane = LocalPlane.around([self.center], self.earth_model)

        cx, cy, radius = plane_circle(self, plane)
        if radius == 0.0:
            return self.center

        xy = plane_optimal_point(
            plane.xy(prev_point), plane.xy(next_point), (cx, cy), radius
        )
        return snap_to_boundary(
            plane.lon_lat(xy), self.center, self.radius, self.earth_model
        )


def distance_through_centers(
    turnpoints: list[TaskTurnpoint], earth_model: object = None
) -> float:
    """Sum the geodesic legs between consecutive turnpoint centers.

    The primitive, not the published number. **S7F defines no "distance
    through centres"**, so which points to include and where to stop is a
    convention — see :mod:`~pyxctsk.distance.center_distance`, which owns that
    decision and calls this. A caller producing a figure for a task board
    wants ``center_distance(task)``; a caller who already knows exactly which
    turnpoints it means wants this.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None). None falls back to the first turnpoint's
            ``earth_model`` attribute, defaulting to WGS84.

    Returns:
        float: Distance through centers in meters.
    """
    if len(turnpoints) < 2:
        return 0.0

    if earth_model is None:
        earth_model = getattr(turnpoints[0], "earth_model", None)

    total = 0.0
    for i in range(len(turnpoints) - 1):
        total += geodesic_distance(
            turnpoints[i].center, turnpoints[i + 1].center, earth_model
        )
    return total
