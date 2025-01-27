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

}
