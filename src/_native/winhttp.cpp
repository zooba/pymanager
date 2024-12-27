#include <Python.h>
#include <windows.h>
#include <winhttp.h>

#include "helpers.h"

#pragma comment(lib, "winhttp.lib")

static void _winhttp_error(const char *location) {
    DWORD err = GetLastError();
    LPWSTR message;
    DWORD message_len = FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER
        | FORMAT_MESSAGE_FROM_HMODULE
        | FORMAT_MESSAGE_FROM_SYSTEM
        | FORMAT_MESSAGE_IGNORE_INSERTS,
        GetModuleHandleW(L"winhttp"),
        err,
        0,
        (LPWSTR)&message,
        0,
        NULL
    );
    if (message_len) {
        while (message_len > 0 && wcschr(L"\r\n\t ", message[--message_len])) {
            message[message_len] = L'\0';
        }

        if (location) {
            PyErr_Format(PyExc_OSError, "%ls (0x%08X) at %s", message, err, location);
        } else {
            PyErr_Format(PyExc_OSError, "%ls (0x%08X)", message, err);
        }
        LocalFree((void *)message);
    } else {
        PyErr_SetFromWindowsErr(err);
    }
}

#ifdef ERROR_LOCATIONS
#define winhttp_error() _winhttp_error(__FILE__ ":" Py_STRINGIFY(__LINE__))
#else
#define winhttp_error() _winhttp_error(NULL)
#endif


template <typename T> struct WHQH_Flags { static const DWORD flags = 0; };
template <> struct WHQH_Flags<DWORD> { static const DWORD flags = WINHTTP_QUERY_FLAG_NUMBER; };
template <> struct WHQH_Flags<uint64_t> { static const DWORD flags = WINHTTP_QUERY_FLAG_NUMBER; };

template <typename T>
static bool read_header(HINTERNET hRequest, DWORD headerIndex, T *value) {
    DWORD value_len = sizeof(T);
    if (!WinHttpQueryHeaders(
        hRequest,
        headerIndex | WHQH_Flags<T>::flags,
        WINHTTP_HEADER_NAME_BY_INDEX,
        value,
        &value_len,
        WINHTTP_NO_HEADER_INDEX
    )) {
        winhttp_error();
        return false;
    }
    return true;
}

static void http_error(HINTERNET hRequest) {
    wchar_t *reason;
    DWORD reason_len;
    DWORD status;

    if (!read_header(hRequest, WINHTTP_QUERY_STATUS_CODE, &status)) {
        return;
    }

    WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_TEXT, WINHTTP_HEADER_NAME_BY_INDEX,
                        WINHTTP_NO_OUTPUT_BUFFER, &reason_len, WINHTTP_NO_HEADER_INDEX);
    if (GetLastError() != ERROR_INSUFFICIENT_BUFFER) {
        winhttp_error();
        return;
    }
    if (!reason_len) {
        PyErr_Format(PyExc_RuntimeError, "HTTP request return status %d", status);
        return;
    }
    // reason_len is in bytes, including null terminator
    reason = (wchar_t*)PyMem_Malloc(reason_len);
    if (!reason) {
        PyErr_NoMemory();
        return;
    }
    if (!WinHttpQueryHeaders(hRequest, WINHTTP_QUERY_STATUS_TEXT, WINHTTP_HEADER_NAME_BY_INDEX,
                             reason, &reason_len, WINHTTP_NO_HEADER_INDEX)) {
        winhttp_error();
        return;
    }
    PyErr_Format(PyExc_RuntimeError, "HTTP status %d: %ls", status, reason);
    PyMem_Free(reason);
}


static bool request_creds(HINTERNET hRequest, const wchar_t *url, PyObject *on_cred_request) {
    PyObject *result = PyObject_CallFunction(on_cred_request, "u", url);
    if (!result) {
        return false;
    }
    if (!PyObject_IsTrue(result)) {
        Py_DECREF(result);
        http_error(hRequest);
        return false;
    }
    // Read new auth from result
    wchar_t *user, *pass;
    if (!PyArg_ParseTuple(result, "O&O&", as_utf16, &user, as_utf16, &pass)) {
        Py_DECREF(result);
        return false;
    }
    Py_DECREF(result);

    BOOL r = WinHttpSetCredentials(
        hRequest,
        WINHTTP_AUTH_TARGET_SERVER,
        WINHTTP_AUTH_SCHEME_BASIC,
        user,
        pass,
        NULL
    );
    PyMem_Free(user);
    PyMem_Free(pass);
    return r;
}

static wchar_t **split_to_array(wchar_t *str, wchar_t sep) {
    int count = 1;
    wchar_t *i;
    for (i = str; *i; ++i) {
        if (*i == sep) {
            ++count;
        }
    }
    wchar_t **arr = (wchar_t **)PyMem_Malloc(sizeof(wchar_t *) * (count + 1));
    if (!arr) {
        PyErr_NoMemory();
        return NULL;
    }
    wchar_t **a = arr + count;
    *a-- = NULL;
    while (i >= &str[1]) {
        if (*--i == sep) {
            *i = L'\0';
            *a-- = i + 1;
        }
    }
    *arr = str;
    return arr;
}

static int crack_url(const wchar_t *url, URL_COMPONENTS *parts) {
    parts->dwHostNameLength = 1;
    parts->dwUserNameLength = 1;
    parts->dwPasswordLength = 1;
    parts->dwUrlPathLength = 1;
    parts->dwExtraInfoLength = 1;
    if (!WinHttpCrackUrl(url, 0, 0, parts)) {
        winhttp_error();
        return 0;
    }
    if (parts->dwHostNameLength) {
        ++parts->dwHostNameLength;
        parts->lpszHostName = (LPWSTR)PyMem_Malloc(parts->dwHostNameLength * sizeof(wchar_t));
        if (!parts->lpszHostName) {
            PyErr_NoMemory();
            return 0;
        }
    } else {
        parts->lpszHostName = NULL;
    }
    if (parts->dwUserNameLength) {
        ++parts->dwUserNameLength;
        parts->lpszUserName = (LPWSTR)PyMem_Malloc(parts->dwUserNameLength * sizeof(wchar_t));
        if (!parts->lpszUserName) {
            PyErr_NoMemory();
            return 0;
        }
    } else {
        parts->lpszUserName = NULL;
    }
    if (parts->dwPasswordLength) {
        ++parts->dwPasswordLength;
        parts->lpszPassword = (LPWSTR)PyMem_Malloc(parts->dwPasswordLength * sizeof(wchar_t));
        if (!parts->lpszPassword) {
            PyErr_NoMemory();
            return 0;
        }
    } else {
        parts->lpszPassword = NULL;
    }
    if (parts->dwUrlPathLength) {
        ++parts->dwUrlPathLength;
        parts->lpszUrlPath = (LPWSTR)PyMem_Malloc(parts->dwUrlPathLength * sizeof(wchar_t));
        if (!parts->lpszUrlPath) {
            PyErr_NoMemory();
            return 0;
        }
    } else {
        parts->lpszUrlPath = NULL;
    }
    if (parts->dwExtraInfoLength) {
        ++parts->dwExtraInfoLength;
        parts->lpszExtraInfo = (LPWSTR)PyMem_Malloc(parts->dwExtraInfoLength * sizeof(wchar_t));
        if (!parts->lpszExtraInfo) {
            PyErr_NoMemory();
            return 0;
        }
    } else {
        parts->lpszExtraInfo = NULL;
    }
    if (!WinHttpCrackUrl(url, 0, 0, parts)) {
        winhttp_error();
        return 0;
    }
    return 1;
}

static int free_cracked_url(URL_COMPONENTS *parts) {
    PyMem_Free(parts->lpszHostName);
    PyMem_Free(parts->lpszUserName);
    PyMem_Free(parts->lpszPassword);
    PyMem_Free(parts->lpszUrlPath);
    PyMem_Free(parts->lpszExtraInfo);
    return 1;
}

extern "C" {

PyObject *winhttp_urlopen(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"url", "method", "headers", "accepts", "chunksize", "on_progress", "on_cred_request", NULL};
    wchar_t *url = NULL;
    wchar_t *method = NULL;
    wchar_t *headers = NULL;
    wchar_t *accepts = NULL;
    PyObject *on_progress = NULL;
    PyObject *on_cred_request = NULL;

    PyObject *result = NULL;
    URL_COMPONENTS url_parts = { sizeof(URL_COMPONENTS) };
    HINTERNET hSession = NULL;
    HINTERNET hConnection = NULL;
    HINTERNET hRequest = NULL;
    DWORD opt = 0;
    LPCWSTR *accepts_array;

    Py_ssize_t chunksize = 65536;
    DWORD status_code = 0;
    uint64_t content_length;
    PyObject *chunks = NULL;
    uint64_t content_read = 0;

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&O&O&O&|nOO:winhttp_urlopen", keywords,
        as_utf16, &url, as_utf16, &method, as_utf16, &headers, as_utf16, &accepts, &chunksize, &on_progress, &on_cred_request)) {
        return NULL;
    }

    if (on_progress && !PyObject_IsTrue(on_progress)) {
        on_progress = NULL;
    }
    if (on_cred_request && !PyObject_IsTrue(on_cred_request)) {
        on_cred_request = NULL;
    }

    accepts_array = (LPCWSTR*)split_to_array(accepts, L';');
    if (!accepts_array) {
        goto exit;
    }
    if (!crack_url(url, &url_parts)) {
        goto exit;
    }

#define CHECK_WINHTTP(x) if (!x) { winhttp_error(); goto exit; }

    hSession = WinHttpOpen(
        NULL,
        WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS,
        url_parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE_DEFAULTS : 0
    );
    CHECK_WINHTTP(hSession);

    hConnection = WinHttpConnect(
        hSession,
        url_parts.lpszHostName,
        url_parts.nPort,
        0
    );
    CHECK_WINHTTP(hConnection);

    hRequest = WinHttpOpenRequest(
        hConnection,
        method,
        url_parts.lpszUrlPath,
        NULL,
        WINHTTP_NO_REFERER,
        accepts_array,
        url_parts.nScheme == INTERNET_SCHEME_HTTPS ? WINHTTP_FLAG_SECURE : 0
    );
    CHECK_WINHTTP(hRequest);

    opt = WINHTTP_DECOMPRESSION_FLAG_ALL;
    CHECK_WINHTTP(WinHttpSetOption(
        hRequest,
        WINHTTP_OPTION_DECOMPRESSION,
        &opt,
        sizeof(opt)
    ));

    if (url_parts.dwUserNameLength || url_parts.dwPasswordLength) {
        CHECK_WINHTTP(WinHttpSetCredentials(
            hRequest,
            WINHTTP_AUTH_TARGET_SERVER,
            WINHTTP_AUTH_SCHEME_BASIC,
            url_parts.lpszUserName,
            url_parts.lpszPassword,
            NULL
        ));
    }

    while (!status_code) {
        CHECK_WINHTTP(WinHttpSendRequest(hRequest, headers, -1, NULL, 0, 0, NULL));
        CHECK_WINHTTP(WinHttpReceiveResponse(hRequest, NULL));
        if (!read_header(hRequest, WINHTTP_QUERY_STATUS_CODE, &status_code)) goto exit;

        if (status_code == HTTP_STATUS_DENIED) {
            // Status 401
            if (on_cred_request) {
                if (!request_creds(hRequest, url, on_cred_request)) {
                    goto exit;
                }
                // Make the request again
                status_code = 0;
                // Do not call on_cred_request again
                on_cred_request = NULL;
            } else {
                http_error(hRequest);
                goto exit;
            }
        } else if (status_code < 200 || status_code >= 300) {
            http_error(hRequest);
            goto exit;
        }
    }

    if (!read_header(hRequest, WINHTTP_QUERY_CONTENT_LENGTH, &content_length)) {
        PyErr_Clear();
        content_length = 0;
    }
    if (on_progress) {
        result = PyObject_CallFunction(on_progress, "i", 0);
        if (!result) {
            goto exit;
        }
        Py_CLEAR(result);
    }

    chunks = PyList_New(0);
    while (true) {
        DWORD data_len, data_read;
        // TODO: Check for KeyboardInterrupt and abort
        if (!WinHttpQueryDataAvailable(hRequest, &data_len)) {
            winhttp_error();
            goto exit;
        }
        if (!data_len) {
            break;
        }
        if (data_len > chunksize) {
            data_len = chunksize;
        }
        PyObject *buffer = PyBytes_FromStringAndSize(NULL, data_len);
        if (!buffer) {
            Py_CLEAR(chunks);
            break;
        }
        if (!WinHttpReadData(hRequest, PyBytes_AsString(buffer), data_len, &data_read)) {
            Py_DECREF(buffer);
            Py_CLEAR(chunks);
            break;
        }
        if (!data_read) {
            Py_DECREF(buffer);
            break;
        }
        _PyBytes_Resize(&buffer, data_read);
        if (!buffer) {
            Py_CLEAR(chunks);
            break;
        }
        if (PyList_Append(chunks, buffer) < 0) {
            Py_DECREF(buffer);
            Py_CLEAR(chunks);
            break;
        }
        Py_DECREF(buffer);
        content_read += data_read;
        if (on_progress && content_length) {
            result = PyObject_CallFunction(on_progress, "i", content_read * 100 / content_length);
            if (!result) {
                Py_CLEAR(chunks);
                break;
            }
            Py_CLEAR(result);
        }
    }

    if (chunks) {
        PyObject *sep = PyBytes_FromStringAndSize(NULL, 0);
        if (sep) {
            result = PyObject_CallMethod(sep, "join", "O", chunks);
            Py_DECREF(sep);
        }
        Py_DECREF(chunks);

        if (on_progress) {
            PyObject *result2 = PyObject_CallFunction(on_progress, "i", 100);
            if (!result2) {
                goto exit;
            }
            Py_DECREF(result2);
        }
    }
exit:
    if (hRequest) {
        WinHttpCloseHandle(hRequest);
    }
    if (hConnection) {
        WinHttpCloseHandle(hConnection);
    }
    if (hSession) {
        WinHttpCloseHandle(hSession);
    }
    free_cracked_url(&url_parts);
    PyMem_Free(accepts_array);
    PyMem_Free(accepts);
    PyMem_Free(headers);
    PyMem_Free(method);
    PyMem_Free(url);
    return result;
}

}