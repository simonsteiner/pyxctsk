"""Tests for the models nested inside a QR task."""


class TestTheNestedModelsAreReachableOnTheirOwn:
    """``to_dict`` / ``from_dict`` on the objects nested inside a QR task.

    The task's own table reaches these shapes directly, so nothing inside the
    library calls these four methods any more — but they are public API, and
    ``QRCodeTakeoff``'s pair had never run at all.
    """

    def test_a_goal_round_trips(self):
        """Keys in the order tools.xcontest.org writes them."""
        from pyxctsk.qrcode.models import QRCodeGoal

        source = {"d": "18:00:00Z", "fa": 50, "t": 1}
        goal = QRCodeGoal.from_dict(source)

        assert goal.deadline is not None
        assert goal.deadline.hour == 18
        assert goal.finish_altitude == 50
        assert list(goal.to_dict()) == ["d", "fa", "t"]
        assert goal.to_dict() == source

    def test_a_start_round_trips(self):
        """The obsolete direction first, the type last."""
        from pyxctsk.qrcode.models import QRCodeSSS

        source = {"d": 2, "g": ["12:00:00Z"], "t": 1}
        sss = QRCodeSSS.from_dict(source)

        assert sss.time_gates[0].hour == 12
        assert list(sss.to_dict()) == ["d", "g", "t"]
        assert sss.to_dict() == source

    def test_a_takeoff_round_trips(self):
        """The one shape the task flattens, read on its own terms."""
        from pyxctsk.qrcode.models import QRCodeTakeoff

        source = {"o": "08:00:00Z", "c": "09:30:00Z"}
        takeoff = QRCodeTakeoff.from_dict(source)

        assert takeoff.time_open is not None and takeoff.time_close is not None
        assert (takeoff.time_open.hour, takeoff.time_close.hour) == (8, 9)
        assert takeoff.to_dict() == source

    def test_an_empty_takeoff_writes_nothing(self):
        """Absent times must stay absent rather than become null."""
        from pyxctsk.qrcode.models import QRCodeTakeoff

        assert QRCodeTakeoff().to_dict() == {}
