"""Stdlib-only checks for the activity graph renderer. Run: python scripts/test_activity_graph.py"""

from datetime import date, timedelta
from xml.etree import ElementTree
import re
import sys

from activity_graph import curve, render, y_ticks


def segment_y_bounds(path: str) -> list[tuple[float, float, float, float]]:
    """Return (start, control1, control2, end) y values for every cubic segment."""
    start_y = float(re.match(r"M [-\d.]+ ([-\d.]+)", path).group(1))
    segments = []
    for c1y, c2y, end_y in re.findall(
        r"C [-\d.]+ ([-\d.]+), [-\d.]+ ([-\d.]+), [-\d.]+ ([-\d.]+)", path
    ):
        segments.append((start_y, float(c1y), float(c2y), float(end_y)))
        start_y = float(end_y)
    return segments


def test_curve_deep_trough_stays_within_segment_bounds_expected() -> None:
    # A cubic Bezier lies inside the convex hull of its control points, so bounded
    # control points prove the drawn line never overshoots past a zero-contribution day.
    ys = [340.0, 80.0, 340.0, 100.0, 340.0, 340.0, 200.0]
    path = curve([(index * 30.0, y) for index, y in enumerate(ys)])
    for start_y, c1y, c2y, end_y in segment_y_bounds(path):
        low, high = min(start_y, end_y), max(start_y, end_y)
        assert low <= c1y <= high, f"control 1 at {c1y} escapes [{low}, {high}]"
        assert low <= c2y <= high, f"control 2 at {c2y} escapes [{low}, {high}]"


def test_curve_flat_run_keeps_control_points_flat_expected() -> None:
    path = curve([(index * 30.0, 340.0) for index in range(5)])
    for values in segment_y_bounds(path):
        assert all(abs(value - 340.0) < 1e-9 for value in values), path


def test_y_ticks_small_peak_returns_unit_steps_expected() -> None:
    assert y_ticks(3) == [0, 1, 2, 3]


def test_y_ticks_large_peak_covers_peak_with_five_ticks_expected() -> None:
    for peak in (5, 17, 64, 101, 999, 4321):
        ticks = y_ticks(peak)
        assert ticks[0] == 0 and ticks[-1] >= peak, (peak, ticks)
        assert len(ticks) <= 5, (peak, ticks)


def test_render_emits_parsable_svg_with_expected_size_expected() -> None:
    start = date(2026, 1, 1)
    days = [(start + timedelta(days=offset), offset % 7) for offset in range(31)]
    root = ElementTree.fromstring(render(days, "Contribution Graph"))
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("width") == "840" and root.get("height") == "400"


def test_render_all_zero_days_does_not_divide_by_zero_expected() -> None:
    start = date(2026, 1, 1)
    ElementTree.fromstring(render([(start + timedelta(days=n), 0) for n in range(31)], "T"))


if __name__ == "__main__":
    failures = 0
    for name, test in sorted(vars().copy().items()):
        if not name.startswith("test_"):
            continue
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL {name}: {error}")
        else:
            print(f"ok   {name}")
    sys.exit(1 if failures else 0)
