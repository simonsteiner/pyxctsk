"""Optimization configuration and constants for distance calculations."""

from typing import Dict, Optional

# Configuration constants
DEFAULT_ANGLE_STEP = 10  # Angle step in degrees for perimeter point generation (5-15° for good accuracy/performance balance)
DEFAULT_BEAM_WIDTH = (
    10  # Number of best candidates to keep at each DP stage for beam search
)
DEFAULT_NUM_ITERATIONS = 5  # Default number of iterations for iterative refinement


def get_optimization_config(
    angle_step: Optional[int] = None,
    beam_width: Optional[int] = None,
    num_iterations: Optional[int] = None,
) -> Dict[str, int]:
    """Get centralized optimization configuration parameters.

    This ensures consistent optimization parameters are used throughout the code.

    Args:
        angle_step: Optional angle step override
        beam_width: Optional beam width override
        num_iterations: Optional iteration count override

    Returns:
        Dictionary containing optimization configuration parameters
    """
    return {
        "angle_step": angle_step if angle_step is not None else DEFAULT_ANGLE_STEP,
        "beam_width": beam_width if beam_width is not None else DEFAULT_BEAM_WIDTH,
        "num_iterations": (
            num_iterations if num_iterations is not None else DEFAULT_NUM_ITERATIONS
        ),
    }
