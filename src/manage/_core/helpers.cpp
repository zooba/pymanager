#include <Python.h>
#include <windows.h>

#include "helpers.h"

int as_utf16(PyObject *obj, wchar_t **address) {
    if (obj == NULL) {
        // Automatic cleanup
        PyMem_Free(*address);
        return 1;
    }
    PyObject *wobj = PyObject_Str(obj);
    if (!wobj) {
        return 0;
    }
    PyObject *b = PyObject_CallMethod(wobj, "encode", "ss", "utf-16-le", "strict");
    Py_DECREF(wobj);
    if (!b) {
        return 0;
    }
    char *src;
    Py_ssize_t len;
    if (PyBytes_AsStringAndSize(b, &src, &len) < 0) {
        Py_DECREF(b);
        return 0;
    }
    Py_ssize_t wlen = len / sizeof(wchar_t);
    wchar_t *result = (wchar_t *)PyMem_Malloc((wlen + 1) * sizeof(wchar_t));
    if (!result) {
        Py_DECREF(b);
        return 0;
    }
    wcsncpy_s(result, wlen + 1, (wchar_t *)src, wlen);
    Py_DECREF(b);
    *address = result;
    return Py_CLEANUP_SUPPORTED;
}
