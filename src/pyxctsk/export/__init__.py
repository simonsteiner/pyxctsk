"""Rendering a task as a map: KML and GeoJSON.

These modules turn a :class:`~pyxctsk.Task` into something a map can draw —
cylinders as polygons, the optimized route as a line, the goal line and its
control zone as their own shapes. They read the task and the distance
calculations; nothing reads back into them, which is what makes this the
outermost layer of the library.

- :mod:`~pyxctsk.export.kml` — ``task_to_kml``
- :mod:`~pyxctsk.export.geojson` — ``generate_task_geojson``
- :mod:`~pyxctsk.export.common` — the shapes and styling both writers need

The geometry itself is not here: cylinders come from
:mod:`pyxctsk.distance.turnpoint` and the goal line from
:mod:`pyxctsk.distance.goal_line`, because distance calculation needs the same
shapes and must not depend on the format they are drawn in.

Modules inside the package import each other directly rather than through this
file; the re-exports below are for callers outside it.
"""

from .common import get_turnpoints_to_render
from .geojson import generate_task_geojson
from .kml import task_to_kml

__all__ = [
    "generate_task_geojson",
    "get_turnpoints_to_render",
    "task_to_kml",
]
