"""uv run matrix simulate --days N --seconds S --brain reduced|full [--control Fil]"""

from __future__ import annotations

import json
from pathlib import Path

from world.simulation import Day


def main(args) -> int:
    root = Path(args.out)
    root.mkdir(parents=True, exist_ok=True)
    summary = []
    for d in range(args.start, args.start + args.days):
        out = root / f"day_{d:04d}"
        day = Day(args.seconds, brain_mode=args.brain, out_dir=out, control_fly=args.control, day_index=d)
        day.run()
        summary.append({"day": d, "dir": str(out), **day.stats.get("_dia", {})})
        (root / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0
