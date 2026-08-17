"""Rendering a task as a map: KML and GeoJSON.

These modules turn a :class:`~pyxctsk.Task` into something a map can draw —
cylinders as polygons, the optimized route as a line, the goal line and its
control zone as their own shapes. They read the task and the distance
calculations; nothing reads back into them, which is what makes this the
outermost layer of the library.

- :mod:`~pyxctsk.export.kml` — ``task_to_kml``, ``drawing_to_kml``
- :mod:`~pyxctsk.export.geojson` — ``generate_task_geojson``, ``drawing_to_geojson``
- :mod:`~pyxctsk.export.common` — ``TaskDrawing``, plus the styling both writers need

``TaskDrawing.from_task`` derives what a task looks like once — the turnpoints to
draw, the goal line, the optimized route — and both writers render that value.
Rendering one task in both formats therefore optimizes the route once, and the
two formats cannot disagree about the task's shape.

The geometry itself is not here: cylinders come from
:mod:`pyxctsk.distance.turnpoint` and the goal line from
:mod:`pyxctsk.distance.goal_line`, because distance calculation needs the same
shapes and must not depend on the format they are drawn in.

Modules inside the package import each other directly rather than through this
file; the re-exports below are for callers outside it.
"""

from .common import TaskDrawing
from .geojson import drawing_to_geojson, generate_task_geojson
from .kml import drawing_to_kml, task_to_kml

__all__ = [
    "TaskDrawing",
    "drawing_to_geojson",
    "drawing_to_kml",
    "generate_task_geojson",
    "task_to_kml",
]
