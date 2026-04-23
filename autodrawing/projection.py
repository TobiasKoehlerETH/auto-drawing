from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import sqrt

from .contracts import (
    Bounds2D,
    CanonicalCadModel,
    Point2D,
    Point3D,
    ProjectedArc,
    ProjectedCircle,
    ProjectedEdge,
    ProjectedViewGeometry,
    ProjectionBundle,
    ProjectionSourceRef,
)
from .view_planner import select_centerline_circles, select_hidden_line_policy


class ProjectionAdapter:
    name = "adapter"

    def build_projection(self, model: CanonicalCadModel, mode: str = "preview") -> ProjectionBundle:
        raise NotImplementedError


class OcctProjectionAdapter(ProjectionAdapter):
    name = "occt"
    _ISO_VIEW_DIRECTION = (1.0, 0.8, 1.1)
    _ISO_WORLD_UP = (0.0, 1.0, 0.0)

    def build_projection(self, model: CanonicalCadModel, mode: str = "preview") -> ProjectionBundle:
        shape = model.primary_shape
        bbox = shape.bounding_box.size
        hints = shape.feature_hints
        orthographic_axes = self._orthographic_axes_for_model(model)
        views = [
            self._orthographic_view(model, orthographic_axes["front"], hints, mode),
            self._orthographic_view(model, orthographic_axes["top"], hints, mode),
            self._orthographic_view(model, orthographic_axes["right"], hints, mode),
            self._isometric_view(model, bbox.x, bbox.y, bbox.z, mode),
        ]
        return ProjectionBundle(
            schema_version="1.0",
            model_name=model.source_name,
            mode=mode,  # type: ignore[arg-type]
            adapter="occt",
            views=views,
        )

    def _orthographic_axes_for_model(self, model: CanonicalCadModel) -> dict[str, "_OrthographicAxes"]:
        bbox = model.primary_shape.bounding_box.size
        candidates = [
            _OrthographicAxes(kind="front", width_axis="x", height_axis="y", depth_axis="z", width=bbox.x, height=bbox.y),
            _OrthographicAxes(kind="front", width_axis="x", height_axis="z", depth_axis="y", width=bbox.x, height=bbox.z),
            _OrthographicAxes(kind="front", width_axis="y", height_axis="z", depth_axis="x", width=bbox.y, height=bbox.z),
        ]
        front = max(candidates, key=lambda candidate: (candidate.width * candidate.height, min(candidate.width, candidate.height)))

        if (front.width_axis, front.height_axis, front.depth_axis) == ("x", "y", "z"):
            top = _OrthographicAxes(kind="top", width_axis="x", height_axis="z", depth_axis="y", width=bbox.x, height=bbox.z)
            right = _OrthographicAxes(kind="right", width_axis="y", height_axis="z", depth_axis="x", width=bbox.y, height=bbox.z)
        elif (front.width_axis, front.height_axis, front.depth_axis) == ("x", "z", "y"):
            top = _OrthographicAxes(kind="top", width_axis="x", height_axis="y", depth_axis="z", width=bbox.x, height=bbox.y)
            right = _OrthographicAxes(kind="right", width_axis="y", height_axis="z", depth_axis="x", width=bbox.y, height=bbox.z)
        else:
            top = _OrthographicAxes(kind="top", width_axis="y", height_axis="x", depth_axis="z", width=bbox.y, height=bbox.x)
            right = _OrthographicAxes(kind="right", width_axis="x", height_axis="z", depth_axis="y", width=bbox.x, height=bbox.z)

        front = _OrthographicAxes(
            kind="front",
            width_axis=front.width_axis,
            height_axis=front.height_axis,
            depth_axis=front.depth_axis,
            width=front.width,
            height=front.height,
        )
        return {"front": front, "top": top, "right": right}

    def _orthographic_view(
        self,
        model: CanonicalCadModel,
        axes: "_OrthographicAxes",
        hints,
        mode: str,
    ) -> ProjectedViewGeometry:
        kind = axes.kind
        width = axes.width
        height = axes.height
        width = max(width, 1.0)
        height = max(height, 1.0)
        bounds = Bounds2D.from_extents(0.0, 0.0, width, height)
        view_source = ProjectionSourceRef(
            id=f"{model.primary_shape.id}-{kind}",
            shape_id=model.primary_shape.id,
            role=f"{kind}-view",
            entity_kind="view",
        )

        using_source_edges = bool(model.primary_shape.source_edges)
        if using_source_edges:
            bounds, visible_edges, hidden_edges = self._source_edges_for_orthographic_view(model, axes, mode)
            width = max(bounds.width, 1.0)
            height = max(bounds.height, 1.0)
        else:
            visible_edges = [
                self._edge(
                    f"{kind}-outline",
                    [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height), (0.0, 0.0)],
                    view_source,
                    "visible",
                ),
                self._edge(f"{kind}-outline-bottom", [(0.0, 0.0), (width, 0.0)], view_source, "visible"),
                self._edge(f"{kind}-outline-right", [(width, 0.0), (width, height)], view_source, "visible"),
                self._edge(f"{kind}-outline-top", [(width, height), (0.0, height)], view_source, "visible"),
                self._edge(f"{kind}-outline-left", [(0.0, height), (0.0, 0.0)], view_source, "visible"),
            ]
            hidden_edges: list[ProjectedEdge] = []
        smooth_edges: list[ProjectedEdge] = []
        circles: list[ProjectedCircle] = []
        arcs: list[ProjectedArc] = []
        centerlines: list[ProjectedEdge] = []

        show_hidden = select_hidden_line_policy(model, kind, default=mode == "final")
        if show_hidden and not using_source_edges:
            hidden_edges.extend(
                [
                    self._edge(
                        f"{kind}-hidden-mid-x",
                        [(width * 0.5, height * 0.08), (width * 0.5, height * 0.92)],
                        view_source,
                        "hidden",
                    ),
                    self._edge(
                        f"{kind}-hidden-mid-y",
                        [(width * 0.1, height * 0.5), (width * 0.9, height * 0.5)],
                        view_source,
                        "hidden",
                    ),
                ]
            )

        perpendicular_axis = axes.depth_axis
        hole_hints = [hint for hint in hints if hint.kind in {"circular-hole", "hole-pattern"}]
        visible_hints = [hint for hint in hole_hints if (hint.axis or "z") == perpendicular_axis]
        hidden_hints = [hint for hint in hole_hints if hint not in visible_hints]

        for hint in visible_hints:
            centers = self._circle_centers(width, height, hint.count)
            radius = min(hint.radius or min(width, height) * 0.12, min(width, height) * 0.18)
            for index, center in enumerate(centers, start=1):
                circles.append(
                    ProjectedCircle(
                        id=f"{kind}-{hint.id}-circle-{index}",
                        center=center,
                        radius=radius,
                        source_ref=ProjectionSourceRef(
                            id=f"{kind}-{hint.id}-circle-{index}",
                            shape_id=model.primary_shape.id,
                            role=f"{kind}-circle",
                            entity_kind="circle",
                        ),
                    )
                )
                if select_centerline_circles(hints, kind):
                    centerlines.extend(self._circle_centerlines(kind, center, radius, model.primary_shape.id))

        if hidden_hints and show_hidden and not using_source_edges:
            hidden_edges.extend(
                [
                    self._edge(
                        f"{kind}-hidden-hole-left",
                        [(width * 0.38, height * 0.12), (width * 0.38, height * 0.88)],
                        view_source,
                        "hidden",
                    ),
                    self._edge(
                        f"{kind}-hidden-hole-right",
                        [(width * 0.62, height * 0.12), (width * 0.62, height * 0.88)],
                        view_source,
                        "hidden",
                    ),
                ]
            )

        if not using_source_edges and kind == "front" and model.primary_shape.bounding_box.size.z < max(model.primary_shape.bounding_box.size.x, 1.0) * 0.5:
            smooth_edges.append(
                self._edge(
                    f"{kind}-smooth-break",
                    [(width * 0.15, height * 0.15), (width * 0.85, height * 0.85)],
                    view_source,
                    "smooth",
                )
            )

        warnings = [diagnostic.message for diagnostic in model.diagnostics if diagnostic.severity != "info"]
        return ProjectedViewGeometry(
            id=f"geometry-{kind}",
            kind=kind,  # type: ignore[arg-type]
            label=kind.title(),
            source_ref=view_source,
            bounds=bounds,
            visible_edges=visible_edges,
            hidden_edges=hidden_edges,
            smooth_edges=smooth_edges,
            circles=circles,
            arcs=arcs,
            centerlines=centerlines,
            warnings=warnings,
        )

    def _isometric_view(self, model: CanonicalCadModel, width: float, depth: float, height: float, mode: str) -> ProjectedViewGeometry:
        if model.primary_shape.source_edges:
            return self._source_edges_for_isometric_view(model)

        vertices = {
            "A": self._project_isometric_point(0.0, 0.0, 0.0),
            "B": self._project_isometric_point(width, 0.0, 0.0),
            "C": self._project_isometric_point(width, depth, 0.0),
            "D": self._project_isometric_point(0.0, depth, 0.0),
            "E": self._project_isometric_point(0.0, 0.0, height),
            "F": self._project_isometric_point(width, 0.0, height),
            "G": self._project_isometric_point(width, depth, height),
            "H": self._project_isometric_point(0.0, depth, height),
        }

        min_x = min(point.x for point in vertices.values())
        min_y = min(point.y for point in vertices.values())
        margin = 10.0

        def normalized(name: str) -> Point2D:
            point = vertices[name]
            return Point2D(x=point.x - min_x + margin, y=point.y - min_y + margin)

        visible_edges = [
            self._edge("iso-visible-1", [normalized("B"), normalized("C")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-2", [normalized("C"), normalized("G")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-3", [normalized("G"), normalized("F")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-4", [normalized("F"), normalized("B")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-5", [normalized("D"), normalized("C")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-6", [normalized("H"), normalized("D")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-7", [normalized("E"), normalized("F")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-8", [normalized("H"), normalized("E")], self._view_ref(model, "isometric"), "visible"),
            self._edge("iso-visible-9", [normalized("G"), normalized("H")], self._view_ref(model, "isometric"), "visible"),
        ]
        hidden_edges = []
        show_hidden = select_hidden_line_policy(model, "isometric", default=mode == "final")
        if show_hidden:
            hidden_edges = [
                self._edge("iso-hidden-1", [normalized("A"), normalized("B")], self._view_ref(model, "isometric"), "hidden"),
                self._edge("iso-hidden-2", [normalized("A"), normalized("D")], self._view_ref(model, "isometric"), "hidden"),
                self._edge("iso-hidden-3", [normalized("A"), normalized("E")], self._view_ref(model, "isometric"), "hidden"),
            ]

        width_2d = max(point.x for point in vertices.values()) - min_x + margin * 2
        height_2d = max(point.y for point in vertices.values()) - min_y + margin * 2
        return ProjectedViewGeometry(
            id="geometry-isometric",
            kind="isometric",
            label="Isometric",
            source_ref=self._view_ref(model, "isometric"),
            bounds=Bounds2D.from_extents(0.0, 0.0, max(width_2d, 20.0), max(height_2d, 20.0)),
            visible_edges=visible_edges,
            hidden_edges=hidden_edges,
            smooth_edges=[],
            circles=[],
            arcs=[],
            centerlines=[],
        )

    def _source_edges_for_orthographic_view(
        self, model: CanonicalCadModel, axes: "_OrthographicAxes", mode: str
    ) -> tuple[Bounds2D, list[ProjectedEdge], list[ProjectedEdge]]:
        bbox = model.primary_shape.bounding_box
        kind = axes.kind
        view_source = self._view_ref(model, kind)

        def project(point: Point3D) -> tuple[Point2D, float]:
            return Point2D(x=self._axis_value(point, axes.width_axis), y=self._axis_value(point, axes.height_axis)), self._axis_value(point, axes.depth_axis)

        projected_segments: list[tuple[str, Point2D, Point2D, float, float, str]] = []
        all_points: list[Point2D] = []
        for edge in model.primary_shape.source_edges:
            start_2d, start_depth = project(edge.start)
            end_2d, end_depth = project(edge.end)
            if self._same_2d_point(start_2d, end_2d):
                continue
            projected_segments.append((edge.id, start_2d, end_2d, start_depth, end_depth, edge.curve_kind))
            all_points.extend([start_2d, end_2d])

        if not all_points:
            return Bounds2D.from_extents(0.0, 0.0, 1.0, 1.0), [], []

        raw_bounds = Bounds2D.from_points(all_points)
        visible_by_key: dict[tuple[tuple[float, float], tuple[float, float]], ProjectedEdge] = {}
        hidden_by_key: dict[tuple[tuple[float, float], tuple[float, float]], ProjectedEdge] = {}
        near_depth, far_depth = self._depth_extents(bbox, axes.depth_axis)
        show_hidden = select_hidden_line_policy(model, kind, default=mode == "final")

        for edge_id, start, end, start_depth, end_depth, curve_kind in projected_segments:
            normalized_start = Point2D(x=start.x - raw_bounds.x_min, y=start.y - raw_bounds.y_min)
            normalized_end = Point2D(x=end.x - raw_bounds.x_min, y=end.y - raw_bounds.y_min)
            key = self._segment_key(normalized_start, normalized_end)
            depth_visible = self._edge_is_visible(start_depth, end_depth, near_depth, far_depth)
            style = "visible" if depth_visible or not show_hidden else "hidden"
            projected = self._edge(
                f"{kind}-{edge_id}",
                [normalized_start, normalized_end],
                ProjectionSourceRef(id=f"{model.primary_shape.id}-{edge_id}", shape_id=model.primary_shape.id, role=f"{kind}-edge", entity_kind="edge"),
                style,
            )
            if style == "visible":
                visible_by_key[key] = projected
                hidden_by_key.pop(key, None)
            elif key not in visible_by_key:
                hidden_by_key[key] = projected

        bounds = Bounds2D.from_extents(0.0, 0.0, max(raw_bounds.width, 1.0), max(raw_bounds.height, 1.0))
        return bounds, list(visible_by_key.values()), list(hidden_by_key.values())

    def _source_edges_for_isometric_view(self, model: CanonicalCadModel) -> ProjectedViewGeometry:
        bbox = model.primary_shape.bounding_box
        triangles = model.primary_shape.source_triangles

        def project(point: Point3D) -> tuple[Point2D, float]:
            point_2d = self._project_isometric_point(point.x, point.y, point.z)
            _, _, view = self._isometric_basis()
            depth = point.x * view[0] + point.y * view[1] + point.z * view[2]
            return point_2d, depth

        projected_triangles: list[tuple[tuple[Point2D, float], tuple[Point2D, float], tuple[Point2D, float]]] = []
        _, _, view_direction = self._isometric_basis()
        for triangle in triangles:
            normal = self._triangle_normal_3d(triangle.a, triangle.b, triangle.c)
            if normal is None:
                continue
            if normal[0] * view_direction[0] + normal[1] * view_direction[1] + normal[2] * view_direction[2] <= 1e-6:
                continue
            projected_triangles.append(
                (
                    project(triangle.a),
                    project(triangle.b),
                    project(triangle.c),
                )
            )

        raw_segments: list[tuple[str, Point2D, Point2D, float, float]] = []
        all_points: list[Point2D] = []
        for edge in model.primary_shape.source_edges:
            start, start_depth = project(edge.start)
            end, end_depth = project(edge.end)
            if edge.adjacent_normals and not self._edge_has_front_facing_normal(edge, view_direction):
                continue
            if triangles:
                if not self._isometric_edge_visible_against_triangles(start, end, start_depth, end_depth, projected_triangles):
                    continue
            elif not self._isometric_edge_is_visible(edge.start, edge.end, bbox):
                continue
            if self._same_2d_point(start, end):
                continue
            raw_segments.append((edge.id, start, end, start_depth, end_depth))
            all_points.extend([start, end])

        if not all_points:
            return ProjectedViewGeometry(
                id="geometry-isometric",
                kind="isometric",
                label="Isometric",
                source_ref=self._view_ref(model, "isometric"),
                bounds=Bounds2D.from_extents(0.0, 0.0, 20.0, 20.0),
                visible_edges=[],
                hidden_edges=[],
                smooth_edges=[],
                circles=[],
                arcs=[],
                centerlines=[],
            )

        raw_bounds = Bounds2D.from_points(all_points)
        margin = 10.0
        visible_by_key: dict[tuple[tuple[float, float], tuple[float, float]], ProjectedEdge] = {}
        for edge_id, start, end, _start_depth, _end_depth in raw_segments:
            normalized_start = Point2D(x=start.x - raw_bounds.x_min + margin, y=start.y - raw_bounds.y_min + margin)
            normalized_end = Point2D(x=end.x - raw_bounds.x_min + margin, y=end.y - raw_bounds.y_min + margin)
            key = self._segment_key(normalized_start, normalized_end)
            visible_by_key[key] = self._edge(
                f"isometric-{edge_id}",
                [normalized_start, normalized_end],
                ProjectionSourceRef(id=f"{model.primary_shape.id}-{edge_id}", shape_id=model.primary_shape.id, role="isometric-edge", entity_kind="edge"),
                "visible",
            )

        return ProjectedViewGeometry(
            id="geometry-isometric",
            kind="isometric",
            label="Isometric",
            source_ref=self._view_ref(model, "isometric"),
            bounds=Bounds2D.from_extents(0.0, 0.0, max(raw_bounds.width + margin * 2, 20.0), max(raw_bounds.height + margin * 2, 20.0)),
            visible_edges=list(visible_by_key.values()),
            hidden_edges=[],
            smooth_edges=[],
            circles=[],
            arcs=[],
            centerlines=[],
        )

    def _depth_extents(self, bbox, axis: str) -> tuple[float, float]:
        if axis == "x":
            return bbox.min.x, bbox.max.x
        if axis == "y":
            return bbox.min.y, bbox.max.y
        return bbox.min.z, bbox.max.z

    def _axis_value(self, point: Point3D, axis: str) -> float:
        if axis == "x":
            return point.x
        if axis == "y":
            return point.y
        return point.z

    def _edge_is_visible(self, start_depth: float, end_depth: float, near_depth: float, far_depth: float) -> bool:
        eps = max(abs(far_depth - near_depth), 1.0) * 1e-5
        touches_near = abs(start_depth - near_depth) <= eps or abs(end_depth - near_depth) <= eps
        spans_depth = abs(start_depth - end_depth) > eps
        return touches_near or spans_depth

    def _isometric_edge_is_visible(self, start: Point3D, end: Point3D, bbox) -> bool:
        eps = max(bbox.size.x, bbox.size.y, bbox.size.z, 1.0) * 1e-5

        def on_plane(value: float, target: float) -> bool:
            return abs(value - target) <= eps

        view_x, view_y, view_z = self._normalized(self._ISO_VIEW_DIRECTION)
        visible_planes = (
            bbox.max.x if view_x >= 0 else bbox.min.x,
            bbox.max.y if view_y >= 0 else bbox.min.y,
            bbox.max.z if view_z >= 0 else bbox.min.z,
        )

        return any(
            (
                on_plane(start.x, visible_planes[0]) and on_plane(end.x, visible_planes[0]),
                on_plane(start.y, visible_planes[1]) and on_plane(end.y, visible_planes[1]),
                on_plane(start.z, visible_planes[2]) and on_plane(end.z, visible_planes[2]),
            )
        )

    def _project_isometric_point(self, x: float, y: float, z: float) -> Point2D:
        right, up, _ = self._isometric_basis()
        return Point2D(
            x=x * right[0] + y * right[1] + z * right[2],
            y=x * up[0] + y * up[1] + z * up[2],
        )

    def _isometric_edge_visible_against_triangles(
        self,
        start: Point2D,
        end: Point2D,
        start_depth: float,
        end_depth: float,
        projected_triangles: list[tuple[tuple[Point2D, float], tuple[Point2D, float], tuple[Point2D, float]]],
    ) -> bool:
        samples = (0.2, 0.5, 0.8)
        for t in samples:
            point = Point2D(
                x=start.x + (end.x - start.x) * t,
                y=start.y + (end.y - start.y) * t,
            )
            depth = start_depth + (end_depth - start_depth) * t
            if not self._point_occluded_by_isometric_triangles(point, depth, projected_triangles):
                return True
        return False

    def _point_occluded_by_isometric_triangles(
        self,
        point: Point2D,
        depth: float,
        projected_triangles: list[tuple[tuple[Point2D, float], tuple[Point2D, float], tuple[Point2D, float]]],
    ) -> bool:
        for triangle in projected_triangles:
            coverage = self._triangle_barycentric(point, triangle[0][0], triangle[1][0], triangle[2][0])
            if coverage is None:
                continue
            w0, w1, w2 = coverage
            triangle_depth = triangle[0][1] * w0 + triangle[1][1] * w1 + triangle[2][1] * w2
            if triangle_depth > depth + 1e-5:
                return True
        return False

    def _triangle_barycentric(self, p: Point2D, a: Point2D, b: Point2D, c: Point2D) -> tuple[float, float, float] | None:
        denominator = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
        if abs(denominator) <= 1e-9:
            return None
        w0 = ((b.y - c.y) * (p.x - c.x) + (c.x - b.x) * (p.y - c.y)) / denominator
        w1 = ((c.y - a.y) * (p.x - c.x) + (a.x - c.x) * (p.y - c.y)) / denominator
        w2 = 1.0 - w0 - w1
        tolerance = 1e-6
        if w0 < -tolerance or w1 < -tolerance or w2 < -tolerance:
            return None
        return w0, w1, w2

    def _triangle_normal_3d(self, a: Point3D, b: Point3D, c: Point3D) -> tuple[float, float, float] | None:
        ab = (b.x - a.x, b.y - a.y, b.z - a.z)
        ac = (c.x - a.x, c.y - a.y, c.z - a.z)
        nx = ab[1] * ac[2] - ab[2] * ac[1]
        ny = ab[2] * ac[0] - ab[0] * ac[2]
        nz = ab[0] * ac[1] - ab[1] * ac[0]
        length = sqrt(nx * nx + ny * ny + nz * nz)
        if length <= 1e-9:
            return None
        return (nx / length, ny / length, nz / length)

    def _edge_has_front_facing_normal(self, edge, view_direction: tuple[float, float, float]) -> bool:
        for normal in edge.adjacent_normals:
            if normal.x * view_direction[0] + normal.y * view_direction[1] + normal.z * view_direction[2] > 1e-6:
                return True
        return False

    def _isometric_basis(self) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
        view = self._normalized(self._ISO_VIEW_DIRECTION)
        right = self._normalized(self._cross(self._ISO_WORLD_UP, view))
        up = self._cross(view, right)
        return right, up, view

    def _normalized(self, vector: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = vector
        length = sqrt(x * x + y * y + z * z) or 1.0
        return x / length, y / length, z / length

    def _cross(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0],
        )

    def _same_2d_point(self, a: Point2D, b: Point2D) -> bool:
        return round(a.x, 6) == round(b.x, 6) and round(a.y, 6) == round(b.y, 6)

    def _segment_key(self, a: Point2D, b: Point2D) -> tuple[tuple[float, float], tuple[float, float]]:
        start = (round(a.x, 5), round(a.y, 5))
        end = (round(b.x, 5), round(b.y, 5))
        return tuple(sorted([start, end]))  # type: ignore[return-value]


    def _circle_centers(self, width: float, height: float, count: int) -> list[Point2D]:
        if count >= 4:
            return [
                Point2D(x=width * 0.28, y=height * 0.28),
                Point2D(x=width * 0.72, y=height * 0.28),
                Point2D(x=width * 0.28, y=height * 0.72),
                Point2D(x=width * 0.72, y=height * 0.72),
            ]
        if count == 3:
            return [
                Point2D(x=width * 0.3, y=height * 0.5),
                Point2D(x=width * 0.5, y=height * 0.5),
                Point2D(x=width * 0.7, y=height * 0.5),
            ]
        if count == 2:
            return [
                Point2D(x=width * 0.38, y=height * 0.5),
                Point2D(x=width * 0.62, y=height * 0.5),
            ]
        return [Point2D(x=width * 0.5, y=height * 0.5)]

    def _circle_centerlines(self, view_name: str, center: Point2D, radius: float, shape_id: str) -> list[ProjectedEdge]:
        ref = ProjectionSourceRef(id=f"{view_name}-centerline", shape_id=shape_id, role="centerline", entity_kind="edge")
        return [
            self._edge(
                f"{view_name}-centerline-h-{center.x:.2f}-{center.y:.2f}",
                [(center.x - radius * 1.8, center.y), (center.x + radius * 1.8, center.y)],
                ref,
                "centerline",
            ),
            self._edge(
                f"{view_name}-centerline-v-{center.x:.2f}-{center.y:.2f}",
                [(center.x, center.y - radius * 1.8), (center.x, center.y + radius * 1.8)],
                ref,
                "centerline",
            ),
        ]

    def _view_ref(self, model: CanonicalCadModel, kind: str) -> ProjectionSourceRef:
        return ProjectionSourceRef(
            id=f"{model.primary_shape.id}-{kind}",
            shape_id=model.primary_shape.id,
            role=f"{kind}-view",
            entity_kind="view",
        )

    def _edge(
        self,
        edge_id: str,
        points: Iterable[tuple[float, float] | Point2D],
        source_ref: ProjectionSourceRef,
        style_role: str,
    ) -> ProjectedEdge:
        normalized_points = [
            point if isinstance(point, Point2D) else Point2D(x=point[0], y=point[1]) for point in points
        ]
        return ProjectedEdge(
            id=edge_id,
            points=normalized_points,
            source_ref=source_ref,
            style_role=style_role,  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class _OrthographicAxes:
    kind: str
    width_axis: str
    height_axis: str
    depth_axis: str
    width: float
    height: float


class TechDrawOracleAdapter(ProjectionAdapter):
    name = "techdraw-oracle"

    def build_projection(self, model: CanonicalCadModel, mode: str = "preview") -> ProjectionBundle:
        raise RuntimeError("TechDraw oracle projection is only available in a local FreeCAD-backed environment.")


class ProjectionService:
    def __init__(self, adapter: ProjectionAdapter | None = None) -> None:
        self.adapter = adapter or OcctProjectionAdapter()

    def build_projection(self, model: CanonicalCadModel, mode: str = "preview") -> ProjectionBundle:
        return self.adapter.build_projection(model, mode=mode)
