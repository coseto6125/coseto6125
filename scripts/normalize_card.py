from pathlib import Path
import re
import sys


def normalize_card(path: str, width: int = 420, height: int = 195, y_offset: int = 15) -> None:
    target = Path(path)
    svg = target.read_text(encoding="utf-8")

    svg, width_count = re.subn(
        r'(\n\s*width=")\d+("\s*\n)',
        rf'\g<1>{width}\2',
        svg,
        count=1,
    )
    svg, height_count = re.subn(
        r'(\n\s*height=")\d+("\s*\n)',
        rf'\g<1>{height}\2',
        svg,
        count=1,
    )
    svg, viewbox_count = re.subn(
        r'(viewBox="0 0 )\d+ \d+("\s*\n)',
        rf'\g<1>{width} {height}\2',
        svg,
        count=1,
    )

    if not (width_count and height_count and viewbox_count):
        raise RuntimeError("Could not identify the outer SVG dimensions")

    background_match = re.search(
        r'<rect\s+data-testid="card-bg".*?/\s*>',
        svg,
        flags=re.DOTALL,
    )
    outer_end = svg.rfind("</svg>")
    if background_match is None or outer_end == -1 or background_match.end() > outer_end:
        raise RuntimeError("Could not identify SVG background or outer closing tag")

    insert_at = background_match.end()
    svg = (
        svg[:insert_at]
        + f'\n      <g transform="translate(0,{y_offset})">'
        + svg[insert_at:outer_end]
        + "\n      </g>"
        + svg[outer_end:]
    )
    target.write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: normalize_card.py <svg-path>")
    normalize_card(sys.argv[1])
