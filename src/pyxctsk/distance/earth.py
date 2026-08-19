"""The two earths a task can be measured on, and distances upon them.

FAI Sporting Code S7F §4.2 admits the WGS84 ellipsoid; XCTrack's ``earthModel``
field also offers the FAI sphere (R = 6 371 km), and a task that declares it
must have *every* length measured there — route, legs, goal line and control
zone alike (ADR 0003). This module is where that choice is made, once, and the
rest of ``distance/`` takes an :data:`EarthModelLike` and passes it down.

Split out of ``turnpoint.py``, which had grown to hold four unrelated things
under a name that covered one of them.
"""

from pyproj import Geod

from ..model.enums import EarthModel

#: Radius of the FAI sphere earth model in meters (FAI Sporting Code S7F).
FAI_SPHERE_RADIUS_M = 6_371_000.0

# Geodesic engines for the two supported earth models. A sphere with equal
# semi-axes makes pyproj's Karney solver compute exact great-circle distances.
_WGS84_GEOD = Geod(ellps="WGS84")
_FAI_SPHERE_GEOD = Geod(a=FAI_SPHERE_RADIUS_M, b=FAI_SPHERE_RADIUS_M)


#: What a caller may hand any of these functions to pick an earth model: an
#: ``EarthModel`` member, its string value, or None for the WGS84 default —
#: the three ADR 0003 settled on. It was spelled ``object`` in 16 signatures
#: and described in four docstrings, which meant the type checker could see
#: nothing: ``geodesic_distance(a, b, "WSG84")`` and ``…, 42)`` both passed
#: mypy and both silently measured on WGS84, because everything unrecognised
#: did. Naming the set is what lets a typo be a type error.
EarthModelLike = EarthModel | str | None


def _is_fai_sphere(earth_model: EarthModelLike) -> bool:
    """Return True if the given earth model designates the FAI sphere.

    Args:
        earth_model: An ``EarthModel`` enum member, its string value, or None
            (None means the XCTrack default, WGS84).

    Returns:
        True for the FAI sphere model, False otherwise.

    Raises:
        ValueError: If the value names no earth model this library knows. It
            used to fall through to WGS84, so a misspelling cost 97.6 m on a
            135 km leg and said nothing.
    """
    if earth_model is None:
        return False
    value = getattr(earth_model, "value", earth_model)
    name = str(value).upper()
    if name == EarthModel.FAI_SPHERE.value:
        return True
    if name == EarthModel.WGS84.value:
        return False
    raise ValueError(
        f"not an earth model: {earth_model!r} "
        f"(expected one of {[m.value for m in EarthModel]}, or None for WGS84)"
    )


def geod_for_earth_model(earth_model: EarthModelLike = None) -> Geod:
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
    earth_model: EarthModelLike = None,
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


def snap_to_boundary(
    point_lonlat: tuple[float, float],
    center: tuple[float, float],
    radius: float,
    earth_model: EarthModelLike = None,
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
