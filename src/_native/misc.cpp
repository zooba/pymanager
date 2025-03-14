#include <Python.h>
#include <windows.h>

#include "helpers.h"


extern "C" {

PyObject *coinitialize(PyObject *, PyObject *args, PyObject *kwargs) {
    HRESULT hr = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    if (FAILED(hr)) {
        PyErr_SetFromWindowsErr(hr);
        return NULL;
    }
    Py_RETURN_NONE;
}

static void _invalid_parameter(
   const wchar_t * expression,
   const wchar_t * function,
   const wchar_t * file,
   unsigned int line,
   uintptr_t pReserved
) { }

PyObject *fd_supports_vt100(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"fd", NULL};
    int fd;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "i:fd_supports_vt100", keywords, &fd)) {
        return NULL;
    }
    PyObject *r = NULL;
    HANDLE h;
    DWORD mode;
    const DWORD expect_flags = ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING;

    auto handler = _set_thread_local_invalid_parameter_handler(_invalid_parameter);
    h = (HANDLE)_get_osfhandle(fd);
    _set_thread_local_invalid_parameter_handler(handler);

    if (GetConsoleMode(h, &mode)) {
        if ((mode & expect_flags) == expect_flags) {
            r = Py_GetConstant(Py_CONSTANT_TRUE);
        } else {
            r = Py_GetConstant(Py_CONSTANT_FALSE);
        }
    } else {
        PyErr_SetFromWindowsErr(0);
    }
    return r;
}

PyObject *date_as_str(PyObject *, PyObject *, PyObject *) {
    wchar_t buffer[256];
    DWORD cch = GetDateFormatEx(
        LOCALE_NAME_INVARIANT,
        0,
        NULL,
        L"yyyyMMdd",
        buffer,
        sizeof(buffer) / sizeof(buffer[0]),
        NULL
    );
    if (!cch) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buffer, cch - 1);
}

PyObject *datetime_as_str(PyObject *, PyObject *, PyObject *) {
    wchar_t buffer[256];
    DWORD cch = GetDateFormatEx(
        LOCALE_NAME_INVARIANT,
        0,
        NULL,
        L"yyyyMMdd",
        buffer,
        sizeof(buffer) / sizeof(buffer[0]),
        NULL
    );
    if (!cch) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    cch -= 1;
    cch += GetTimeFormatEx(
        LOCALE_NAME_INVARIANT,
        0,
        NULL,
        L"HHmmss",
        &buffer[cch],
        sizeof(buffer) / sizeof(buffer[0]) - cch
    );
    return PyUnicode_FromWideChar(buffer, cch - 1);
}

}
