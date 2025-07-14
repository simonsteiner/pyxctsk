# pg_path_opt.py

from dataclasses import dataclass

from geographiclib.geodesic import Geodesic


@dataclass
class Gate:
    """A circular gate on the WGS84 ellipsoid."""

    center: tuple  # (lat, lon) in degrees
    radius: float  # metres


def _geod_inverse(geod, p1, p2):
    """Return inverse geodesic solution between p1 and p2."""
    inv = geod.Inverse(p1[0], p1[1], p2[0], p2[1])
    return inv["s12"], inv["azi1"], inv["azi2"]


def _geod_direct(geod, p, azi, s):
    """Return point reached by going distance s from p at azimuth azi."""
    d = geod.Direct(p[0], p[1], azi, s)
    return (d["lat2"], d["lon2"])


def _pcp_point(geod, A, B, gate):
    """
    Compute the Point-Circle-Point (PCP) reflection contact
    on gate.circle that minimizes path A→P→B.
    """

    # In practice, solve via light‐reflection law: angle in = angle out.
    # Here we do a 1D root‐find over bearing θ around circle:
    # define F(θ) = bearing(P→A) + bearing(P→B) + 180°, find zero.
    # Parametrize P(θ) = Direct(center, θ, radius).
    def bearing(p_from, p_to):
        return geod.Inverse(p_from[0], p_from[1], p_to[0], p_to[1])["azi1"]

    def F(theta):
        P = _geod_direct(geod, gate.center, theta, gate.radius)
        # want: (azi_PA - θ_at_P) + (azi_PB - θ_at_P) = 0 mod 360
        # equivalently: bearing(P,A) + bearing(P,B) - 2*(θ+180) = 0
        # but we'll do a simple bracketed secant search on F(θ)=dθ.
        return (bearing(P, A) + bearing(P, B) + 360) % 360 - 180

    # bracket and bisect on θ ∈ [0, 2π)
    lo, hi = 0.0, 360.0
    f_lo = F(lo)
    for _ in range(50):
        mid = (lo + hi) / 2
        f_mid = F(mid)
        # choose subinterval containing zero
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    theta_star = (lo + hi) / 2
    return _geod_direct(geod, gate.center, theta_star, gate.radius)


def _line_circle_intersection(geod, A, B, gate):
    """
    Compute the first intersection along A→B of the
    geodesic AB with the circle boundary.
    Returns None if no intersection.
    """
    # We'll sample along AB at small increments to detect sign-change
    s_tot, azi, _ = _geod_inverse(geod, A, B)
    line = geod.Line(A[0], A[1], azi)
    n = 200
    last_inside = _geod_inverse(geod, A, gate.center)[0] < gate.radius
    for i in range(1, n + 1):
        si = s_tot * i / n
        P = line.Position(si)
        dist_to_center = _geod_inverse(geod, (P["lat2"], P["lon2"]), gate.center)[0]
        inside = dist_to_center < gate.radius
        if inside != last_inside:
            # intersection between (i-1)/n and i/n
            s0, s1 = s_tot * (i - 1) / n, si
            for _ in range(30):
                sm = (s0 + s1) / 2
                Pm = line.Position(sm)
                d = _geod_inverse(geod, (Pm["lat2"], Pm["lon2"]), gate.center)[0]
                if (d < gate.radius) == last_inside:
                    s0 = sm
                else:
                    s1 = sm
            Pm = line.Position((s0 + s1) / 2)
            return (Pm["lat2"], Pm["lon2"])
    return None


def _opt_point(geod, A, B, gate):
    """
    Given fixed A (prev contact) and B (next contact), compute
    optimal contact on 'gate' via either crossing or PCP reflection.
    """
    # Try crossing first if line AB intersects circle
    pt_int = _line_circle_intersection(geod, A, B, gate)
    if pt_int:
        return pt_int
    # otherwise fall back to PCP reflection
    return _pcp_point(geod, A, B, gate)


def optimize_path(gates, geod=None, max_iter=100, tol=1e-6):
    """
    gates: [Gate, ...] in order: takeoff → SSS → … → goal
    Returns: (route_points, total_length_m)
    """
    if geod is None:
        geod = Geodesic(6378137, 1 / 298.257223563)

    n = len(gates)
    # initialize: project each center onto next circle
    route = []
    for i in range(n):
        if i == 0:
            # takeoff: use circle-center projection
            route.append(_geod_direct(geod, gates[i].center, 0, gates[i].radius))
        else:
            route.append(_opt_point(geod, route[i - 1], gates[i].center, gates[i]))

    def total_length(pts):
        L = 0.0
        for i in range(1, len(pts)):
            L += _geod_inverse(geod, pts[i - 1], pts[i])[0]
        return L

    prev_L = total_length(route)
    for iteration in range(max_iter):
        # Odd-even updates
        for parity in (1, 0):  # 1: odd indices, then 0: even
            for i in range(parity, n, 2):
                A = route[i - 1] if i > 0 else route[i]
                B = route[i + 1] if i < n - 1 else route[i]
                route[i] = _opt_point(geod, A, B, gates[i])
        curr_L = total_length(route)
        if abs(prev_L - curr_L) < tol:
            break
        prev_L = curr_L

    return route, prev_L


# Example usage:
if __name__ == "__main__":
    geod = Geodesic(6378137, 1 / 298.257223563)
    gates = [
        Gate(center=(46.521, 6.565), radius=1000),
        Gate(center=(46.530, 6.600), radius=2000),
        Gate(center=(46.540, 6.650), radius=2000),
        Gate(center=(46.550, 6.700), radius=3000),
        Gate(center=(46.560, 6.750), radius=2000),
        Gate(center=(46.570, 6.700), radius=2000),
        Gate(center=(46.580, 6.650), radius=2000),
        Gate(center=(46.590, 6.600), radius=1000),
    ]
    route, length = optimize_path(gates, geod, max_iter=100, tol=1e-6)
    print("Route:", route)
    print(f"Total distance: {length:.2f} m")
