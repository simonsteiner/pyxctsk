"""The per-turnpoint distance table — a *rendering* of the distance report.

What a task board prints beside a map: two totals in kilometres, the saving
between them, and a row per turnpoint carrying its cumulative distance in each.
Rounded to 0.1 km, because that is what a board shows and what every published
reference value is quoted to.

**It is not a second report.** :class:`~pyxctsk.distance.report.DistanceReport`
is the surface another implementation diffs against, and this is that value
displayed. It used to be a parallel computation: it measured the centre column
leg by leg itself while the report asked
:mod:`~pyxctsk.distance.center_distance`, and its rows carried different keys
and different units from the report's, so the two published shapes disagreed by
up to 50 m by construction and a consumer could not tell which was canonical.
Every number here is now read off one report, and the rounding is the only
thing this module does.

The cylinder conversion this module used to own lives in
:mod:`~pyxctsk.distance.measured_task`, beside the value that holds its result.
"""

from dataclasses import dataclass
from typing import Any

from ..model.task import Task
from .measured_task import MeasuredTask
from .report import DistanceReport

#: What a board rounds to, and what every published reference value is quoted
#: to. The report itself carries unrounded metres.
DISPLAY_PRECISION_KM = 1


def _km(metres: float) -> float:
    """Metres to kilometres, at display precision."""
    return round(metres / 1000.0, DISPLAY_PRECISION_KM)


@dataclass(frozen=True)
class TurnpointRow:
    """One turnpoint's row in the table.

    Attributes:
        index: Its position in the task, zero-based.
        name: The waypoint's name.
        lat: Latitude of the turnpoint centre.
        lon: Longitude of the turnpoint centre.
        radius: Cylinder radius in metres.
        type: The turnpoint's role as the format spells it, ``""`` for none.
        cumulative_center_km: Distance through centres to here.
        cumulative_optimized_km: Distance along the optimized route to here.
            A prefix of the task's optimized distance by construction, because
            it is read off the one route rather than re-optimized.
    """

    index: int
    name: str
    lat: float
    lon: float
    radius: int
    type: str
    cumulative_center_km: float
    cumulative_optimized_km: float

    def as_dict(self) -> dict[str, Any]:
        """Render this row as the dictionary the table has always published."""
        return {
            "index": self.index,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "radius": self.radius,
            "type": self.type,
            "cumulative_center_km": self.cumulative_center_km,
            "cumulative_optimized_km": self.cumulative_optimized_km,
        }


@dataclass(frozen=True)
class TaskDistanceTable:
    """A task's distances as a board displays them.

    Build one with :func:`task_distances_from` or
    :func:`calculate_task_distances`, and call :meth:`as_dict` for the
    dictionary this used to be.

    Attributes:
        center_distance_km: The distance through centres, under
            :data:`~pyxctsk.distance.PROPOSED_READING` — a convention S7F does
            not define. See :mod:`~pyxctsk.distance.center_distance`.
        optimized_distance_km: S7F §7.2's task distance.
        savings_km: How much the optimized route saves over the centres.
        savings_percent: The same as a percentage of the centre distance, 0.0
            when there is no centre distance to be a percentage of.
        turnpoints: One row per turnpoint, in task order.
    """

    center_distance_km: float
    optimized_distance_km: float
    savings_km: float
    savings_percent: float
    turnpoints: tuple[TurnpointRow, ...]

    @classmethod
    def empty(cls) -> "TaskDistanceTable":
        """The table for a task with too few turnpoints to have a distance.

        Zeros rather than an error, which is what this shape has always
        returned. A caller wanting the rule stated instead wants
        :meth:`~pyxctsk.distance.report.DistanceReport.from_task`, which raises
        :class:`~pyxctsk.distance.TooFewTurnpointsError`.

        Returns:
            A table of zeros with no rows.
        """
        return cls(0.0, 0.0, 0.0, 0.0, ())

    @classmethod
    def from_report(cls, report: DistanceReport) -> "TaskDistanceTable":
        """Render a distance report at display precision.

        Args:
            report: The measured task's report — the canonical values.

        Returns:
            The table, in kilometres rounded to 0.1.
        """
        # Each figure is rounded once, from the report's unrounded metres.
        # Note the consequence: the displayed saving is the difference of the
        # *exact* distances rounded, not the difference of the two displayed
        # figures, so the three can disagree in the last digit. That is what
        # this has always published, and changing it is a decision about the
        # numbers rather than about the code.
        center_km = (report.center_distance_m or 0.0) / 1000.0
        optimized_km = report.task_distance_m / 1000.0
        savings_km = center_km - optimized_km
        return cls(
            center_distance_km=round(center_km, DISPLAY_PRECISION_KM),
            optimized_distance_km=round(optimized_km, DISPLAY_PRECISION_KM),
            savings_km=round(savings_km, DISPLAY_PRECISION_KM),
            savings_percent=round(
                (savings_km / center_km * 100) if center_km > 0 else 0.0,
                DISPLAY_PRECISION_KM,
            ),
            turnpoints=tuple(
                TurnpointRow(
                    index=row["index"],
                    name=row["name"],
                    lat=row["center_lat"],
                    lon=row["center_lon"],
                    radius=row["radius_m"],
                    type=row["type"],
                    cumulative_center_km=_km(row["cumulative_center_m"]),
                    cumulative_optimized_km=_km(row["cumulative_m"]),
                )
                for row in report.route()
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        """Render the table as the dictionary it has always published.

        Returns:
            Dict[str, Any]: Distance calculations and turnpoint details.
        """
        return {
            "center_distance_km": self.center_distance_km,
            "optimized_distance_km": self.optimized_distance_km,
            "savings_km": self.savings_km,
            "savings_percent": self.savings_percent,
            "turnpoints": [row.as_dict() for row in self.turnpoints],
        }


def task_distances_from(measured: MeasuredTask) -> TaskDistanceTable:
    """Render a measured task as the table a board displays.

    A caller that already holds a measured task — the export package's
    ``TaskDrawing``, say — gets the table beside the map without optimizing the
    task a second time.

    Args:
        measured (MeasuredTask): The task and the route measured for it.

    Returns:
        TaskDistanceTable: The table. Call ``as_dict()`` for the dictionary
        this used to return.
    """
    if len(measured.turnpoints) < 2:
        return TaskDistanceTable.empty()
    return TaskDistanceTable.from_report(DistanceReport.from_measured_task(measured))


def calculate_task_distances(task: Task) -> TaskDistanceTable:
    """Measure a task and render its distance table.

    Measures the task once and projects it with :func:`task_distances_from`.
    Pass a :class:`~pyxctsk.distance.MeasuredTask` to that function instead if
    you already hold one.

    Args:
        task (Task): Task object.

    Returns:
        TaskDistanceTable: The table. Call ``as_dict()`` for the dictionary
        this used to return.
    """
    return task_distances_from(MeasuredTask.from_task(task))
