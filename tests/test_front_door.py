"""The front door: `pyxctsk.__all__` names every answer the library documents."""


class TestTheFrontDoorNamesTheAnswers:
    """`pyxctsk.__all__` is the whole library's interface, not a sample of it.

    Its export set had no rule: it carried 7 of `pyxctsk.distance`'s 22 names,
    including `distance_through_centers` — documented as "the primitive, not
    the published number" — while `center_distance`, the call that docstring
    tells you to make instead, was absent. It also exported `OptimizedRoute`
    and `task_distances_from` without exporting anything that could build the
    argument, which is why `docs/s7f-distance-reference.md` reached past it.
    """

    #: What a doc, a docstring or a test tells a caller to import from the top
    #: level. Adding a name here without exporting it fails.
    DOCUMENTED = (
        "DistanceReport",
        "MeasuredTask",
        "TaskDrawing",
        "Task",
        "parse_task",
        "render_task",
        "OUTPUT_FORMATS",
        "center_distance",
        "center_distance_readings",
        "CenterDistanceReading",
        "PROPOSED_READING",
        "GoalLine",
        "TooFewTurnpointsError",
        "TaskValidationError",
        "pyXCTSKError",
        "ValidationRule",
        "calculate_iteratively_refined_route",
        "task_to_turnpoints",
    )

    def test_every_documented_name_is_reachable_from_the_front_door(self):
        """Reaching into a subpackage should be a choice, not a workaround."""
        import pyxctsk

        missing = [n for n in self.DOCUMENTED if not hasattr(pyxctsk, n)]

        assert missing == []
        assert [n for n in self.DOCUMENTED if n not in pyxctsk.__all__] == []

    def test_the_published_reading_travels_with_the_primitive(self):
        """Exporting `distance_through_centers` alone is what misled a caller.

        The primitive stays — it is a real function over `TaskTurnpoint`s — but
        the number a task board publishes has to be reachable beside it.
        """
        import pyxctsk

        if "distance_through_centers" in pyxctsk.__all__:
            assert "center_distance" in pyxctsk.__all__
            assert "CenterDistanceReading" in pyxctsk.__all__

    def test_every_exported_name_resolves(self):
        """`__all__` and the module cannot disagree about what exists."""
        import pyxctsk

        assert [n for n in pyxctsk.__all__ if not hasattr(pyxctsk, n)] == []

    def test_a_route_can_be_built_by_a_caller_who_only_uses_the_front_door(self):
        """`OptimizedRoute` was exported with no exported way to make one."""
        import pyxctsk

        assert hasattr(pyxctsk, "OptimizedRoute")
        assert hasattr(pyxctsk, "MeasuredTask")
        route = pyxctsk.MeasuredTask.from_task(
            pyxctsk.Task(
                task_type=pyxctsk.TaskType.CLASSIC,
                version=1,
                turnpoints=[
                    pyxctsk.Turnpoint(
                        radius=400,
                        waypoint=pyxctsk.Waypoint(
                            name="A", lat=46.0, lon=8.0, alt_smoothed=0
                        ),
                    ),
                    pyxctsk.Turnpoint(
                        radius=400,
                        waypoint=pyxctsk.Waypoint(
                            name="B", lat=46.5, lon=8.5, alt_smoothed=0
                        ),
                    ),
                ],
            )
        ).route

        assert isinstance(route, pyxctsk.OptimizedRoute)
