#include <Python.h>
#include <windows.h>
#include <shlwapi.h>

#include "helpers.h"

#pragma comment(lib, "Shlwapi.lib")

extern "C" {

PyObject *
package_get_root(PyObject *, PyObject *, PyObject *)
{
    // Assume current process is running in the package root
    wchar_t buffer[MAX_PATH];
    DWORD cch = GetModuleFileName(NULL, buffer, MAX_PATH);
    if (!cch) {
        PyErr_SetFromWindowsErr(GetLastError());
        return NULL;
    }
    while (cch > 0 && buffer[--cch] != L'\\') { }
    return PyUnicode_FromWideChar(buffer, cch);
}


PyObject *
file_url_to_path(PyObject *, PyObject *args, PyObject *kwargs)
{
    static const char * keywords[] = {"url", NULL};
    wchar_t *url = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&:file_url_to_path", keywords,
        as_utf16, &url)) {
        return NULL;
    }

    PyObject *r = NULL;
    wchar_t path[32768];
    DWORD path_len = 32767;
    HRESULT hr = PathCreateFromUrlW(url, path, &path_len, 0);
    if (SUCCEEDED(hr)) {
        r = PyUnicode_FromWideChar(path, -1);
    } else {
        PyErr_SetFromWindowsErr(hr);
    }
    PyMem_Free(url);
    return r;
}

}