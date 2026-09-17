"""The mabat dashboard. Run with ``mabat-ui`` or ``streamlit run app.py``.

Headline metrics, then one expander per section with the flattened reading as a
key/value table. Sections that cannot answer on this host show their reason instead of
an empty panel. Everything comes from the same collectors the CLI uses. The body is a
fragment that re-runs on the chosen interval, so nothing sleeps and the sidebar stays
responsive.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

import mabat

st.set_page_config(page_title="mabat", layout="wide")

health = mabat.health()
st.title(f"mabat - {health.platform_release}")
if not health.ok:
    missing = ", ".join(p.name for p in health.providers if p.required and not p.available)
    st.error(f"core providers missing: {missing}")

with st.sidebar:
    st.header("mabat")
    refresh = st.slider("refresh every (s)", min_value=1, max_value=60, value=5)
    chosen = st.multiselect(
        "sections", list(mabat.section_names()), default=["cpu", "memory", "gpu", "network"]
    )
    top_n = st.number_input("processes to rank (0 = count only)", min_value=0, value=0)
    counters = st.checkbox("GPU performance counters (Windows, ~5 s)", value=False)
    redact = st.checkbox("redact identity (hostname, users, addresses)", value=False)
    st.caption("The system section scans every process; on some hosts that takes seconds.")

options: dict[str, Any] = {"top_n": int(top_n), "sample_seconds": 0}
if counters:
    options["counters"] = True


@st.fragment(run_every=timedelta(seconds=int(refresh)))
def dashboard() -> None:
    snap = mabat.snapshot(only=chosen, **options)
    if redact:
        snap = mabat.redact(snap)

    # --- headline metrics -----------------------------------------------------------------
    cols = st.columns(4)
    if snap.cpu.data and snap.cpu.data.usage:
        cols[0].metric("CPU", f"{snap.cpu.data.usage.percent:.0f} %")
    if snap.memory.data and snap.memory.data.virtual:
        cols[1].metric("RAM", f"{snap.memory.data.virtual.percent:.0f} %")
    gpu = snap.gpu.data.devices[0] if snap.gpu.data and snap.gpu.data.devices else None
    if gpu and gpu.telemetry and gpu.telemetry.utilization_percent is not None:
        cols[2].metric("GPU", f"{gpu.telemetry.utilization_percent:.0f} %")
    if snap.network.data and snap.network.data.total_rates:
        down = snap.network.data.total_rates.recv_bytes_per_s / 1024
        cols[3].metric("down", f"{down:.0f} KiB/s")

    # --- one panel per section --------------------------------------------------------------
    for name, section in mabat.sections_of(snap).items():
        if name not in chosen:
            continue
        with st.expander(name, expanded=True):
            if not section.available:
                reason = section.problems[0].detail if section.problems else "no data"
                st.warning(reason)
                continue
            flat = mabat.flatten(section.data)
            table = pd.DataFrame(
                {"value": [str(v) for v in flat.values()]}, index=list(flat.keys())
            )
            st.dataframe(table, use_container_width=True)
            for problem in section.problems:
                st.caption(f"{problem.source} [{problem.kind.value}]: {problem.detail}")

    st.caption(f"collected {snap.collected_at.astimezone():%H:%M:%S} - every {refresh} s")


dashboard()
