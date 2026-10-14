from streamlit.testing.v1 import AppTest
from tests.conftest import ROOT


def test_dashboard_renders_without_api():
    app = AppTest.from_file(str(ROOT / "dashboard/dashboard.py"), default_timeout=30).run()
    assert not app.exception
    labels = app.selectbox[1].options
    assert "Webcam + EMG replay (no sensor)" in labels
    assert any("Cannot reach API" in e.value for e in app.error)
