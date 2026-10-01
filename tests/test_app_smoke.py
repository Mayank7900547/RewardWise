"""Smoke tests: every page renders without raising, using Streamlit's headless AppTest."""
import pytest
from streamlit.testing.v1 import AppTest

from conftest import ROOT

PAGES = ["Dashboard", "Credit card portfolio", "Expenses", "Card comparison", "Monthly allocation"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception, [e.value for e in at.exception]


def test_dashboard_shows_recommended_reward_metric():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    labels = [m.label for m in at.metric]
    assert "Final Score with recommended plan" in labels
