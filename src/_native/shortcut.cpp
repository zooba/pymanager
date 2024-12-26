#include <Python.h>
#include <windows.h>
#include <shlobj.h>
#include <shlguid.h>
#include "helpers.h"

extern "C" {

PyObject *
shortcut_create(PyObject *, PyObject *args, PyObject *kwargs)
{
    static const char *keywords[] = {
        "path", "target", "arguments", "working_directory",
        "icon", "icon_index",
        NULL
    };
    wchar_t *path = NULL;
    wchar_t *target = NULL;
    wchar_t *arguments = NULL;
    wchar_t *workingDirectory = NULL;
    wchar_t *iconPath = NULL;
    int iconIndex = 0;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs,
            "O&O&|O&O&O&i:shortcut_create", keywords,
            as_utf16, &path, as_utf16, &target, as_utf16, &arguments, as_utf16, &workingDirectory,
            as_utf16, &iconPath, &iconIndex)) {
        return NULL;
    }

    PyObject *r = NULL;
    IShellLinkW *lnk = NULL;
    IPersistFile *persist = NULL;
    HRESULT hr;

    hr = CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER,
        IID_IShellLinkW, (void **)&lnk);

    if (FAILED(hr)) {
        err_SetFromWindowsErrWithMessage(hr, "Creating system shortcut", NULL);
        goto done;
    }
    if (FAILED(hr = lnk->SetPath(target))) {
        err_SetFromWindowsErrWithMessage(hr, "Setting shortcut target", NULL);
        goto done;
    }
    if (arguments && *arguments && FAILED(hr = lnk->SetArguments(arguments))) {
        err_SetFromWindowsErrWithMessage(hr, "Setting shortcut arguments", NULL);
        goto done;
    }
    if (workingDirectory && *workingDirectory && FAILED(hr = lnk->SetWorkingDirectory(workingDirectory))) {
        err_SetFromWindowsErrWithMessage(hr, "Setting shortcut working directory", NULL);
        goto done;
    }
    if (iconPath && *iconPath && FAILED(hr = lnk->SetIconLocation(iconPath, iconIndex))) {
        err_SetFromWindowsErrWithMessage(hr, "Setting shortcut icon", NULL);
        goto done;
    }
    if (FAILED(hr = lnk->QueryInterface(&persist)) ||
        FAILED(hr = persist->Save(path, 0))) {
        err_SetFromWindowsErrWithMessage(hr, "Writing shortcut", NULL);
        goto done;
    }

    r = Py_NewRef(Py_None);

done:
    if (persist) {
        persist->Release();
    }
    if (lnk) {
        lnk->Release();
    }
    if (path) PyMem_Free(path);
    if (target) PyMem_Free(target);
    if (arguments) PyMem_Free(arguments);
    if (workingDirectory) PyMem_Free(workingDirectory);
    if (iconPath) PyMem_Free(iconPath);
    return r;
}


PyObject *
shortcut_get_start_programs(PyObject *, PyObject *, PyObject *)
{
    wchar_t *path;
    HRESULT hr = SHGetKnownFolderPath(
        FOLDERID_Programs,
        KF_FLAG_NO_PACKAGE_REDIRECTION | KF_FLAG_CREATE,
        NULL,
        &path
    );
    if (FAILED(hr)) {
        err_SetFromWindowsErrWithMessage(hr, "Obtaining Start Menu location", NULL);
        return NULL;
    }
    PyObject *r = PyUnicode_FromWideChar(path, -1);
    CoTaskMemFree(path);
    return r;
}


PyObject *
hide_file(PyObject *, PyObject *args, PyObject *kwargs)
{
    static const char *keywords[] = {"path", "hidden", NULL};
    wchar_t *path;
    int hidden = 1;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&|b:hide_file", keywords, as_utf16, &path, &hidden)) {
        return NULL;
    }
    PyObject *r = NULL;
    DWORD attr = GetFileAttributesW(path);
    if (attr == INVALID_FILE_ATTRIBUTES) {
        err_SetFromWindowsErrWithMessage(GetLastError(), "Reading file attributes", NULL);
        goto done;
    }
    if (hidden) {
        attr |= FILE_ATTRIBUTE_HIDDEN;
    } else {
        attr &= ~FILE_ATTRIBUTE_HIDDEN;
    }
    if (!SetFileAttributesW(path, attr)) {
        err_SetFromWindowsErrWithMessage(GetLastError(), "Setting file attributes", NULL);
        goto done;
    }

    r = Py_NewRef(Py_None);

done:
    PyMem_Free(path);
    return r;
}

}
