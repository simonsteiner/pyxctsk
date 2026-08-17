# pyxctsk

XCTrack's task format for paragliding and hang gliding competitions: reading it,
writing it, and measuring the route a pilot has to fly. The vocabulary below is
the competition's and the format's, not this library's — where the two disagree,
the format's spelling is noted so the wire and the domain stay tellable apart.

## The task

**Task**:
One competition course: an ordered list of turnpoints plus the timing and goal
rules that score it.
_Avoid_: route, course, flight plan

**Turnpoint**:
One point of the course — a waypoint with a radius, making a cylinder a pilot
must touch. Position and radius are separate concerns: the waypoint says where,
the turnpoint says how close.
_Avoid_: gate, marker

**Waypoint**:
A named position: latitude, longitude and altitude. Carries no radius and no
role in the course; it is the geography a turnpoint points at.

**Cylinder**:
The volume a turnpoint defines — its radius swept vertically. What "reaching a
turnpoint" means.

**Turnpoint type**:
The role a turnpoint plays beyond being a point to touch: takeoff, start of
speed section, or end of speed section. Most turnpoints have none.

**Speed section**:
The timed part of the task, from the SSS to the ESS. Everything before the SSS
and after the ESS is flown but not raced.
_Avoid_: race section, timed leg

**SSS**:
Start of Speed Section — the turnpoint where the clock starts.

**ESS**:
End of Speed Section — the turnpoint where the clock stops. Often, but not
always, the last turnpoint.

**Goal**:
Where the task ends. Either the last turnpoint's cylinder, or a goal line.
_Avoid_: finish, end point

**Goal line**:
A line perpendicular to the approach, centred on the last turnpoint, that a
pilot crosses rather than enters. Its total length is twice that turnpoint's
radius — the radius means half the line, not a cylinder. A goal line needs an
approach direction, so a task whose previous turnpoint sits on the goal has
none.

**Control zone**:
The semicircular area behind a goal line. A crossing counts only from the
approach side, and this is the side that does not count.

**Elevated goal**:
A goal that ends above the ground, given as metres above the last turnpoint's
altitude. Some producers instead write an absolute height above sea level in a
field the spec does not define — a different measurement wearing a similar
name, and never read as this one.

**Time gate**:
One of the start times a race start offers. A pilot may cross the SSS at any
gate.

**Deadline**:
The time after which reaching goal no longer scores.

## Measuring it

**Earth model**:
The shape of the earth a task's distances are measured on — the WGS84 ellipsoid
or the FAI sphere. A property of the task, so every length in a task agrees:
route, legs, goal line and control zone alike.

**Optimized route**:
The shortest path that touches every turnpoint's cylinder in order. What a task
is actually worth, as against the longer distance through the turnpoint centres.
_Avoid_: shortest path, optimal route, opt distance

**Leg**:
One segment of the optimized route, between two consecutive points on it. Legs
are where a route's length lives; a total or a distance-so-far is read off
them, never measured separately.

**Touching**:
Reaching a cylinder's boundary, which every turnpoint requires in turn — so two
turnpoints sharing a centre make a route fly out and back rather than skipping
one.

## The two formats

**Full format**:
The task file: JSON with spelled-out keys, the format the spec calls the task
format.
_Avoid_: long format, normal format, JSON format

**QR format**:
The compact encoding carried in a QR code, with one- and two-letter keys and
coordinates packed into a single polyline string. Small enough to scan in
direct sunlight, and lossy about a metre in position.
_Avoid_: short format, compressed format — "compressed" means the zlib variant
of this same encoding, which is a different question

**Competition shape**:
A task with cylinders, timing and a goal: the full course. Both formats have
one.

**XC/Waypoints shape**:
"A simple route from waypoints without cylinders" — names and positions only,
with no radii, no timing and no goal. Both formats have one, and it is a
different shape rather than a subset that happens to leave fields out.
_Avoid_: simplified task, waypoint task, waypoints mode

## What a format is made of

**Serializable shape**:
One object as it appears on the wire — a turnpoint in the full format, a goal in
the QR one, an XC/Waypoints task. Shapes and classes are not one to one: a class
that both formats express is two shapes, and a class each format writes two ways
is two more.

**Field table**:
A shape's whole mapping, declared once as an ordered list of fields. Its order
is the order keys appear on the wire.

**Field**:
One row of a field table: a slice of an object and the wire keys that slice
occupies. Keys plural — a turnpoint's whole geometry is one key, and a takeoff
window is one value across two.

**Wire key**:
The name a field goes by in a format. The same concept has two: a turnpoint's
type is `type` in the full format and `t` in the QR one.

**Unknown key**:
A key a shape does not define. Carried back out verbatim and never interpreted,
because real producers put data outside the format and dropping it loses a
round-trip. Unknown is relative to a shape: a key one shape defines is unknown
to the one beside it, and a key crossing between formats may land on a name the
other format has already spent.
_Avoid_: extra field, custom field, passthrough field

**Extension**:
The format's own mechanism for manufacturer data: a list of opaque objects, each
naming who wrote it. Distinct from an unknown key in being sanctioned — both are
carried without being read.
