"""Builders for the tasks tests make up.

Around thirty tasks were hand-built across the suite, each spelling out a
``Turnpoint`` wrapping a ``Waypoint`` wrapping five keyword arguments, to vary
one of them. Test setup became the bulk of the test, and what a case was
actually about — this radius, that goal type — was buried in the shape of a
task the reader already knows.

These are for *made-up* tasks only. Real ones come from ``tests/corpus.py``;
nothing here is a fixture of anything.
"""

from pyxctsk import (
    SSS,
    Goal,
    GoalType,
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
)


def waypoint(
    name: str = "TP",
    lat: float = 46.5,
    lon: float = 8.0,
    alt: int = 1000,
    description: str | None = None,
) -> Waypoint:
    """Return a waypoint, defaulting to a point in the Swiss Alps.

    Args:
        name: The waypoint name.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        alt: Smoothed altitude in metres.
        description: Optional description.

    Returns:
        Waypoint: The waypoint.
    """
    return Waypoint(
        name=name, lat=lat, lon=lon, alt_smoothed=alt, description=description
    )


def turnpoint(
    name: str = "TP",
    lat: float = 46.5,
    lon: float = 8.0,
    alt: int = 1000,
    radius: int = 1000,
    type: TurnpointType | None = None,
) -> Turnpoint:
    """Return a turnpoint around a waypoint of the same position.

    Args:
        name: The waypoint name.
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        alt: Smoothed altitude in metres.
        radius: Cylinder radius in metres.
        type: The turnpoint's role, if it has one.

    Returns:
        Turnpoint: The turnpoint.
    """
    return Turnpoint(radius=radius, waypoint=waypoint(name, lat, lon, alt), type=type)


def task(
    *turnpoints: Turnpoint,
    goal: Goal | GoalType | None = None,
    sss: SSS | None = None,
    task_type: TaskType = TaskType.CLASSIC,
    version: int = 1,
) -> Task:
    """Return a task of these turnpoints.

    Args:
        *turnpoints: The course, in order. With none, two default ones are
            used — a task needs turnpoints to have a goal at all, and most
            cases do not care which.
        goal: The goal, or just its type for the common case.
        sss: The start of the speed section, if the case needs one.
        task_type: CLASSIC unless the case is about waypoints tasks.
        version: The format version.

    Returns:
        Task: The task.
    """
    if not turnpoints:
        turnpoints = (
            turnpoint("A", 46.5, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("Goal", 47.0, 8.5, radius=400),
        )
    if isinstance(goal, GoalType):
        goal = Goal(type=goal)
    return Task(
        task_type=task_type,
        version=version,
        turnpoints=list(turnpoints),
        goal=goal,
        sss=sss,
    )
