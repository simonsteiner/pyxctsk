"""The S7F distance report — the numbers pyxctsk publishes about one task.

This is the surface another implementation diffs against: the two distances
S7F §7.2 defines, the centre distance it does *not*, every reading of that
number, and the optimized crossing point per turnpoint. Exchange the points
rather than the totals — a total says two implementations disagree, the points
say where. See ``docs/s7f-distance-reference.md``.

It lives here rather than in ``cli.py``, where it was written, because it is a
value and not a command. As two private functions behind a click command it
could only be reached by running the CLI, so every test of *what the report
says* had to build a runner, invoke a command, assert an exit code and parse
stdout; the documentation told a library user to hand-roll the whole thing from
four imports, and that snippet crashed on a task with no speed section. The
numbers were also selected twice — once to build the dict, once to read it back
out by string key for the text rendering — and the two had already drifted on
what a missing value means.

So the report is one value with two renderings: :meth:`DistanceReport.as_dict`
for the diff surface and :meth:`DistanceReport.as_text` for a human. Both read
the same fields, so they cannot disagree about a number or its absence.
"""

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from ..model.task import Task
from .center_distance import (
    PROPOSED_READING,
    center_distance,
    center_distance_readings,
    cumulative_center_m,
)
from .earth import name_of
from .measured_task import MeasuredTask
from .speed_section import SpeedSection

#: The S7F edition the distance calculations are audited against.
S7F_EDITION = "2026 V1.0"

#: The fewest turnpoints a task needs before any of these numbers mean anything.
#: One turnpoint has no leg, so there is no route and no distance — the library
#: used to answer 0.0 and only the CLI knew to refuse.
MIN_TURNPOINTS_FOR_DISTANCE = 2

#: What each published number is, and which section defines it. Carried with
#: the report because "not defined by S7F" is the single most important thing
#: it says, and a number travelling without it invites a false comparison.
NOTES = {
    "task_distance_m": "FAI S7F 2026 §7.2, optimized launch to goal",
    "speed_section_distance_m": (
        "FAI S7F 2026 §7.2, a separate launch-to-ESS optimization minus "
        "its pre-start portion; null when the task has no SSS/ESS pair"
    ),
    "center_distance_m": (
        "NOT DEFINED BY S7F. A task-board convention; this is the "
        "reading pyxctsk proposes. See center_distance_readings_m for "
        "the alternatives and docs/s7f-distance-reference.md for why "
        "they differ by up to 39.9 km"
    ),
    "route": (
        "The optimized crossing point per turnpoint. Exchange these "
        "rather than totals: a total says two implementations disagree, "
        "these say where. cumulative_center_m is the prefix of the "
        "center_distance_m reading above, so its last row equals it"
    ),
}


def pyxctsk_version() -> str:
    """Return the installed library version, or ``"unknown"``.

    Returns:
        The version string from package metadata.
    """
    try:
        return version("pyxctsk")
    except PackageNotFoundError:  # pragma: no cover - editable/source runs
        return "unknown"


class TooFewTurnpointsError(ValueError):
    """Raised when a task has too few turnpoints to have a distance at all."""


@dataclass(frozen=True)
class DistanceReport:
    """Every number pyxctsk publishes about one task, with its provenance.

    Build one with :meth:`from_task` and render it with :meth:`as_dict` or
    :meth:`as_text`. The numbers are all projections of :attr:`measured` and
    :attr:`speed_section`, so the two renderings read one set of values.

    Attributes:
        measured: The task and the route measured for it.
        speed_section: §7.2's second distance, or None when the task has no
            SSS/ESS pair to measure one between.
    """

    measured: MeasuredTask
    speed_section: SpeedSection | None

    @classmethod
    def from_task(cls, task: Task) -> "DistanceReport":
        """Measure a task and build its report.

        Args:
            task: The task to measure.

        Returns:
            The report.

        Raises:
            TooFewTurnpointsError: If the task has fewer than
                :data:`MIN_TURNPOINTS_FOR_DISTANCE` turnpoints, which leaves no
                leg to measure.
        """
        if len(task.turnpoints) < MIN_TURNPOINTS_FOR_DISTANCE:
            raise TooFewTurnpointsError(
                "a task needs at least two turnpoints to have a distance."
            )
        return cls.from_measured_task(MeasuredTask.from_task(task))

    @classmethod
    def from_measured_task(cls, measured: MeasuredTask) -> "DistanceReport":
        """Build the report for an already-measured task.

        Args:
            measured: The task and the route measured for it.

        Returns:
            The report.
        """
        return cls(
            measured=measured,
            speed_section=SpeedSection.from_measured_task(measured),
        )

    @property
    def task(self) -> Task:
        """The task being reported on."""
        return self.measured.task

    @property
    def earth_model(self) -> str:
        """The earth model the distances were measured on, named for output.

        Read off the *route*, which is where the legs were measured, rather
        than off the task, which is only where the choice was declared. The two
        agree for any measured task built by ``MeasuredTask.from_task``; when a
        caller assembles one by hand they need not, and the report was then
        naming a model its own numbers had not been computed on.

        ``earth.name_of`` owns the two names and the "missing means WGS84"
        rule, so this module does not have to know them.
        """
        return name_of(self.measured.route.earth_model)

    @property
    def task_distance_m(self) -> float:
        """S7F §7.2's task distance: optimized launch to goal, in meters."""
        return self.measured.total_m

    @property
    def speed_section_distance_m(self) -> float | None:
        """S7F §7.2's speed section distance, or None if the task has none."""
        return self.speed_section.distance_m if self.speed_section else None

    @property
    def speed_section_to_ess_m(self) -> float | None:
        """The ``taskToESS`` optimization's total, or None."""
        return self.speed_section.to_ess_m if self.speed_section else None

    @property
    def speed_section_pre_start_m(self) -> float | None:
        """How far along ``taskToESS`` the start sits, or None."""
        return self.speed_section.pre_start_m if self.speed_section else None

    @property
    def center_distance_m(self) -> float | None:
        """The published distance through centres — a convention, not a rule.

        The reading named by :data:`~pyxctsk.distance.PROPOSED_READING`. S7F
        defines no such number; see :mod:`~pyxctsk.distance.center_distance`.
        """
        return center_distance(self.task)

    @property
    def center_distance_reading(self) -> str:
        """Which reading :attr:`center_distance_m` used."""
        return PROPOSED_READING.value

    @property
    def center_distance_readings_m(self) -> dict[str, float | None]:
        """Every reading of the centre distance, for diagnosing a disagreement."""
        return center_distance_readings(self.task)

    def route(self) -> list[dict[str, Any]]:
        """One row per turnpoint: where it is, and where the route crosses it.

        Returns:
            A row per turnpoint, in task order, each carrying the turnpoint's
            centre and radius, the optimized crossing point, and the distance
            along the route to it — optimized, and through centres.
        """
        cumulative = self.measured.cumulative_m()
        # The centre column's prefix, from the module that owns the convention.
        # `task_distances` used to re-derive it leg by leg beside this one, so
        # the two published shapes measured the same thing twice.
        center_cumulative = cumulative_center_m(self.task)
        return [
            {
                "index": i,
                "name": tp.waypoint.name,
                "type": tp.type.value if tp.type else "",
                "radius_m": tp.radius,
                "center_lat": tp.waypoint.lat,
                "center_lon": tp.waypoint.lon,
                "route_lat": point[0],
                "route_lon": point[1],
                "cumulative_m": cumulative[i],
                "cumulative_center_m": center_cumulative[i],
            }
            for i, (tp, point) in enumerate(
                zip(self.task.turnpoints, self.measured.route.points)
            )
        ]

    def as_dict(self) -> dict[str, Any]:
        """Render the report as the JSON shape another implementation diffs.

        The key names and the ``notes`` block are part of the published
        surface; see ``docs/s7f-distance-reference.md``.

        Returns:
            A JSON-serializable report.
        """
        return {
            "pyxctsk_version": pyxctsk_version(),
            "s7f_edition": S7F_EDITION,
            "earth_model": self.earth_model,
            "task_distance_m": self.task_distance_m,
            "speed_section_distance_m": self.speed_section_distance_m,
            "speed_section_to_ess_m": self.speed_section_to_ess_m,
            "speed_section_pre_start_m": self.speed_section_pre_start_m,
            "center_distance_m": self.center_distance_m,
            "center_distance_reading": self.center_distance_reading,
            "center_distance_readings_m": self.center_distance_readings_m,
            "route": self.route(),
            "notes": dict(NOTES),
        }

    def as_text(self) -> str:
        """Render the report for a human rather than a diff.

        Reads the same fields :meth:`as_dict` does, rather than reading its
        output back out by string key — which is how the two came to disagree
        about what a missing value means.

        Returns:
            A plain-text rendering.
        """
        lines = [
            f"pyxctsk {pyxctsk_version()}  |  FAI S7F {S7F_EDITION}"
            f"  |  earth model: {self.earth_model}",
            "",
            f"  task distance (§7.2)        {self.task_distance_m / 1000:10.3f} km",
        ]
        if self.speed_section_distance_m is None:
            lines.append("  speed section (§7.2)              no SSS/ESS pair")
        else:
            lines.append(
                f"  speed section (§7.2)        "
                f"{self.speed_section_distance_m / 1000:10.3f} km"
            )
        center = self.center_distance_m
        shown = f"{center / 1000:10.3f} km" if center is not None else "       n/a"
        lines += [
            f"  through centres             {shown}   [{self.center_distance_reading}]",
            "",
            "  'through centres' is NOT defined by S7F. Other readings of it:",
        ]
        for name, value in self.center_distance_readings_m.items():
            reading = f"{value / 1000:10.3f} km" if value is not None else "       n/a"
            lines.append(f"    {name:26s} {reading}")
        lines += ["", "  optimized route:"]
        for point in self.route():
            lines.append(
                f"    {point['index']:2d} {point['name']:<10s} {point['type']:<8s}"
                f" r={point['radius_m']:>6} m"
                f"  {point['route_lat']:>10.6f} {point['route_lon']:>11.6f}"
                f"  {point['cumulative_m'] / 1000:8.3f} km"
            )
        return "\n".join(lines)
