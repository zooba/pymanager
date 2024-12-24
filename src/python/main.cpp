#include <Python.h>
#include <string.h>

#include <Windows.h>
#include <stdio.h>

#include <shellapi.h>
#include <shlobj.h>

#include <string>
#include <vector>

#include <appmodel.h>
#include <winrt\Windows.ApplicationModel.h>
#include <winrt\Windows.Storage.h>

#include "_launch.h"
#include "src\_native\helpers.h"
#include "commands.g.h"

// HRESULT-compatible error codes
#define ERROR_NO_MATCHING_INSTALL   0xA0000004
#define ERROR_NO_INSTALLS           0xA0000005

#ifndef PY_WINDOWED
#define PY_WINDOWED 0
#endif

struct {
    PyObject *mod;
    PyObject *no_install_found_error;
    PyObject *no_installs_error;
} manage = {NULL};

static std::wstring
get_root()
{
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


static bool
is_env_var_set(const wchar_t *name)
{
    /* only looking for non-empty, which means at least one character
       and the null terminator */
    return GetEnvironmentVariableW(name, NULL, 0) >= 2;
}


static int
read_tag_from_argv(std::wstring arg, std::wstring &tag)
{
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
args_to_skip(const wchar_t *arg)
{
    int retval = 0;
    for (const wchar_t *c = arg; *c; ++c) {
        switch (*c) {
        case L'c':
        case L'm':
            return -1;
        case L'W':
        case L'X':
            retval = 1;
        case L'-':
            break;
        default:
            if (!isalnum(*c)) {
                return 0;
            }
        }
    }
    return retval;
}

static void
read_script_from_argv(int argc, const wchar_t **argv, std::wstring &script)
{
    int skip = 0;
    for (int i = 1; i < argc; ++i) {
        if (skip > 0) {
            --skip;
            continue;
        }
        if (argv[i][0] == L'-') {
            skip = args_to_skip(argv[i]);
            if (skip < 0) {
                break;
            }
            continue;
        }
        script = argv[i];
        return;
    }
}


static int
init_python()
{
    // Ensure we are safely loading before triggering delay loaded DLL
    if (!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32
            | LOAD_LIBRARY_SEARCH_USER_DIRS
            | LOAD_LIBRARY_SEARCH_APPLICATION_DIR)) {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    PyStatus status;
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    status = Py_InitializeFromConfig(&config);
    if (PyStatus_Exception(status)) {
        PyConfig_Clear(&config);
        if (PyStatus_IsExit(status)) {
            return status.exitcode;
        }
        assert(PyStatus_Exception(status));
        Py_ExitStatusException(status);
        // Unreachable
        return -1;
    }

    // Ensure our main module is loadable
    manage.mod = PyImport_ImportModule("manage");
    if (!manage.mod) {
        PyErr_Print();
        return -1;
    }
    manage.no_install_found_error = PyObject_GetAttrString(manage.mod, "NoInstallFoundError");
    if (!manage.no_install_found_error) {
        PyErr_Print();
        return -1;
    }
    manage.no_installs_error = PyObject_GetAttrString(manage.mod, "NoInstallsError");
    if (!manage.no_installs_error) {
        PyErr_Print();
        return -1;
    }
    return 0;
}


static void
close_python()
{
    assert(manage.mod);
    Py_CLEAR(manage.no_installs_error);
    Py_CLEAR(manage.no_install_found_error);
    Py_CLEAR(manage.mod);
    Py_Finalize();
}


static int
run_command(int argc, const wchar_t **argv)
{
    int exitCode = 1;
    auto root_str = get_root();
    PyObject *args = NULL;
    PyObject *root = NULL;
    PyObject *r = NULL;

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
    r = PyObject_CallMethod(manage.mod, "main", "OO", args, root);
    if (r) {
        exitCode = PyLong_AsLong(r);
        goto done;
    }
python_fail:
    PyErr_Print();
done:
    Py_XDECREF(r);
    Py_XDECREF(root);
    Py_XDECREF(args);
    return exitCode;
}


static int
auto_install_runtime(const wchar_t *argv0, const std::wstring &tag, const std::wstring &script)
{
    int err = 0;
    const wchar_t *new_argv[] = { argv0, NULL, NULL, NULL, NULL };
    new_argv[1] = L"install";
    new_argv[2] = L"--automatic";
    if (!tag.empty()) {
        new_argv[3] = tag.c_str();
        err = run_command(4, new_argv);
    } else if (!script.empty()) {
        new_argv[3] = L"--from-script";
        new_argv[4] = script.c_str();
        err = run_command(5, new_argv);
    } else {
        err = run_command(3, new_argv);
    }
    return err;
}


static int
locate_runtime(
    const std::wstring &tag,
    const std::wstring &script,
    std::wstring &executable,
    std::wstring &args,
    int print_not_found_error
) {
    int exitCode = 1;
    auto root_str = get_root();
    PyObject *r = NULL;

    r = PyObject_CallMethod(manage.mod, "find_one", "uuuii",
        root_str.c_str(), tag.c_str(), script.c_str(), PY_WINDOWED, print_not_found_error);
    if (!r) {
        if (PyErr_ExceptionMatches(manage.no_installs_error)) {
            exitCode = ERROR_NO_INSTALLS;
        } else if (PyErr_ExceptionMatches(manage.no_install_found_error)) {
            exitCode = ERROR_NO_MATCHING_INSTALL;
        }
        // Other errors should already have been printed
        PyErr_Clear();
        goto done;
    } else {
        wchar_t *w_exe, *w_args;
        if (!PyArg_ParseTuple(r, "O&O&", as_utf16, &w_exe, as_utf16, &w_args)) {
            PyErr_Print();
            goto done;
        }
        executable = w_exe;
        args = w_args;
        PyMem_Free(w_exe);
        PyMem_Free(w_args);
        exitCode = 0;
    }
done:
    Py_XDECREF(r);
    return exitCode;
}


int
wmain(int argc, wchar_t **argv)
{
    int err = 0;
    DWORD exitCode;
    std::wstring executable, args, tag, script;
    int skip_argc = 0;

    err = init_python();
    if (err) {
        return err;
    }

    if (argc >= 2) {
        // Subcommands list is generated at sdist/build time and stored
        // in commands.g.h
        for (const wchar_t **cmd_name = subcommands; *cmd_name; ++cmd_name) {
            if (!wcscmp(argv[1], *cmd_name)) {
                return run_command(argc, (const wchar_t**)argv);
            }
        }
    }

    if (argc >= 2) {
        if (read_tag_from_argv(argv[1], tag)) {
            skip_argc += 1;
        } else {
            read_script_from_argv(argc, (const wchar_t **)argv, script);
        }
    }

    err = locate_runtime(tag, script, executable, args, 0);
#if !PY_WINDOWED
    // No implicit install when there's no console UI
    if (err == ERROR_NO_MATCHING_INSTALL || err == ERROR_NO_INSTALLS) {
        err = auto_install_runtime(argv[0], tag, script);
        if (!err) {
            err = locate_runtime(tag, script, executable, args, 1);
        }
        if (err == ERROR_NO_MATCHING_INSTALL || err == ERROR_NO_INSTALLS) {
            // Error has already been displayed
            goto error;
        }
    }
#endif

    if (err) {
        // Most 'not found' errors have been handled above. These are genuine
        fprintf(stderr, "FATAL ERROR: Found no suitable runtimes (0x%08X)\n", err);
        goto error;
    }

    err = launch(executable.c_str(), args.c_str(), skip_argc, &exitCode);
    if (err) {
        fprintf(stderr, "FATAL ERROR: Failed to launch '%ls' (0x%08X)\n", executable.c_str(), err);
    } else {
        err = (int)exitCode;
    }

error:
    close_python();
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
