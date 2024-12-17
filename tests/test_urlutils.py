import manage._core.urlutils as UU
import pytest


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
