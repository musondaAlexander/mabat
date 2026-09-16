"""Time every section (cold, then warm) and the whole snapshot against a latency budget.

    python scripts/bench.py            # table; exit 1 if a warm reading exceeds its budget
    python scripts/bench.py --json     # machine-readable

Budgets are generous on purpose: they catch regressions (a collector that suddenly
spawns a process per call), not slow hardware. Per-process scans on hosts with
security software hooking handle access can legitimately take seconds.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from typing import Any

import mabat

# warm-call budget in seconds; cold calls pay one-off costs (py-cpuinfo, WMI) and are
# reported but not judged
BUDGETS: dict[str, float] = {
    "cpu": 1.5,
    "memory": 0.2,
    "system": 10.0,
    "storage": 3.0,
    "gpu": 1.5,
    "sensors": 3.0,
    "network": 1.0,
    "snapshot": 20.0,
}


def _time(call: Callable[[], object]) -> float:
    started = time.perf_counter()
    call()
    return time.perf_counter() - started


def main(argv: list[str]) -> int:
    targets: dict[str, Callable[[], object]] = dict(mabat.collectors())
    targets["snapshot"] = mabat.snapshot
    rows: list[dict[str, Any]] = []
    for name, collect in targets.items():
        cold = _time(collect)
        warm = _time(collect)
        budget = BUDGETS.get(name, 5.0)
        rows.append(
            {
                "section": name,
                "cold_s": round(cold, 3),
                "warm_s": round(warm, 3),
                "budget_s": budget,
                "ok": warm <= budget,
            }
        )

    if "--json" in argv:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{'section':<10}{'cold':>8}{'warm':>8}{'budget':>8}  status")
        for row in rows:
            status = "ok" if row["ok"] else "OVER BUDGET"
            print(
                f"{row['section']:<10}{row['cold_s']:>8.2f}{row['warm_s']:>8.2f}"
                f"{row['budget_s']:>8.1f}  {status}"
            )
    over = [row["section"] for row in rows if not row["ok"]]
    if over:
        print(f"\nover budget: {', '.join(over)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
