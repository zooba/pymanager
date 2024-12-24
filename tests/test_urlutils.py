import time

import pytest

import _native
import manage.urlutils as UU


@pytest.mark.parametrize("url, expect", [pytest.param(*i, id=i[0]) for i in [
    ("https://example.com/", "https://example.com/"),
    ("https://user@example.com/", "https://example.com/"),
    ("https://user:placeholder@example.com/", "https://example.com/"),
]])
def test_urlsanitise(url, expect):
    assert expect == UU.sanitise_url(url)


@pytest.mark.parametrize("url1, url2, to_parent, expect",
    [pytest.param(*i, id=f'{i[1]}-{i[2]}') for i in [
        ("https://example.com/A/B/C", "D", False, "https://example.com/A/B/C/D"),
        ("https://example.com/A/B/C", "D", True, "https://example.com/A/B/D"),
        ("https://example.com/A/B/C", "/D", None, "https://example.com/D"),
        ("https://example.com/A/B/C", "//D", None, "https://D/A/B/C"),
        ("https://example.com/A/B/C", "http:", None, "http://example.com/A/B/C"),
        ("https://example.com/A/B/C", "//EXAMPLE.COM", None, "https://EXAMPLE.COM/A/B/C"),
        ("https://example.com/A/B/C", "//EXAMPLE.COM/A", True, "https://EXAMPLE.COM/A"),
        ("https://example.com/A/B/C", "//EXAMPLE.COM/", None, "https://EXAMPLE.COM/"),
    ]
])
def test_urljoin(url1, url2, to_parent, expect):
    if to_parent != True:
        assert expect == UU.urljoin(url1, url2, to_parent=False)
    if to_parent != False:
        assert expect == UU.urljoin(url1, url2, to_parent=True)


def test_urllib_urlretrieve(localserver, tmp_path):
    dest = tmp_path / "read.txt"
    progress = []
    UU._urllib_urlretrieve(localserver + "/128kb", dest, "GET", {}, 1024, progress.append, None)
    assert dest.is_file()
    assert progress[:1] + progress[-1:] == [0, 100]
    assert sorted(progress) == progress


def test_urllib_urlopen(localserver):
    progress = []
    data = UU._urllib_urlopen(localserver + "/1kb", "GET", {}, progress.append, None)
    assert data
    assert progress[:1] + progress[-1:] == [0, 100]
    assert sorted(progress) == progress


def test_urllib_auth(localserver):
    import base64
    with pytest.raises(Exception) as ex:
        data = UU._urllib_urlopen(localserver + "/withauth", "GET", {}, None, None)
    assert "401" in str(ex)

    auth_header = {"Authorization": "Basic " + base64.b64encode("in header".encode()).decode()}
    data = UU._urllib_urlopen(localserver + "/withauth", "GET", auth_header, None, None)
    assert data == b"Basic in header"

    auth_callback =  lambda u: ("on", "demand")
    data = UU._urllib_urlopen(localserver + "/withauth", "GET", {}, None, auth_callback)
    assert data == b"Basic on:demand"


def test_winhttp_urlretrieve(localserver, tmp_path):
    dest = tmp_path / "read.txt"
    progress = []
    UU._winhttp_urlretrieve(localserver + "/128kb", dest, "GET", {}, 1024, progress.append, None)
    assert dest.is_file()
    # progress is _probably_ [0, 100, 100]
    assert progress[:1] + progress[-1:] == [0, 100]
    assert progress != [0, 100]
    assert sorted(progress) == progress


def test_winhttp_urlopen(localserver):
    progress = []
    data = UU._winhttp_urlopen(localserver + "/1kb", "GET", {}, progress.append, None)
    assert data
    # progress is _probably_ [0, 100, 100]
    assert progress[:1] + progress[-1:] == [0, 100]
    assert progress != [0, 100]
    assert sorted(progress) == progress


def test_winhttp_https(localserver):
    data = UU._winhttp_urlopen("https://example.com", "GET", {}, None, None)
    assert data


def test_winhttp_auth(localserver):
    import base64
    with pytest.raises(Exception) as ex:
        data = UU._winhttp_urlopen(localserver + "/withauth", "GET", {}, None, None)
    assert "401" in str(ex)

    auth_header = {"Authorization": "Basic " + base64.b64encode("in header".encode()).decode()}
    data = UU._winhttp_urlopen(localserver + "/withauth", "GET", auth_header, None, None)
    assert data == b"Basic in header"

    creds = {
        localserver + "/withauth": ("placeholder", "placeholder"),
    }
    data = UU._winhttp_urlopen(localserver + "/withauth", "GET", {}, None, creds.__getitem__)
    assert data == b"Basic placeholder:placeholder"



def test_bits_urlretrieve(localserver, tmp_path):
    dest = tmp_path / "read.txt"
    progress = []
    UU._bits_urlretrieve(localserver + "/128kb", dest, progress.append, None)
    assert dest.is_file()
    assert progress[:1] + progress[-1:] == [0, 100]
    assert progress != [0, 100]
    assert sorted(progress) == progress


def test_bits_urlretrieve_auth(localserver, tmp_path):
    dest = tmp_path / "read.txt"
    creds = {
        localserver + "/withauth": ("placeholder", "placeholder"),
    }
    UU._bits_urlretrieve(localserver + "/withauth", dest, None, creds.__getitem__)
    assert dest.is_file()
    assert dest.read_bytes() == b"Basic placeholder:placeholder"


@pytest.fixture
def inject_error():
    try:
        yield _native.bits_inject_error
    finally:
        _native.bits_inject_error(0, 0, 0, 0)


def test_bits_errors(localserver, tmp_path, inject_error):
    import uuid

    ERROR_MR_MID_NOT_FOUND = 0x8007013D

    dest = tmp_path / "read.txt"
    url = localserver + "/128kb"
    conn = _native.bits_connect()

    # Should get our error code, chained to "message not found" error
    inject_error(0xA0000001, 0, 0, 0)
    with pytest.raises(OSError) as ex:
        _native.bits_find_job(conn, uuid.UUID(int=0).bytes_le)
    assert "Retrieving error message" in str(ex.value)
    assert ex.value.winerror & 0xFFFFFFFF == ERROR_MR_MID_NOT_FOUND
    assert isinstance(ex.value.__context__, OSError)
    assert ex.value.__context__.winerror & 0xFFFFFFFF == 0xA0000001

    # Should get our error code, chained to our second error code
    inject_error(0xA0000001, 0, 0xA0000002, 0)
    with pytest.raises(OSError) as ex:
        _native.bits_find_job(conn, uuid.UUID(int=0).bytes_le)
    assert ex.value.winerror & 0xFFFFFFFF == 0xA0000002
    assert "Retrieving error message" in str(ex.value)
    assert isinstance(ex.value.__context__, OSError)
    assert ex.value.__context__.winerror & 0xFFFFFFFF == 0xA0000001

    # Inject errors into get_progress.
    # (No errors while we get started)
    inject_error(0, 0, 0, 0)
    job = _native.bits_begin(conn, "PyManager Test", url, dest)
    try:
        progress = _native.bits_get_progress(conn, job)

        # This will be treated as the reason we couldn't read the error code
        inject_error(1, 0xA0000001, 0, 0)
        with pytest.raises(OSError) as ex:
            _native.bits_get_progress(conn, job)
        # Original error is unspecified OSError
        assert ex.value.__context__.winerror == None
        # The cause is our error
        assert ex.value.winerror & 0xFFFFFFFF == 0xA0000001
    finally:
        _native.bits_cancel(conn, job)

    # Inject errors into get_progress.
    # (No errors while we get started)
    inject_error(0, 0, 0, 0)
    job = _native.bits_begin(conn, "PyManager Test", localserver + "/always404", dest)
    try:
        # This will be treated as the reason we couldn't get text for the error
        # code.
        inject_error(0, 0, 0xA0000002, 0)
        with pytest.raises(OSError) as ex:
            for _ in range(100):
                _native.bits_get_progress(conn, job)
                time.sleep(0.1)
        # HACK: We are overriding errors right now. Commented code is "ideal"
        ## Original error is the 404
        #assert "404" in str(ex.value.__context__)
        #assert ex.value.__context__.winerror & 0xFFFFFFFF == 0x80190194
        ## The cause is our error
        #assert ex.value.winerror & 0xFFFFFFFF == 0xA0000002
        assert "404" in str(ex.value)
        assert ex.value.winerror & 0xFFFFFFFF == 0x80190194
    finally:
        _native.bits_cancel(conn, job)


    # Inject an error when adding credentials
    inject_error(0, 0, 0, 0xA0000001)
    # No credentials specified, so does not raise
    try:
        job = _native.bits_begin(conn, "PyManager Test", url, dest)
    finally:
        _native.bits_cancel(conn, job)
    # Add credentials to cause injected error
    with pytest.raises(OSError) as ex:
        job = _native.bits_begin(conn, "PyManager Test", url, dest, "x", "y")
    # Original error is ours
    assert ex.value.__context__.winerror & 0xFFFFFFFF == 0xA0000001
    # The final error is the missing message
    assert ex.value.winerror & 0xFFFFFFFF == ERROR_MR_MID_NOT_FOUND

