"""mabat-ui: the dashboard script runs headlessly and renders every chosen section."""

from __future__ import annotations

import pytest

st = pytest.importorskip("streamlit")
from mabat_ui import APP_PATH, __version__  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

import mabat  # noqa: E402


def _run(timeout: float = 60) -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=timeout)
    # the script ends with sleep + rerun; AppTest runs one pass and stops at rerun
    app.run()
    return app


def test_dashboard_renders_headline_and_sections() -> None:
    app = _run()
    assert not app.exception, app.exception
    assert app.title[0].value.startswith("mabat")
    labels = [m.label for m in app.metric]
    assert "CPU" in labels and "RAM" in labels
    expanders = [e.label for e in app.expander]
    assert {"cpu", "memory", "gpu", "network"} <= set(expanders)


def test_sidebar_controls_exist() -> None:
    app = _run()
    assert app.sidebar.slider[0].label.startswith("refresh")
    assert [c.label for c in app.sidebar.checkbox][-1].startswith("redact")
    assert __version__


def test_unavailable_sections_show_their_reason() -> None:
    app = _run()
    # sensors is unavailable on Windows without LibreHardwareMonitor and inside CI runners
    app.sidebar.multiselect[0].set_value(["sensors"]).run()
    assert not app.exception
    sensors = mabat.sensors()
    if not sensors.available:
        assert app.warning and sensors.problems[0].detail.split(".")[0] in app.warning[0].value
