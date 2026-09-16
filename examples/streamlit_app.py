"""A live dashboard for mabat with Streamlit.

    pip install streamlit pandas
    streamlit run examples/streamlit_app.py

The page calls the same collectors the CLI does, shows headline metrics, then one
expander per section with the flattened reading as a key/value table. Sections that
cannot answer on this host show their reason instead of an empty panel.
"""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

import mabat

st.set_page_config(page_title="mabat", layout="wide")

health = mabat.health()
st.title(f"mabat - {health.platform_release}")
if not health.ok:
    missing = ", ".join(p.name for p in health.providers if p.required and not p.available)
    st.error(f"core providers missing: {missing}")

refresh = st.sidebar.slider("refresh every (s)", min_value=1, max_value=30, value=5)
chosen = st.sidebar.multiselect(
    "sections", list(mabat.section_names()), default=["cpu", "memory", "gpu", "network"]
)
st.sidebar.caption("The system section scans every process; on some hosts that takes seconds.")

snap = mabat.snapshot(only=chosen)

# --- headline metrics --------------------------------------------------------------------
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

# --- one panel per section -----------------------------------------------------------------
for name, section in mabat.sections_of(snap).items():
    if name not in chosen:
        continue
    with st.expander(name, expanded=True):
        if not section.available:
            reason = section.problems[0].detail if section.problems else "no data"
            st.warning(reason)
            continue
        flat = mabat.flatten(section.data)
        table = pd.DataFrame({"value": list(flat.values())}, index=list(flat.keys()))
        st.dataframe(table, use_container_width=True)
        for problem in section.problems:
            st.caption(f"{problem.source} [{problem.kind.value}]: {problem.detail}")

st.caption(f"collected {snap.collected_at.astimezone():%H:%M:%S}")
time.sleep(refresh)
st.rerun()
