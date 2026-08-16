"""Conversion between the domain model and the QR wire format.

``Task`` and ``QRCodeTask`` describe the same thing in two shapes: the full
JSON format the spec calls "the task file", and the compact QR encoding. Neither
should have to know about the other, so the mapping between them lives here —
the one module that imports both.

The two models spell their constrained values with parallel but separate enums
(``TurnpointType`` / ``QRCodeTurnpointType`` and so on). Each pair gets one
translation table below, with the reverse direction derived from it, so a value
added to one side cannot silently go unmapped on the other. The *defaults* are
not symmetric and stay at the call sites: an unrecognized turnpoint type is
``NONE`` going out and ``None`` coming back, for instance.
"""

from ..model.task import (
    SSS,
    Direction,
    EarthModel,
    Goal,
    GoalType,
    SSSType,
    Takeoff,
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
)
from .enums import (
    QRCodeDirection,
    QRCodeEarthModel,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTaskType,
    QRCodeTurnpointType,
)
from .models import QRCodeGoal, QRCodeSSS, QRCodeTakeoff, QRCodeTurnpoint
from .task import QR_CODE_TASK_VERSION, QRCodeTask

#: The task version the full JSON format carries.
TASK_VERSION = 1

# Several of the fields these translate are optional on one or both sides, so
# the key types admit None: an absent value maps to nothing, and the call site
# supplies whatever default that direction wants.
_TO_QR_TASK_TYPE: dict[TaskType | None, QRCodeTaskType] = {
    TaskType.CLASSIC: QRCodeTaskType.CLASSIC,
    TaskType.WAYPOINTS: QRCodeTaskType.WAYPOINTS,
}
_TO_QR_EARTH_MODEL: dict[EarthModel | None, QRCodeEarthModel] = {
    EarthModel.WGS84: QRCodeEarthModel.WGS84,
    EarthModel.FAI_SPHERE: QRCodeEarthModel.FAI_SPHERE,
}
_TO_QR_TURNPOINT_TYPE: dict[TurnpointType | None, QRCodeTurnpointType] = {
    TurnpointType.TAKEOFF: QRCodeTurnpointType.TAKEOFF,
    TurnpointType.SSS: QRCodeTurnpointType.SSS,
    TurnpointType.ESS: QRCodeTurnpointType.ESS,
}
_TO_QR_DIRECTION: dict[Direction | None, QRCodeDirection] = {
    Direction.ENTER: QRCodeDirection.ENTER,
    Direction.EXIT: QRCodeDirection.EXIT,
}
_TO_QR_SSS_TYPE: dict[SSSType | None, QRCodeSSSType] = {
    SSSType.RACE: QRCodeSSSType.RACE,
    SSSType.ELAPSED_TIME: QRCodeSSSType.ELAPSED_TIME,
}
_TO_QR_GOAL_TYPE: dict[GoalType | None, QRCodeGoalType] = {
    GoalType.LINE: QRCodeGoalType.LINE,
    GoalType.CYLINDER: QRCodeGoalType.CYLINDER,
}

# Written out rather than derived by inverting the tables above: the key types
# differ (each admits None exactly where its own source field is optional), and
# a comprehension that had to paper over that would be less clear than this.
# ``tests/qrcode/test_conversion.py`` asserts the two directions stay mutual inverses.
_FROM_QR_TASK_TYPE: dict[QRCodeTaskType | None, TaskType] = {
    QRCodeTaskType.CLASSIC: TaskType.CLASSIC,
    QRCodeTaskType.WAYPOINTS: TaskType.WAYPOINTS,
}
_FROM_QR_EARTH_MODEL: dict[QRCodeEarthModel | None, EarthModel] = {
    QRCodeEarthModel.WGS84: EarthModel.WGS84,
    QRCodeEarthModel.FAI_SPHERE: EarthModel.FAI_SPHERE,
}
_FROM_QR_TURNPOINT_TYPE: dict[QRCodeTurnpointType | None, TurnpointType] = {
    QRCodeTurnpointType.TAKEOFF: TurnpointType.TAKEOFF,
    QRCodeTurnpointType.SSS: TurnpointType.SSS,
    QRCodeTurnpointType.ESS: TurnpointType.ESS,
}
_FROM_QR_DIRECTION: dict[QRCodeDirection | None, Direction] = {
    QRCodeDirection.ENTER: Direction.ENTER,
    QRCodeDirection.EXIT: Direction.EXIT,
}
_FROM_QR_SSS_TYPE: dict[QRCodeSSSType | None, SSSType] = {
    QRCodeSSSType.RACE: SSSType.RACE,
    QRCodeSSSType.ELAPSED_TIME: SSSType.ELAPSED_TIME,
}
_FROM_QR_GOAL_TYPE: dict[QRCodeGoalType | None, GoalType] = {
    QRCodeGoalType.LINE: GoalType.LINE,
    QRCodeGoalType.CYLINDER: GoalType.CYLINDER,
}


def task_to_qr_code_task(task: Task) -> QRCodeTask:
    """Convert a Task to the compact QR code format.

    Args:
        task: Task object to convert.

    Returns:
        QRCodeTask: The same task in QR code form.
    """
    qr_turnpoints = [
        QRCodeTurnpoint(
            lat=tp.waypoint.lat,
            lon=tp.waypoint.lon,
            radius=tp.radius,
            name=tp.waypoint.name,
            alt_smoothed=tp.waypoint.alt_smoothed,
            type=_TO_QR_TURNPOINT_TYPE.get(tp.type, QRCodeTurnpointType.NONE),
            description=tp.waypoint.description,
            extensions=tp.extensions,
            unknown=tp.unknown,
        )
        for tp in task.turnpoints
    ]

    qr_takeoff = None
    if task.takeoff:
        qr_takeoff = QRCodeTakeoff(
            time_open=task.takeoff.time_open,
            time_close=task.takeoff.time_close,
        )

    qr_sss = None
    if task.sss:
        qr_sss = QRCodeSSS(
            direction=_TO_QR_DIRECTION.get(task.sss.direction, QRCodeDirection.EXIT),
            type=_TO_QR_SSS_TYPE.get(task.sss.type, QRCodeSSSType.ELAPSED_TIME),
            time_gates=task.sss.time_gates,
        )

    qr_goal = None
    if task.goal:
        qr_goal = QRCodeGoal(
            deadline=task.goal.deadline,
            type=_TO_QR_GOAL_TYPE.get(task.goal.type),
            finish_altitude=task.goal.finish_altitude,
        )

    return QRCodeTask(
        version=QR_CODE_TASK_VERSION,
        task_type=_TO_QR_TASK_TYPE.get(task.task_type),
        earth_model=_TO_QR_EARTH_MODEL.get(task.earth_model),
        turnpoints=qr_turnpoints,
        takeoff=qr_takeoff,
        sss=qr_sss,
        goal=qr_goal,
        extensions=task.extensions,
        unknown=task.unknown,
    )


def task_to_qr_code_waypoints(task: Task) -> QRCodeTask:
    """Convert a Task to the XC/Waypoints simplified QR format.

    The simplified format is "a simple route from waypoints without cylinders".
    Reducing a task to what it can represent is
    :meth:`QRCodeTask.as_waypoints`'s job, so this is the ordinary conversion
    followed by that — rather than a second, subtly different idea of what a
    waypoints task keeps.

    Args:
        task: Task object to convert.

    Returns:
        QRCodeTask: A WAYPOINTS task holding only the essential turnpoint data.
    """
    return task_to_qr_code_task(task).as_waypoints()


def qr_code_task_to_task(qr: QRCodeTask) -> Task:
    """Convert a QR code task back to the full Task format.

    Args:
        qr: QRCodeTask to convert.

    Returns:
        Task: The same task in full format.
    """
    turnpoints = [
        Turnpoint(
            radius=qr_tp.radius,
            waypoint=Waypoint(
                name=qr_tp.name,
                lat=qr_tp.lat,
                lon=qr_tp.lon,
                alt_smoothed=qr_tp.alt_smoothed,
                description=qr_tp.description,
            ),
            type=_FROM_QR_TURNPOINT_TYPE.get(qr_tp.type),
            extensions=qr_tp.extensions,
            unknown=qr_tp.unknown,
        )
        for qr_tp in qr.turnpoints
    ]

    takeoff = None
    if qr.takeoff:
        takeoff = Takeoff(
            time_open=qr.takeoff.time_open,
            time_close=qr.takeoff.time_close,
        )

    sss = None
    if qr.sss:
        sss = SSS(
            type=_FROM_QR_SSS_TYPE.get(qr.sss.type, SSSType.ELAPSED_TIME),
            direction=_FROM_QR_DIRECTION.get(qr.sss.direction, Direction.EXIT),
            time_gates=qr.sss.time_gates,
            time_close=None,  # QR code format doesn't include time_close
        )

    goal = None
    if qr.goal:
        goal = Goal(
            type=_FROM_QR_GOAL_TYPE.get(qr.goal.type),
            deadline=qr.goal.deadline,
            finish_altitude=qr.goal.finish_altitude,
        )

    return Task(
        task_type=_FROM_QR_TASK_TYPE.get(qr.task_type, TaskType.CLASSIC),
        version=TASK_VERSION,
        turnpoints=turnpoints,
        earth_model=_FROM_QR_EARTH_MODEL.get(qr.earth_model),
        takeoff=takeoff,
        sss=sss,
        goal=goal,
        extensions=qr.extensions,
        unknown=qr.unknown,
    )
