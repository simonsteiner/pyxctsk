"""The per-turnpoint distance table, projected from one measured task.

Center and optimized distances for a task, with a row per turnpoint carrying
its cumulative distance in each. Every optimized number is read off the
measured task's route rather than recomputed, so a turnpoint's cumulative
distance is by construction a prefix of the task's total.

The cylinder conversion this module used to own lives in
:mod:`~pyxctsk.distance.measured_task` now, beside the value that holds its
result — which is also what removed the edge that made the goal line depend on
the distance *report*.
"""

from typing import Any

from ..model.task import Task
from .center_distance import center_distance
from .measured_task import MeasuredTask
from .turnpoint import geodesic_distance


def _calculate_savings(center_km: float, opt_km: float) -> tuple[float, float]:
    """Calculate distance savings in km and percentage.

    Args:
        center_km (float): Center distance in km.
        opt_km (float): Optimized distance in km.

    Returns:
        Tuple[float, float]: Tuple of (savings_km, savings_percent).
    """
    savings_km = center_km - opt_km
    savings_percent = (savings_km / center_km * 100) if center_km > 0 else 0.0
    return savings_km, savings_percent


def _create_turnpoint_details(measured: MeasuredTask) -> list[dict[str, Any]]:
    """Create detailed turnpoint information including cumulative distances.

    The optimized column is read off the measured task's route rather than
    recomputed. Both are distances along one route, so a turnpoint's cumulative
    optimized distance is by construction a prefix of the task's optimized
    distance — which is what re-optimizing a truncated task did not give: the
    optimizer treats the last circle of whatever it is handed as the finish, so
    the truncated optimum bent the route towards turnpoint i instead of passing
    through it, understating the prefix by up to 5 km on the reference tasks.

    Taking the measured task rather than its three parts is what lets this
    zip them without a length guard: they are one value, so they agree.

    Args:
        measured (MeasuredTask): The task and the route measured for it.

    Returns:
        List[Dict[str, Any]]: List of dictionaries with turnpoint details.
    """
    turnpoint_details = []
    cumulative_center = 0.0
    cumulative_optimized = measured.cumulative_m()

    for i, (tp, task_tp) in enumerate(
        zip(measured.task.turnpoints, measured.turnpoints)
    ):
        # Calculate cumulative distances for all turnpoints
        if i > 0:
            # Calculate center distance incrementally
            prev_tp = measured.turnpoints[i - 1]
            leg_distance = (
                geodesic_distance(prev_tp.center, task_tp.center, task_tp.earth_model)
                / 1000.0
            )
            cumulative_center += leg_distance

        turnpoint_details.append(
            {
                "index": i,
                "name": tp.waypoint.name,
                "lat": tp.waypoint.lat,
                "lon": tp.waypoint.lon,
                "radius": tp.radius,
                "type": tp.type.value if tp.type else "",
                "cumulative_center_km": round(cumulative_center, 1),
                "cumulative_optimized_km": round(cumulative_optimized[i] / 1000.0, 1),
            }
        )

    return turnpoint_details


def task_distances_from(measured: MeasuredTask) -> dict[str, Any]:
    """Project a measured task into the distance report.

    Every optimized number in the report comes from the measured task's route,
    so a caller that already holds one — the export package's ``TaskDrawing``,
    say — produces the table beside the map without optimizing the task a
    second time.

    Distances are rounded to 0.1 km here because this dictionary is a report
    for display; the route itself carries unrounded meters.

    Args:
        measured (MeasuredTask): The task and the route measured for it.

    Returns:
        Dict[str, Any]: Dictionary containing distance calculations and turnpoint details.
    """
    if len(measured.turnpoints) < 2:
        return {
            "center_distance_km": 0.0,
            "optimized_distance_km": 0.0,
            "savings_km": 0.0,
            "savings_percent": 0.0,
            "turnpoints": [],
        }

    # Ask the module that owns the convention, not the primitive underneath
    # it. This used to call distance_through_centers directly and publish the
    # result as center_distance_km with no caveat, while the CLI honoured
    # PROPOSED_READING — two spellings of one convention that agreed only
    # because the proposed reading happens to be LAUNCH_TO_GOAL.
    center_m = center_distance(measured.task)
    center_km = (center_m or 0.0) / 1000.0
    opt_km = measured.total_m / 1000.0
    savings_km, savings_percent = _calculate_savings(center_km, opt_km)

    return {
        "center_distance_km": round(center_km, 1),
        "optimized_distance_km": round(opt_km, 1),
        "savings_km": round(savings_km, 1),
        "savings_percent": round(savings_percent, 1),
        "turnpoints": _create_turnpoint_details(measured),
    }


def calculate_task_distances(
    task: Task,
    num_iterations: int | None = None,
) -> dict[str, Any]:
    """Calculate both center and optimized distances for a task.

    Measures the task once and projects it with :func:`task_distances_from`.
    Pass a :class:`~pyxctsk.distance.MeasuredTask` to that function instead if
    you already hold one.

    Args:
        task (Task): Task object.
        num_iterations (Optional[int]): Maximum number of alternating sweeps.

    Returns:
        Dict[str, Any]: Dictionary containing distance calculations and turnpoint details.
    """
    return task_distances_from(MeasuredTask.from_task(task, num_iterations))
