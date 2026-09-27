"""Conversion between the domain model and the QR wire format.

``Task`` and ``QRCodeTask`` describe the same thing in two shapes: the full
JSON format the spec calls "the task file", and the compact QR encoding. Neither
should have to know about the other, so the mapping between them lives here —
the one module that imports both.

Both models hold the same enums — ``TurnpointType``, ``GoalType`` and the rest.
The QR format's integers are a spelling, and live in its field tables as
:func:`~pyxctsk.model.shape.wire_int_codec` codecs. This module used to carry
twelve translation tables between the model's enums and six parallel
``IntEnum`` classes, with a default at each call site for whatever a table
left out — so a new ``TurnpointType`` member silently became ``NONE`` going
out and ``None`` coming back.

Unknown keys cross here too, and this is the one place that can tell whether
they may: a key is unknown only relative to the format it arrived in, and this
is where the namespace changes. Every crossing runs through
:func:`~pyxctsk.model.passthrough.strip_foreign_keys` against the target
shape's own key set, so a carried key can never occupy a slot the other format
defines.

Only the four shapes with a counterpart carry them: ``Task``, ``Turnpoint``,
``SSS`` and ``Goal``. A ``Waypoint``'s unknown keys stay in the full format,
because the QR format has no waypoint object to put them in — it flattens the
waypoint into its turnpoint, and merging the two dicts would leave nothing to
split them back apart by. ``Takeoff`` is the same story: root ``to`` and ``tc``
in the QR format, no object of its own.
"""

from ..model.passthrough import strip_foreign_keys
from ..model.task import (
    SSS,
    Goal,
    Takeoff,
    Task,
    TaskType,
    Turnpoint,
    Waypoint,
)
from ..model.validation import FULL_FORMAT_VERSION
from .models import QRCodeGoal, QRCodeSSS, QRCodeTakeoff, QRCodeTurnpoint
from .task import QR_CODE_TASK_VERSION, QRCodeTask

#: What a carried unknown key may not occupy on the QR side. The QR task
#: renders as either of its two shapes and keeps its unknown keys through
#: ``as_waypoints()``, so both shapes' keys are reserved for it.
_QR_TASK_KEYS = QRCodeTask.COMPETITION_KEYS | QRCodeTask.SIMPLIFIED_KEYS


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
            type=tp.type,
            description=tp.waypoint.description,
            extensions=tp.extensions,
            unknown=strip_foreign_keys(tp.unknown, QRCodeTurnpoint.KNOWN_KEYS),
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
            direction=task.sss.direction,
            type=task.sss.type,
            time_gates=task.sss.time_gates,
            unknown=strip_foreign_keys(task.sss.unknown, QRCodeSSS.KNOWN_KEYS),
        )

    # ``task.goal``, not ``effective_goal``: a task whose goal was never
    # spelled out is written without a ``g`` object, so the payload says what
    # the file said. Both formats read an absent goal as a CYLINDER one, so
    # nothing is lost, and the alternative — writing the default out — is the
    # invention this module exists not to make.
    goal = task.goal
    qr_goal = None
    if goal:
        qr_goal = QRCodeGoal(
            deadline=goal.deadline,
            type=goal.type,
            finish_altitude=goal.finish_altitude,
            unknown=strip_foreign_keys(goal.unknown, QRCodeGoal.KNOWN_KEYS),
        )

    return QRCodeTask(
        version=QR_CODE_TASK_VERSION,
        task_type=task.task_type,
        earth_model=task.earth_model,
        turnpoints=qr_turnpoints,
        takeoff=qr_takeoff,
        sss=qr_sss,
        goal=qr_goal,
        extensions=task.extensions,
        unknown=strip_foreign_keys(task.unknown, _QR_TASK_KEYS),
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
            type=qr_tp.type,
            extensions=qr_tp.extensions,
            unknown=strip_foreign_keys(qr_tp.unknown, Turnpoint.KNOWN_KEYS),
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
            type=qr.sss.type,
            direction=qr.sss.direction,
            time_gates=qr.sss.time_gates,
            time_close=None,  # QR code format doesn't include time_close
            unknown=strip_foreign_keys(qr.sss.unknown, SSS.KNOWN_KEYS),
        )

    goal = None
    if qr.goal:
        goal = Goal(
            type=qr.goal.type,
            deadline=qr.goal.deadline,
            finish_altitude=qr.goal.finish_altitude,
            unknown=strip_foreign_keys(qr.goal.unknown, Goal.KNOWN_KEYS),
        )

    return Task(
        task_type=qr.task_type or TaskType.CLASSIC,
        version=FULL_FORMAT_VERSION,
        turnpoints=turnpoints,
        earth_model=qr.earth_model,
        takeoff=takeoff,
        sss=sss,
        goal=goal,
        extensions=qr.extensions,
        unknown=strip_foreign_keys(qr.unknown, Task.KNOWN_KEYS),
    )
