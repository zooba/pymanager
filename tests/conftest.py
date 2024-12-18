import logging
import os
import pytest
import random
import re
import subprocess
import sys

from pathlib import Path

TESTS = Path(__file__).absolute().parent

import manage._core
if not hasattr(manage._core, "coinitialize"):
    import _core_test
    for k in dir(_core_test):
        if k[:1] not in ("", "_"):
            setattr(manage._core, k, getattr(_core_test, k))


class LogCaptureHandler:
    def __init__(self):
        self.records = []
        self.level = logging.DEBUG

    def handle(self, record):
        self.records.append((record.module, record.msg, record.args))

    def __call__(self, *cmp):
        for x, y in zip(self.records, cmp):
            assert x[0] == y[0]
            assert re.match(y[1], x[1])
            assert x[2] == y[2]

@pytest.fixture
def assert_log():
    logger = logging.getLogger("pymanager")
    capture = LogCaptureHandler()
    logger.addHandler(capture)
    logger.setLevel(logging.DEBUG)
    yield capture


@pytest.fixture(scope="session")
def localserver():
    from urllib.request import urlopen
    from urllib.error import URLError
    port = random.randrange(10000, 20000)
    with subprocess.Popen([sys.executable, TESTS / "localserver.py", str(port)]) as p:
        try:
            p.wait(0.1)
        except subprocess.TimeoutExpired:
            pass
        else:
            raise RuntimeError("failed to launch local server")
        host = f"http://localhost:{port}"
        with urlopen(host + "/alive"): pass
        try:
            yield host
        finally:
            try:
                p.wait(0.1)
            except subprocess.TimeoutExpired:
                try:
                    with urlopen(host + "/stop"): pass
                except URLError:
                    p.kill()
                p.wait(5)


class FakeConfig:
    def __init__(self, installs=[]):
        self.installs = list(installs)

    def get_installs(self):
        return self.installs


@pytest.fixture
def fake_config():
    return FakeConfig()
