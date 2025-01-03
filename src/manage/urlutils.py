import os
import time

from pathlib import Path, PurePath

from .logging import LOGGER
from .fsutils import ensure_tree, rmtree, unlink

try:
    from _native import file_url_to_path
except ImportError:
    from nturl2path import url2pathname as file_url_to_path


ENABLE_BITS = os.getenv("PYMANAGER_ENABLE_BITS_DOWNLOAD", "1").lower()[:1] in "1yt"
ENABLE_WINHTTP = os.getenv("PYMANAGER_ENABLE_WINHTTP_DOWNLOAD", "1").lower()[:1] in "1yt"
ENABLE_URLLIB = os.getenv("PYMANAGER_ENABLE_URLLIB_DOWNLOAD", "1").lower()[:1] in "1yt"
ENABLE_POWERSHELL = os.getenv("PYMANAGER_ENABLE_POWERSHELL_DOWNLOAD", "1").lower()[:1] in "1yt"


class NoInternetError(Exception):
    pass


class _Request:
    def __init__(self, url, method="GET", headers={}, outfile=None):
        self.url = url
        self.method = method.upper()
        self.headers = dict(headers)
        self.chunksize = 64 * 1024
        self.username = None
        self.password = None
        self.outfile = Path(outfile) if outfile else None
        self._on_progress = None
        self._on_auth_request = None

    def __str__(self):
        return sanitise_url(self.url)

    def on_progress(self, progress):
        if self._on_progress:
            self._on_progress(progress)

    def on_auth_request(self, url=None):
        if url is None:
            url = self.url
        if self._on_auth_request:
            return self._on_auth_request(url)
        if self.username or self.password:
            return self.username, self.password
        return None


def _bits_urlretrieve(request):
    from _native import (coinitialize, bits_connect, bits_begin, bits_cancel,
        bits_get_progress, bits_find_job, bits_serialize_job)

    assert request.outfile
    LOGGER.debug("_bits_urlretrieve: %s", request)
    coinitialize()
    bits = bits_connect()

    outfile = request.outfile

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
            LOGGER.debug("Starting new BITS job: %s -> %s", request, outfile)
            ensure_tree(outfile)
            # TODO: Apply auth after failed un-authed attempt?
            auth = request.on_auth_request() or (None, None)
            job = bits_begin(bits, PurePath(outfile).name, request.url, outfile, *auth)
            LOGGER.debug("Writing %s", jobfile)
            jobfile.write_bytes(bits_serialize_job(bits, job))

        LOGGER.debug("Downloading %s", request)
        last_progress = -1
        while last_progress < 100:
            progress = bits_get_progress(bits, job)
            if progress > last_progress:
                request.on_progress(progress)
            last_progress = progress
            time.sleep(0.1)
    except OSError as ex:
        if job:
            bits_cancel(bits, job)
        if jobfile.is_file():
            unlink(jobfile)
        if ex.winerror & 0xFFFFFFFF == 0x80200010:
            raise NoInternetError() from ex
        raise
    unlink(jobfile)


def _winhttp_urlopen(request):
    from _native import winhttp_urlopen, winhttp_isconnected
    headers = {k.lower(): v for k, v in request.headers.items()}
    accepts = headers.pop("accepts", "application/*;text/*")
    header_str = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
    method = request.method.upper()
    LOGGER.debug("winhttp_urlopen: %s", request)
    try:
        data = winhttp_urlopen(request.url, method, header_str, accepts,
            request.chunksize, request.on_progress, request.on_auth_request)
    except OSError as ex:
        if ex.winerror == 0x00002EE7:
            LOGGER.debug("winhttp_isconnected: %s", winhttp_isconnected())
            if not winhttp_isconnected():
                raise NoInternetError() from ex
        raise
    if data[:3] == b"\xEF\xBB\xBF":
        data = data[3:]
    return data

def _winhttp_urlretrieve(request):
    assert request.outfile
    request.outfile.write_bytes(_winhttp_urlopen(request))


def _basic_auth_header(username, password):
    from base64 import b64encode
    pair = f"{username}:{password}".encode("utf-8")
    token = b64encode(pair)
    return "Basic " + token.decode("ascii")


def _urllib_urlopen(request):
    import urllib.error
    from urllib.request import Request, urlopen

    LOGGER.debug("urlopen: %s", request)
    req = Request(request.url, method=request.method, headers=request.headers)
    try:
        request.on_progress(0)
        try:
            r = urlopen(req)
        except urllib.error.HTTPError as ex:
            if ex.status == 401:
                auth = request.on_auth_request()
                if not auth:
                    raise
                req.headers["Authorization"] = _basic_auth_header(*auth)
                r = urlopen(req)
            else:
                raise
        with r:
            data = r.read()
        request.on_progress(100)
        return data
    finally:
        LOGGER.debug("urlopen: complete")


def _urllib_urlretrieve(request):
    import urllib.error
    from urllib.request import Request, urlopen

    outfile = request.outfile
    LOGGER.debug("urlretrieve: %s -> %s", request, outfile)
    ensure_tree(outfile)
    unlink(outfile)
    req = Request(request.url, method=request.method, headers=request.headers)
    try:
        request.on_progress(0)
        try:
            r = urlopen(req)
        except urllib.error.HTTPError as ex:
            if ex.status == 401:
                req.auth = request.on_auth_request()
                if not req.auth:
                    raise
                r = urlopen(req)
            else:
                raise
        with r:
            progress = 0
            try:
                total = int(r.headers.get("Content-Length", 0))
            except ValueError:
                total = 1
            with open(outfile, "wb") as f:
                for chunk in iter(lambda: r.read(request.chunksize), b""):
                    f.write(chunk)
                    progress += len(chunk)
                    request.on_progress((progress * 100) // total)
        request.on_progress(100)
    finally:
        LOGGER.debug("urlretrieve: complete")


def _powershell_urlopen(request):
    import tempfile
    cwd = tempfile.mkdtemp()
    try:
        request.outfile = Path(cwd) / "response.dat"
        _powershell_urlretrieve(request)
        return request.outfile.read_bytes()
    finally:
        rmtree(cwd)


def _powershell_urlretrieve(request):
    from base64 import b64encode
    import subprocess
    powershell = Path(os.getenv("SystemRoot")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    script = fr"""$ProgressPreference = "SilentlyContinue"
$headers = @{{ {''.join(f'"{k}"={v};' for k, v in request.headers.items())} }}
# TODO: Get credentials from environment
$r = Invoke-WebRequest "{request.url}" -UseBasicParsing `
    -Headers $headers `
    -UseDefaultCredentials `
    -Method "{request.method}" `
    -OutFile "{request.outfile}"
"""
    LOGGER.debug("PowerShell script: %s", script)
    with subprocess.Popen(
        [powershell,
            "-ExecutionPolicy", "Bypass",
            "-OutputFormat", "Text",
            "-NonInteractive",
            "-EncodedCommand", b64encode(script.encode("utf-16-le"))
        ],
        cwd=request.outfile.parent,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        # TODO: Pass credentials in environment
        env={**os.environ},
    ) as p:
        request.on_progress(0)
        start = time.time()
        while True:
            try:
                try:
                    out = p.communicate(b'', timeout=10.0)[0].decode("utf-8", "replace")
                    if '<S S="Error">Invoke-WebRequest' in out:
                        raise RuntimeError("Powershell download failed:" + out)
                    request.on_progress(100)
                    LOGGER.debug("PowerShell Output: %s", out)
                    return
                except subprocess.TimeoutExpired:
                    if not request.outfile.exists():
                        # Suppress the original exception to avoid leaking the command
                        raise subprocess.TimeoutExpired(powershell, int(time.time() - start)) from None
            except:
                p.terminate()
                out = p.communicate()[0]
                LOGGER.debug("PowerShell Output: %s", out.decode("utf-8", "replace"))
                raise


def urlopen(url, method="GET", headers={}, on_progress=None, on_auth_request=None):
    if url.casefold().startswith("file://".casefold()):
        with open(file_url_to_path(url), "rb") as f:
            return f.read()

    request = _Request(url, method=method, headers=headers)
    request._on_progress = on_progress
    request._on_auth_request = on_auth_request

    if ENABLE_WINHTTP:
        try:
            return _winhttp_urlopen(request)
        except ImportError:
            LOGGER.debug("WinHTTP module unavailable - using fallback")
        except NoInternetError as ex:
            # No point going any further if WinHTTP has detected no internet
            # connection.
            request.on_progress(None)
            LOGGER.error("Failed to download. Please connect to the internet and try again.")
            raise RuntimeError("Failed to download. Please connect to the internet and try again.") from ex
        except OSError:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using WinHTTP. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    if ENABLE_URLLIB:
        try:
            return _urllib_urlopen(request)
        except ImportError:
            LOGGER.debug("urllib download unavailable - using fallback")
        except (AttributeError, TypeError, ValueError):
            # Blame the caller for these errors and let them bubble out
            raise
        except Exception:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using urllib. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    if ENABLE_POWERSHELL:
        try:
            return _powershell_urlopen(request)
        except FileNotFoundError:
            LOGGER.debug("PowerShell download unavailable - using fallback")
        except Exception:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using PowerShell. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)
        pass

    raise RuntimeError("Unable to download from the internet")


def urlretrieve(url, outfile, method="GET", headers={}, chunksize=64 * 1024, on_progress=None, on_auth_request=None):
    if url.casefold().startswith("file://".casefold()):
        with open(file_url_to_path(url), "rb") as r:
            with open(outfile, "wb") as f:
                for chunk in iter(lambda: r.read(chunksize), b""):
                    f.write(chunk)
        return

    request = _Request(url, method=method, headers=headers)
    request.outfile = Path(outfile)
    request.chunksize = chunksize
    request._on_progress = on_progress
    request._on_auth_request = on_auth_request

    if ENABLE_BITS and method.upper() == "GET":
        try:
            return _bits_urlretrieve(request)
        except ImportError:
            LOGGER.debug("BITS module unavailable - using fallback")
        except NoInternetError as ex:
            request.on_progress(None)
            try:
                from _native import winhttp_isconnected
            except ImportError:
                pass
            else:
                if not winhttp_isconnected():
                    LOGGER.error("Failed to download. Please connect to the internet and try again.")
                    raise RuntimeError("Failed to download. Please connect to the internet and try again.") from ex

            LOGGER.verbose("Failed to download using BITS, " +
                "possibly due to no internet. Retrying with fallback method.")
        except OSError:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using BITS. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    if ENABLE_WINHTTP:
        try:
            return _winhttp_urlretrieve(request)
        except ImportError:
            LOGGER.debug("WinHTTP module unavailable - using fallback")
        except NoInternetError as ex:
            # No point going any further if WinHTTP has detected no internet
            # connection.
            request.on_progress(None)
            LOGGER.error("Failed to download. Please connect to the internet and try again.")
            raise RuntimeError("Failed to download. Please connect to the internet and try again.") from ex
        except OSError:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using WinHTTP. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    if ENABLE_URLLIB:
        try:
            return _urllib_urlretrieve(request)
        except ImportError:
            LOGGER.debug("urllib module unavailable - using fallback")
        except (AttributeError, TypeError, ValueError):
            # Blame the caller for these errors and let them bubble out
            raise
        except Exception:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using urllib. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    if ENABLE_POWERSHELL:
        try:
            return _powershell_urlretrieve(request)
        except FileNotFoundError:
            LOGGER.debug("PowerShell download unavailable - using fallback")
        except Exception:
            request.on_progress(None)
            LOGGER.verbose("Failed to download using PowerShell. Retrying with fallback method.")
            LOGGER.debug("ERROR:", exc_info=True)

    raise RuntimeError("Unable to download from the internet")


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
