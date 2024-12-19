import pytest
import shutil

from copy import copy

from manage._core.fsutils import ensure_tree, rmtree, unlink

@pytest.fixture
def tree(tmp_path):
    a = tmp_path / "a"
    b = a / "b"
    c = a / "c"
    d = c / "d"
    a.mkdir()
    b.write_bytes(b"")
    c.mkdir()
    d.write_bytes(b"")
    try:
        yield a
    finally:
        if a.is_dir():
            shutil.rmtree(a)


def test_ensure_tree(tree):
    p = tree / "e" / "f"
    ensure_tree(p)
    assert (tree / "e").is_dir()
    assert not p.exists()
    ensure_tree(p)

    p2 = p / "g"
    ensure_tree(p2)
    assert p.is_dir()


def test_unlink_success(tree):
    unlink(tree / "b")
    assert not (tree / "b").exists()


def test_unlink_with_rename(tree, monkeypatch):
    b = tree / "b"
    orig_unlink = b.unlink
    def dont_unlink(p):
        if p.name == "b":
            raise PermissionError()
        orig_unlink(p)
    monkeypatch.setattr(type(b), "unlink", dont_unlink)

    unlink(b)
    assert not b.exists()


def test_rmtree(tree):
    rmtree(tree)
    assert not tree.exists()
