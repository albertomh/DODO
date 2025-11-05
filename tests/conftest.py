"""See <https://pytest.org/en/latest/example/simple.html#excontrolskip>"""

import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    is_ci = os.getenv("GITHUB_ACTIONS") == "true"
    if is_ci or config.getoption("--runslow"):
        return  # do not skip slow tests

    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture
def droplet_response():
    return {
        "networks": {
            "v4": [{"type": "public", "ip_address": "1.2.3.4"}],
            "v6": [{"type": "private", "ip_address": "fd00::1"}],
        }
    }
