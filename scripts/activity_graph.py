"""Render a contribution activity graph as a self-hosted SVG card."""

from datetime import date, timedelta
from pathlib import Path
import json
import os
import sys
import urllib.request

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

WIDTH = 840
HEIGHT = 400
PAD_LEFT = 62
PAD_RIGHT = 28
PAD_TOP = 74
PAD_BOTTOM = 52

BG = "#0f172a"
TITLE = "#67e8f9"
AXIS = "#94a3b8"
LINE = "#2dd4bf"
POINT = "#f59e0b"
GRID = "#1e293b"


def fetch_days(login: str, token: str, days: int) -> list[tuple[date, int]]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    payload = json.dumps(
        {
            "query": QUERY,
            "variables": {
                "login": login,
                "from": f"{start.isoformat()}T00:00:00Z",
                "to": f"{end.isoformat()}T23:59:59Z",
            },
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "coseto6125-profile-activity-graph",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)

    if "errors" in body:
        raise RuntimeError(f"GitHub GraphQL error: {body['errors']}")

    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {
        day["date"]: day["contributionCount"] for week in weeks for day in week["contributionDays"]
    }
    return [
        (start + timedelta(days=offset), counts.get((start + timedelta(days=offset)).isoformat(), 0))
        for offset in range(days)
    ]


def y_ticks(peak: int) -> list[int]:
    """Pick at most five round tick values that cover the peak."""
    if peak <= 4:
        return list(range(peak + 1))
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if peak / step <= 4:
            top = -(-peak // step) * step
            return list(range(0, top + step, step))
    step = -(-peak // 4)
    return [step * index for index in range(5)]


def curve(points: list[tuple[float, float]]) -> str:
    """Monotone cubic Hermite through every point, so the line never dips below zero."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    last = len(points) - 1

    slopes = [(ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) for i in range(last)]
    tangents = [slopes[0]]
    tangents += [
        0.0 if slopes[i - 1] * slopes[i] <= 0 else (slopes[i - 1] + slopes[i]) / 2
        for i in range(1, last)
    ]
    tangents.append(slopes[-1])

    for i in range(last):
        if slopes[i] == 0:
            tangents[i] = tangents[i + 1] = 0.0
            continue
        alpha = tangents[i] / slopes[i]
        beta = tangents[i + 1] / slopes[i]
        norm = alpha * alpha + beta * beta
        if norm > 9:
            scale = 3 / norm**0.5
            tangents[i] = scale * alpha * slopes[i]
            tangents[i + 1] = scale * beta * slopes[i]

    path = [f"M {xs[0]:.2f} {ys[0]:.2f}"]
    for i in range(last):
        third = (xs[i + 1] - xs[i]) / 3
        path.append(
            f"C {xs[i] + third:.2f} {ys[i] + tangents[i] * third:.2f}, "
            f"{xs[i + 1] - third:.2f} {ys[i + 1] - tangents[i + 1] * third:.2f}, "
            f"{xs[i + 1]:.2f} {ys[i + 1]:.2f}"
        )
    return " ".join(path)


def render(days: list[tuple[date, int]], title: str) -> str:
    plot_width = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_height = HEIGHT - PAD_TOP - PAD_BOTTOM
    base_y = PAD_TOP + plot_height

    ticks = y_ticks(max(count for _, count in days))
    scale_top = ticks[-1] or 1
    step_x = plot_width / (len(days) - 1)

    def to_y(count: int) -> float:
        return base_y - plot_height * count / scale_top

    points = [(PAD_LEFT + index * step_x, to_y(count)) for index, (_, count) in enumerate(days)]
    line_path = curve(points)
    area_path = f"{line_path} L {points[-1][0]:.2f} {base_y} L {points[0][0]:.2f} {base_y} Z"

    total = sum(count for _, count in days)
    subtitle = (
        f"{total} contributions · {days[0][0].strftime('%d %b %Y')} – "
        f"{days[-1][0].strftime('%d %b %Y')}"
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{title}: {subtitle}">',
        "  <defs>",
        f'    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0%" stop-color="{LINE}" stop-opacity="0.36" />',
        f'      <stop offset="100%" stop-color="{LINE}" stop-opacity="0.02" />',
        "    </linearGradient>",
        "  </defs>",
        f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="6" fill="{BG}" />',
        f'  <text x="{PAD_LEFT}" y="38" fill="{TITLE}" font-family="Segoe UI, Ubuntu, sans-serif" '
        f'font-size="20" font-weight="600">{title}</text>',
        f'  <text x="{PAD_LEFT}" y="58" fill="{AXIS}" font-family="Segoe UI, Ubuntu, sans-serif" '
        f'font-size="12">{subtitle}</text>',
    ]

    for tick in ticks:
        y = to_y(tick)
        parts.append(
            f'  <line x1="{PAD_LEFT}" y1="{y:.2f}" x2="{WIDTH - PAD_RIGHT}" y2="{y:.2f}" '
            f'stroke="{GRID}" stroke-width="1" />'
        )
        parts.append(
            f'  <text x="{PAD_LEFT - 12}" y="{y + 4:.2f}" fill="{AXIS}" '
            f'font-family="Segoe UI, Ubuntu, sans-serif" font-size="11" '
            f'text-anchor="end">{tick}</text>'
        )

    parts.append(f'  <path d="{area_path}" fill="url(#area)" />')
    parts.append(
        f'  <path d="{line_path}" fill="none" stroke="{LINE}" stroke-width="2.4" '
        'stroke-linecap="round" stroke-linejoin="round" />'
    )

    label_every = max(1, round(len(days) / 8))
    for index, (day, count) in enumerate(days):
        x, y = points[index]
        parts.append(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="2.6" fill="{POINT}" />')
        if index % label_every == 0 or index == len(days) - 1:
            parts.append(
                f'  <text x="{x:.2f}" y="{base_y + 24:.2f}" fill="{AXIS}" '
                f'font-family="Segoe UI, Ubuntu, sans-serif" font-size="11" '
                f'text-anchor="middle">{day.strftime("%d %b")}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: activity_graph.py <login> <svg-path>")

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")

    days = fetch_days(sys.argv[1], token, days=31)
    Path(sys.argv[2]).write_text(render(days, "Contribution Graph"), encoding="utf-8")


if __name__ == "__main__":
    main()
