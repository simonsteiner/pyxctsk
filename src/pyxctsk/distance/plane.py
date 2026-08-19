"""The Transverse Mercator plane a route is solved in (S7F §7.1.2, §7.1.6).

The spec places optimal points in a plane "centred on the area of interest",
projects the turnpoints into it, solves there, and converts back. This module
is that plane: how it is scaled (:func:`ltm_scale_factor`), where it is centred
(:func:`task_area_center`), and the value carrying both plus the earth it was
built on (:class:`LocalPlane`).

Split out of ``turnpoint.py``. Nothing here knows what a turnpoint is — a
caller projects a point, solves, and projects back.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from pyproj import CRS, Transformer

from .earth import EarthModelLike, canonical, crs_for_earth_model, datum_proj4


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
def local_tm_transformers(
    lat0: float, lon0: float, earth_model: EarthModelLike = None
) -> tuple[Transformer, Transformer]:
    """Return transformers to/from a local Transverse Mercator plane.

    Per FAI Sporting Code S7F §7.1.2, optimal points are placed in a plane
    obtained by a Transverse Mercator projection centred on the area of
    interest, then converted back to geographic coordinates.

    The earth's own figure comes from :mod:`~pyxctsk.distance.earth`, which is
    where the choice between the two is made. This function used to build both
    of them itself, in a two-branch ``if`` pairing a datum with a geographic
    CRS — so the module docstring next door claiming the choice was made
    "once" was not true, and only that module refused a value naming no earth.

    It was also two functions: this one converted its arguments and handed
    them to a cached twin, keyed on ``fai_sphere: bool`` — the two-valued
    world :data:`EarthModelLike` was widened to replace, one layer down. The
    cache is keyed on the model itself now, so the pass-through is gone.

    ``+k_0`` rather than ``+k``: the two are synonyms in PROJ, but the 2026
    edition's own document history records the correction "parameter +k_0
    instead of deprecated +k" against its Annex A sample.

    Args:
        lat0: Latitude of the projection centre in degrees.
        lon0: Longitude of the projection centre in degrees.
        earth_model: Earth model selector (see
            :func:`~pyxctsk.distance.earth.geod_for_earth_model`).

    Returns:
        ``(to_plane, to_geo)`` transformers; both use (lon, lat) ↔ (x, y)
        axis order (``always_xy``).
    """
    k0 = ltm_scale_factor(lat0)
    geo_crs = crs_for_earth_model(earth_model)
    tm_crs = CRS.from_proj4(
        f"+proj=tmerc +lat_0={float(lat0)} +lon_0={float(lon0)} +k_0={k0} "
        f"+x_0=0 +y_0=0 {datum_proj4(earth_model)} +units=m +no_defs"
    )
    to_plane = Transformer.from_crs(geo_crs, tm_crs, always_xy=True)
    to_geo = Transformer.from_crs(tm_crs, geo_crs, always_xy=True)
    return to_plane, to_geo


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

    The plane keeps the earth model it was built from. It has to: a planar
    solution is snapped back onto a cylinder boundary measured on that model
    (§7.1.7), and when the plane and the snap disagreed the answer was an
    FAI-sphere boundary point placed from a WGS84 planar solution — the same
    paragraph answered two ways again, one layer down. Carrying it means the
    consumers stop taking it as a second argument nothing checked against the
    first.

    Attributes:
        to_plane: Geographic to planar, in (lon, lat) → (x, y) axis order.
        to_geo: The inverse.
        earth_model: The model this plane was built on, and the one its points
            must be snapped back onto.
    """

    to_plane: Transformer
    to_geo: Transformer
    earth_model: EarthModelLike = None

    @classmethod
    def around(
        cls, centers: Sequence[tuple[float, float]], earth_model: EarthModelLike = None
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
        # `canonical` for the cache key, so "WGS84", EarthModel.WGS84 and None
        # are one entry rather than three; the plane keeps the selector it was
        # given, which is what its consumers snap against.
        lat0, lon0 = task_area_center(centers)
        return cls(
            *local_tm_transformers(float(lat0), float(lon0), canonical(earth_model)),
            earth_model=earth_model,
        )

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
