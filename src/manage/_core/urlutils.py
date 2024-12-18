import os
import time

from pathlib import Path, PurePath

from .logging import LOGGER
from .fsutils import ensure_tree, unlink

try:
    from . import file_url_to_path
except ImportError:
    from nturl2path import url2pathname as file_url_to_path


ENABLE_BITS = os.getenv("PYTHON_DISABLE_BITS", "0").lower()[:1] not in "1yt"
ENABLE_WINHTTP = os.getenv("PYTHON_DISABLE_WINHTTP", "0").lower()[:1] not in "1yt"


try:
    from . import (coinitialize, bits_connect, bits_begin, bits_cancel,
        bits_get_progress, bits_find_job, bits_serialize_job)
except ImportError:
    pass
else:
    def _bits_urlretrieve(url, outfile, on_progress, on_auth_request):
        LOGGER.debug("_bits_urlretrieve: %s", sanitise_url(url))
        coinitialize()
        bits = bits_connect()

        job = None
        jobfile = outfile.with_suffix(".job")
        last_progress = None
        try:
            job_id = jobfile.read_bytes()
        except OSError:
            job_id = None
        else:
            LOGGER.debug("Recovering job %s from %s", job_id, jobfile)

        try:
            if job_id:
                try:
                    job = bits_find_job(bits, job_id)
                except OSError as ex:
                    LOGGER.debug("Failed to recover job due to %s", ex)
                    job = None
                else:
                    last_progress = bits_get_progress(bits, job)
            if not job:
                LOGGER.debug("Starting new BITS job: %s -> %s", sanitise_url(url), outfile)
                ensure_tree(outfile)
                if on_auth_request:
                    user, passw = on_auth_request(url)
                else:
                    user, passw = None, None
                job = bits_begin(bits, PurePath(outfile).name, url, outfile, user, passw)
                LOGGER.debug("Writing %s", jobfile)
                jobfile.write_bytes(bits_serialize_job(bits, job))

            LOGGER.debug("Downloading %s", sanitise_url(url))
            last_progress = -1
            while last_progress < 100:
                progress = bits_get_progress(bits, job)
                if on_progress and progress > last_progress:
                    on_progress(progress)
                last_progress = progress
                time.sleep(0.1)
        except OSError:
            if job:
                bits_cancel(bits, job)
            if jobfile.is_file():
                unlink(jobfile)
            raise
        unlink(jobfile)


try:
    from . import winhttp_urlopen
except ImportError:
    pass
else:
    def _winhttp_urlopen(url, method, headers, on_progress, on_auth_request):
        headers = {k.lower(): v for k, v in headers.items()}
        accepts = headers.pop("accepts", "application/*;text/*")
        header_str = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
        method = method.upper()
        LOGGER.debug("winhttp_urlopen: %s %s", method, sanitise_url(url))
        data = winhttp_urlopen(url, method, header_str, accepts, on_progress, on_auth_request)
        if data[:3] == b"\xEF\xBB\xBF":
            data = data[3:]
        return data

    def _winhttp_urlretrieve(
        url,
        outfile,
        method,
        headers={},
        chunksize=...,
        on_progress=None,
        on_auth_request=None,
    ):
        Path(outfile).write_bytes(_winhttp_urlopen(url, method, headers, on_progress, on_auth_request))


def _basic_auth_header(username, password):
    from base64 import b64encode
    pair = f"{username}:{password}".encode("utf-8")
    token = b64encode(pair)
    return "Basic " + token.decode("ascii")


def _urllib_urlopen(url, method, headers, on_progress, on_auth_request):
    try:
        import urllib.error
        from urllib.request import Request, urlopen
    except ImportError as ex:
        raise RuntimeError("Unable to download from the internet") from ex

    if not on_progress:
        on_progress = lambda *_: None

    LOGGER.debug("urlopen: %s %s", method, sanitise_url(url))
    req = Request(url, method=method, headers=headers)
    try:
        on_progress(0)
        try:
            r = urlopen(req)
        except urllib.error.HTTPError as ex:
            if ex.status == 401 and on_auth_request:
                req.headers["Authorization"] = _basic_auth_header(*on_auth_request(url))
                r = urlopen(req)
            else:
                raise
        with r:
            data = r.read()
        on_progress(100)
        return data
    finally:
        LOGGER.debug("urlopen: complete")


def urlopen(url, method="GET", headers={}, on_progress=None, on_auth_request=None):
    if url.casefold().startswith("file://".casefold()):
        with open(file_url_to_path(url), "rb") as f:
            return f.read()

    if ENABLE_WINHTTP:
        try:
            _winhttp_urlopen
        except NameError:
            LOGGER.debug("WinHTTP download unavailable - using fallback")
        else:
            return _winhttp_urlopen(url, method, headers, on_progress, on_auth_request)

    return _urllib_urlopen(url, method, headers, on_progress, on_auth_request)


def _urllib_urlretrieve(url, outfile, method, headers, chunksize, on_progress=None, on_auth_request=None):
    try:
        import urllib.error
        from urllib.request import Request, urlopen
    except ImportError as ex:
        raise RuntimeError("Unable to download from the internet") from ex

    if not on_progress:
        on_progress = lambda *_: None

    outfile = Path(outfile)
    LOGGER.debug("urlretrieve: %s %s -> %s", method, sanitise_url(url), outfile)
    ensure_tree(outfile)
    unlink(outfile)
    req = Request(url, method=method, headers=headers)
    try:
        on_progress(0)
        try:
            r = urlopen(req)
        except urllib.error.HTTPError as ex:
            if ex.status == 401 and on_auth_request:
                req.auth = on_auth_request(url)
                r = urlopen(req)
            else:
                raise
        with r:
            progress = 0
            try:
                total = int(r.headers.get("Content-Length", 0))
            except ValueError:
                total = 0
            with open(outfile, "wb") as f:
                for chunk in iter(lambda: r.read(chunksize), b""):
                    f.write(chunk)
                    progress += len(chunk)
                    on_progress((progress * 100) // total)
        on_progress(100)
    finally:
        LOGGER.debug("urlretrieve: complete")


def urlretrieve(url, outfile, method="GET", headers={}, chunksize=32 * 1024, on_progress=None, on_auth_request=None):
    if url.casefold().startswith("file://".casefold()):
        with open(file_url_to_path(url), "rb") as r:
            with open(outfile, "wb") as f:
                for chunk in iter(lambda: r.read(chunksize), b""):
                    f.write(chunk)
        return

    if ENABLE_BITS:
        try:
            _bits_urlretrieve
        except NameError:
            LOGGER.debug("BITS download unavailable - using fallback")
        else:
            if method.casefold() == "GET".casefold():
                return _bits_urlretrieve(url, outfile, on_progress=on_progress, on_auth_request=on_auth_request)

    if ENABLE_WINHTTP:
        try:
            _winhttp_urlretrieve
        except NameError:
            LOGGER.debug("WinHTTP download unavailable - using fallback")
        else:
            return _winhttp_urlretrieve(url, outfile, method, headers, chunksize, on_progress, on_auth_request)

    return _urllib_urlretrieve(url, outfile, method, headers, chunksize, on_progress, on_auth_request)


def sanitise_url(url):
    from urllib.parse import urlparse, urlunparse
    p = urlparse(url)
    userpass, _, netloc = p[1].rpartition("@")
    if userpass:
        user, _, passw = userpass.partition(":")
        # URLs like https://__token__:%TOKEN%@netloc/ are permitted
        if passw and passw.startswith("%") and passw.endswith("%"):
            return url
    return urlunparse((*p[:1], netloc, *p[2:]))


def urljoin(base_url, other_url, *, to_parent=False):
    from pathlib import PurePosixPath
    from urllib.parse import urlparse, urlunparse
    u1, u2 = urlparse(base_url), urlparse(other_url)
    if u2.scheme and u2.netloc:
        return other_url
    p1 = PurePosixPath(u1[2])
    if to_parent and u2[2]:
        p1 = p1.parent
    return urlunparse((
        u2[0] or u1[0],
        u2[1] or u1[1],
        str(p1 / u2[2]),
        *u1[3:]
    ))
