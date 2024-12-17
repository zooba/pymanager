#include <Python.h>
#include <string.h>

#include <Windows.h>
#include <stdio.h>

#include <shellapi.h>
#include <shlobj.h>

#include <string>

#include <appmodel.h>
#include <winrt\Windows.ApplicationModel.h>
#include <winrt\Windows.Storage.h>

#include "_launch.h"
#include "commands.g.h"

// HRESULT-compatible error codes
#define ERROR_NO_MATCHING_INSTALL   0xA0000004
#define ERROR_NO_INSTALLS           0xA0000005

static std::wstring get_root() {
    std::wstring path;
    try {
        const auto appData = winrt::Windows::Storage::ApplicationData::Current();
        if (appData) {
            const auto localCache = appData.LocalCacheFolder();
            if (localCache) {
                return localCache.Path().c_str();
            }
        }
    } catch (...) {
    }

    if (path.empty()) {
        while (true) {
            path.resize(path.size() + 260);
            DWORD path_len = GetModuleFileNameW(NULL, path.data(), path.size());
            if (!path_len) {
                break;
            }
            if (path_len <= path.size()) {
                path.resize(path.find_last_of(L"/\\", path_len, 2));
                return path;
            }
        }
    }

    return std::wstring();
}


static int
readCompanyTagFromArgv(std::wstring arg, std::wstring &tag) {
    if (arg[0] != L'-' && arg[0] != L'/') {
        return 0;
    }

    if (arg.substr(1, 2) == L"V:") {
        tag = arg.substr(3);
        return 1;
    } else if (arg[1] == L'3') {
        tag = std::wstring(L"PythonCore\\") + arg.substr(1);
        return 1;
    }
    return 0;
}


static int
runCommand(int argc, const wchar_t **argv)
{
    PyStatus status;
    PyConfig config;
    int exitCode = 1;
    auto root_str = get_root();
    PyObject *manage = NULL;
    PyObject *args = NULL;
    PyObject *root = NULL;
    PyObject *r = NULL;

    PyConfig_InitIsolatedConfig(&config);
    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) goto init_fail;

    manage = PyImport_ImportModule("manage");
    if (!manage) goto python_fail;
    args = PyList_New(0);
    if (!args) goto python_fail;
    for (int i = 0; i < argc; ++i) {
        PyObject *s = PyUnicode_FromWideChar(argv[i], -1);
        if (!s) goto python_fail;
        if (PyList_Append(args, s) < 0) {
            Py_DECREF(s);
            goto python_fail;
        }
        Py_DECREF(s);
    }
    root = PyUnicode_FromWideChar(root_str.c_str(), -1);
    if (!root) goto python_fail;
    r = PyObject_CallMethod(manage, "main", "OO", args, root);
    if (r) {
        exitCode = PyLong_AsLong(r);
    }
python_fail:
    Py_XDECREF(r);
    Py_XDECREF(root);
    Py_XDECREF(args);
    Py_XDECREF(manage);
    return exitCode;

init_fail:
    PyConfig_Clear(&config);
    if (PyStatus_IsExit(status)) {
        return status.exitcode;
    }
    assert(PyStatus_Exception(status));
    Py_ExitStatusException(status);
    /* Unreachable code */
    return 0;
}


static int
locateRuntime(const std::wstring &tag, std::wstring &executable) {
    PyStatus status;
    PyConfig config;
    int exitCode = 1;
    auto root_str = get_root();
    PyObject *manage = NULL;
    PyObject *r = NULL;

    PyConfig_InitIsolatedConfig(&config);
    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) goto init_fail;

    manage = PyImport_ImportModule("manage");
    if (!manage) goto python_fail;
    r = PyObject_CallMethod(manage, "_find_one", "uu", tag.c_str(), root_str.c_str());
    if (r) {
        if (PyUnicode_Check(r)) {
            executable.resize(PyUnicode_GetLength(r));
            executable.resize(PyUnicode_AsWideChar(r, executable.data(), executable.size()));
            exitCode = 0;
        } else {
            Py_CLEAR(r);
            r = PyObject_CallMethod(manage, "_find_any", "u", root_str.c_str());
            if (r) {
                if (PyObject_IsTrue(r)) {
                    exitCode = ERROR_NO_MATCHING_INSTALL;
                } else {
                    exitCode = ERROR_NO_INSTALLS;
                }
                Py_DECREF(r);
            } else {
                PyErr_Print();
            }
        }
    } else {
        PyErr_Print();
    }
python_fail:
    Py_XDECREF(r);
    Py_XDECREF(manage);
    return exitCode;

init_fail:
    PyConfig_Clear(&config);
    if (PyStatus_IsExit(status)) {
        return status.exitcode;
    }
    assert(PyStatus_Exception(status));
    Py_ExitStatusException(status);
    /* Unreachable code */
    return 0;
}


int
wmain(int argc, wchar_t **argv)
{
    // Ensure we are safely loading before triggering delay loaded DLL
    if (!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32
            | LOAD_LIBRARY_SEARCH_USER_DIRS
            | LOAD_LIBRARY_SEARCH_APPLICATION_DIR)) {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    if (argc >= 2) {
        // Subcommands list is generated at sdist/build time and stored
        // in commands.g.h
        for (const wchar_t **cmd_name = subcommands; *cmd_name; ++cmd_name) {
            if (!wcscmp(argv[1], *cmd_name)) {
                return runCommand(argc, (const wchar_t**)argv);
            }
        }
    }

    int err = 0;
    DWORD exitCode;
    std::wstring executable, tag;
    int skip_argc = 0;

    if (argc >= 2) {
        if (readCompanyTagFromArgv(argv[1], tag)) {
            skip_argc += 1;
        }
    }

    err = locateRuntime(tag, executable);
    if (err == ERROR_NO_MATCHING_INSTALL || err == ERROR_NO_INSTALLS) {
        const wchar_t *new_argv[] = { argv[0], NULL, NULL, NULL };
        new_argv[1] = L"install";
        new_argv[2] = L"--automatic";
        if (skip_argc) {
            new_argv[3] = tag.c_str();
        }
        err = runCommand(3 + skip_argc, new_argv);
        if (err) {
            return err;
        }
        err = locateRuntime(tag, executable);
    }

    if (err) {
        if (tag.empty()) {
            fprintf(stderr, "FATAL ERROR: Finding default executable (0x%08X)\n", err);
        } else {
            fprintf(stderr, "FATAL ERROR: Finding executable for %ls (0x%08X)\n", tag.c_str(), err);
        }
        goto error;
    }

    err = launch(executable.c_str(), skip_argc, &exitCode);
    if (err) {
        fprintf(stderr, "FATAL ERROR: Failed to launch '%ls' (0x%08X)\n", executable.c_str(), err);
    } else {
        err = (int)exitCode;
    }

error:
    return err;
}

int WINAPI wWinMain(
    HINSTANCE hInstance,      /* handle to current instance */
    HINSTANCE hPrevInstance,  /* handle to previous instance */
    LPWSTR lpCmdLine,         /* pointer to command line */
    int nCmdShow              /* show state of window */
)
{
    return wmain(__argc, __wargv);
}
