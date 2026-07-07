"""Centralized configuration and constants for optimization routines in distance calculations.

Provides default parameters and a utility function to retrieve optimization settings
for the Ding–Xie–Jiang alternating route optimizer and perimeter point generation.
"""

# Configuration constants
DEFAULT_ANGLE_STEP = 10  # Angle step in degrees for perimeter point generation (visualization/sampling only)
DEFAULT_BEAM_WIDTH = 10  # Deprecated: retained for API compatibility with the removed beam-search optimizer; unused
DEFAULT_NUM_ITERATIONS = 100  # Maximum alternating optimization sweeps (convergence normally stops far earlier)

#: Convergence threshold for the alternating route optimizer, in meters.
#: Iteration stops once a full sweep changes the total path length by less
#: than this (FAI Sporting Code S7F §7.1.3: ε = 0.1 m).
CONVERGENCE_EPSILON_M = 0.1


def get_optimization_config(
    angle_step: int | None = None,
    beam_width: int | None = None,
    num_iterations: int | None = None,
) -> dict[str, int]:
    """Get centralized optimization configuration parameters.

    This ensures consistent optimization parameters are used throughout the code.

    Args:
        angle_step (Optional[int]): Optional angle step override.
        beam_width (Optional[int]): Optional beam width override (deprecated, unused).
        num_iterations (Optional[int]): Optional maximum-sweep count override.

    Returns:
        Dict[str, int]: Dictionary containing optimization configuration parameters.
    """
    return {
        "angle_step": angle_step if angle_step is not None else DEFAULT_ANGLE_STEP,
        "beam_width": beam_width if beam_width is not None else DEFAULT_BEAM_WIDTH,
        "num_iterations": (
            num_iterations if num_iterations is not None else DEFAULT_NUM_ITERATIONS
        ),
    }
