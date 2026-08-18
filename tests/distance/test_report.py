"""The S7F distance report — the surface another implementation diffs against.

These used to live in `tests/test_cli.py`, where asserting *what the report
says* meant building a runner, invoking a click command, checking an exit code
and parsing stdout — because the report was two private functions inside
`cli.py`. They assert on the value now. What is left in `test_cli.py` is the
wiring: that the command renders this report and writes it out.
"""

import pytest

from pyxctsk import DistanceReport, Task, TaskType
from pyxctsk.distance import NOTES, TooFewTurnpointsError
from tests.builders import task, turnpoint
from tests.corpus import reference_task


def _report(stem: str = "task_pepi") -> DistanceReport:
    """The report for a reference task."""
    return DistanceReport.from_task(reference_task(stem).task)


class TestTheNumbersItPublishes:
    """What the report says, read off the value."""

    def test_it_reports_both_of_s7f_7_2_s_distances(self):
        """The two the Sporting Code actually defines."""
        report = _report()

        assert report.task_distance_m == pytest.approx(92001.6, abs=1.0)
        assert report.speed_section_distance_m == pytest.approx(86761.2, abs=1.0)

    def test_it_reports_the_centre_distance_and_says_it_is_undefined(self):
        """The number boards publish that S7F does not define.

        A vendor reading this output must not come away thinking the convention
        is specified, so the disclaimer travels with the number.
        """
        report = _report()

        assert report.center_distance_m == pytest.approx(321439.7, abs=1.0)
        assert report.center_distance_reading == "LAUNCH_TO_GOAL"
        assert "NOT DEFINED BY S7F" in NOTES["center_distance_m"]

    def test_it_reports_every_reading_of_the_centre_distance(self):
        """So a disagreement can be traced to a convention rather than a bug."""
        readings = _report().center_distance_readings_m

        assert set(readings) == {
            "LAUNCH_TO_GOAL",
            "LAUNCH_TO_GOAL_BOUNDARY",
            "START_TO_GOAL",
        }
        values = [v for v in readings.values() if v is not None]
        assert max(values) - min(values) > 39_000

    def test_it_reports_the_route_points(self):
        """The whole point: a total says two implementations disagree, these say where."""
        report = _report()

        assert len(report.route()) == len(report.task.turnpoints)
        first, last = report.route()[0], report.route()[-1]
        assert first["cumulative_m"] == 0.0
        assert last["cumulative_m"] == pytest.approx(report.task_distance_m)
        for point in report.route():
            assert {"route_lat", "route_lon", "center_lat", "center_lon"} <= set(point)

    def test_it_names_the_version_and_the_spec_edition(self):
        """A number without a provenance cannot be compared later."""
        rendered = _report().as_dict()

        assert rendered["s7f_edition"] == "2026 V1.0"
        assert rendered["pyxctsk_version"]
        assert str(rendered["earth_model"]).startswith("WGS84")

    def test_a_task_with_no_speed_section_reports_null_not_zero(self):
        """An XC route has no SSS/ESS pair, and zero would read as a measurement."""
        report = _report("task_dami_route")

        assert report.speed_section is None
        assert report.speed_section_distance_m is None
        assert report.speed_section_to_ess_m is None
        assert report.speed_section_pre_start_m is None
        assert report.task_distance_m > 0

    def test_the_documented_snippet_does_not_crash_without_a_speed_section(self):
        """`docs/s7f-distance-reference.md` used to tell readers to hand-roll this.

        Its snippet did ``SpeedSection.from_task(t).distance_m``, which is an
        AttributeError on a third of the corpus. Reading the property is the
        documented way now, and it answers None.
        """
        for stem in ("task_dami_route", "task_pepi"):
            report = DistanceReport.from_task(reference_task(stem).task)

            assert report.as_dict()["task_distance_m"] > 0


class TestTheTwoRenderings:
    """`as_dict` and `as_text` read one set of fields, so they cannot disagree."""

    def test_the_dict_carries_every_published_number(self):
        """The JSON shape is the published surface; its keys are pinned."""
        rendered = _report().as_dict()

        assert set(rendered) == {
            "pyxctsk_version",
            "s7f_edition",
            "earth_model",
            "task_distance_m",
            "speed_section_distance_m",
            "speed_section_to_ess_m",
            "speed_section_pre_start_m",
            "center_distance_m",
            "center_distance_reading",
            "center_distance_readings_m",
            "route",
            "notes",
        }

    def test_every_note_names_a_number_the_report_publishes(self):
        """A note about a key the report does not carry would be a lie."""
        rendered = _report().as_dict()

        assert set(NOTES) <= set(rendered)

    def test_the_text_and_the_dict_agree_on_the_task_distance(self):
        """The two renderings are of one value, not two assemblies of it."""
        report = _report()

        assert f"{report.task_distance_m / 1000:.3f} km" in report.as_text()

    def test_the_text_says_the_centre_distance_is_undefined(self):
        """The disclaimer travels into the human rendering too."""
        assert "NOT defined by S7F" in _report().as_text()

    def test_the_text_names_the_absent_speed_section_rather_than_printing_zero(self):
        """The rendering that used to divide an absent value by 1000."""
        text = _report("task_dami_route").as_text()

        assert "no SSS/ESS pair" in text
        assert "0.000 km" not in text.split("optimized route:")[0]

    def test_the_text_lists_every_route_point(self):
        """One line per turnpoint, under the route heading."""
        report = _report()

        body = report.as_text().split("optimized route:")[1].strip().splitlines()
        assert len(body) == len(report.route())


class TestTooFewTurnpoints:
    """One turnpoint has no leg, so it has no distance — and no report."""

    def test_a_task_with_one_turnpoint_is_refused(self):
        """It used to be the CLI alone that knew this; the library answered 0.0."""
        built = task(turnpoint("A", 46.0, 8.0, radius=400))

        with pytest.raises(TooFewTurnpointsError):
            DistanceReport.from_task(built)

    def test_an_empty_task_is_refused(self):
        """Same rule, at the other degenerate end."""
        with pytest.raises(TooFewTurnpointsError):
            DistanceReport.from_task(
                Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])
            )

    def test_the_message_says_what_is_wrong(self):
        """The CLI prints this verbatim, so it is written for a user."""
        built = task(turnpoint("A", 46.0, 8.0, radius=400))

        with pytest.raises(TooFewTurnpointsError, match="at least two turnpoints"):
            DistanceReport.from_task(built)
