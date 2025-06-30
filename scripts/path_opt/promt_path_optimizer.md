# Task Prompt: Paragliding Path Optimization via Cylindrical Gates on WGS84

**Objective**  
Write a Python module that computes the shortest feasible flight path for a paragliding task defined entirely by cylindrical gates on the Earth’s surface, modeled as a WGS84 ellipsoid.

**1. Inputs**  

- `gates`: Ordered list of *N* circular gates (`Gate` objects) where each gate has:  
  - `type = 'circle'`  
  - `center`: tuple `(lat, lon)` in degrees (WGS84)  
  - `radius`: `r` in metres (geodesic radius over WGS84)  
  
  The sequence must be: take-off cylinder → start-speed cylinder (SSS) → one or more primary turnpoint cylinders → end-speed cylinder (ESS) → zero or more safety turnpoint cylinders → goal cylinder.  

- **Algorithm parameters** (optional):  
  - `max_iter`: maximum number of optimization iterations (default: 100)  
  - `tol`: convergence tolerance on total path-length change in metres (default: 1e-6)

**2. Outputs**  

- `route`: List of *N* contact points `(lat_i, lon_i)`, one per gate, on each cylinder’s circumference in input order.  
- `length`: Total geodesic distance (in metres) along the piecewise path connecting these contacts, computed on the WGS84 ellipsoid.

**3. Requirements & Assumptions**  

1. **Uniform gate handling**: treat take-off, SSS, ESS, safety, and goal gates identically as surface circles on the ellipsoid—no special-case lines or fixed points.  
2. **Ellipsoidal Earth model**: use the WGS84 ellipsoid for all distance and bearing calculations; compute geodesic intersections, projections, and PCP reflections via a geodesic library (e.g., GeographicLib).  
3. **Optimization algorithm**: implement the Odd–Even alternating scheme with Point–Circle–Point (PCP) adapted to geodesics:  
   - **Initialization**: project each geodesic from the previous gate’s center to the next gate’s center onto the next gate’s great-circle circle using geodesic direct/inverse solves.  
   - **Iteration**: until convergence or `max_iter`:  
     a. **Odd-indexed updates** (gates 1,3,5…): fix other points and recompute each odd gate’s optimal boundary point—if the geodesic segment intersects the gate’s circle, pick the earliest intersection along the route; otherwise use the geodesic PCP reflection trick to find the tangent contact point.  
     b. **Even-indexed updates** (gates 2,4,6…): same procedure.  
4. **Performance target**: handle up to ~20 gates in <1 s; stop when geodesic path-length change < `tol`.

**4. Example Usage**  

```python
from geographiclib.geodesic import Geodesic
from your_module import Gate, optimize_path

# Define gates (lat, lon in degrees; radii in metres)
takeoff = Gate('circle', center=(46.521, 6.565),    radius=1000)
sss     = Gate('circle', center=(46.530, 6.600),    radius=2000)
tp1     = Gate('circle', center=(46.540, 6.650),    radius=2000)
ess     = Gate('circle', center=(46.550, 6.700),    radius=3000)
ess2    = Gate('circle', center=(46.560, 6.750),    radius=2000)
stp1    = Gate('circle', center=(46.570, 6.700),    radius=2000)  # safety
stp2    = Gate('circle', center=(46.580, 6.650),    radius=2000)  # safety
goal    = Gate('circle', center=(46.590, 6.600),    radius=1000)

gates = [takeoff, sss, tp1, ess, ess2, stp1, stp2, goal]

# Optimize on WGS84
geod = Geodesic.WGS84
route, length = optimize_path(gates, geod, max_iter=100, tol=1e-6)
print("Route:", route)
print(f"Total distance: {length:.2f} m")
```

Source paper <https://www.matec-conferences.org/articles/matecconf/pdf/2018/91/matecconf_eitce2018_03027.pdf>
