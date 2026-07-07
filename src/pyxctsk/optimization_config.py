"""Centralized configuration and constants for optimization routines in distance calculations.

Provides the convergence threshold and sweep limit for the Ding–Xie–Jiang
alternating route optimizer.
"""

#: Maximum alternating optimization sweeps (convergence normally stops far earlier).
DEFAULT_NUM_ITERATIONS = 100

#: Convergence threshold for the alternating route optimizer, in meters.
#: Iteration stops once a full sweep changes the total path length by less
#: than this (FAI Sporting Code S7F §7.1.3: ε = 0.1 m).
CONVERGENCE_EPSILON_M = 0.1
