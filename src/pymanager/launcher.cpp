#include <windows.h>
#include <stdio.h>

#include "_launch.h"

#define MAXLEN 32768

// HRESULT-compatible error codes
#define ERROR_NO_FILENAME   0xA0000001
#define ERROR_NO_PYTHON3    0xA0000002
#define ERROR_DLL_LOAD_DISABLED 0xA0000003

static int
print_error(int err, const wchar_t *message)
{
    if (!err) {
        err = GetLastError();
    }
    switch (err) {
    case 0:
        fwprintf(stderr, L"[WARN] Error was reported but no error code was set.\n"
                        "[ERROR] %s\n", message);
        break;
    default:
        // TODO: Improved rendering of errors
        fwprintf(stderr, L"[ERROR] %s (0x%08X)\n", message, err);
    }
    return err;
}


int
get_executable(wchar_t *executable, unsigned int bufferSize)
{
    wchar_t config[MAXLEN];
    DWORD len = GetModuleFileNameW(NULL, config, MAXLEN);
    if (len == 0) {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    wcscat_s(config, L".__target__");

    HANDLE hFile = CreateFileW(config, GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
    if (hFile == INVALID_HANDLE_VALUE) {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    char buffer[MAXLEN];
    DWORD bytesRead;
    if (!ReadFile(hFile, buffer, sizeof(buffer), &bytesRead, NULL)) {
        int err = GetLastError();
        CloseHandle(hFile);
        return HRESULT_FROM_WIN32(err);
    }
    buffer[bytesRead] = '\0';
    CloseHandle(hFile);
    if (!MultiByteToWideChar(CP_UTF8, 0, buffer, bytesRead + 1, executable, bufferSize)) {
        return HRESULT_FROM_WIN32(GetLastError());
    }

    return 0;
}



int
try_load_python3_dll(const wchar_t *executable, unsigned int bufferSize, void **mainFunction)
{
#ifdef NO_DLL_LOADING
    return ERROR_DLL_LOAD_DISABLED;
#else
    wchar_t directory[MAXLEN];
    wcscpy_s(directory, executable);
    wchar_t *sep = wcsrchr(directory, L'\\');
    if (!sep) {
        return ERROR_NO_FILENAME;
    }
    *sep = L'\0';

    if (!SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_SYSTEM32 | LOAD_LIBRARY_SEARCH_USER_DIRS)) {
        return HRESULT_FROM_WIN32(GetLastError());
    }
    AddDllDirectory(directory);
    HMODULE mod = LoadLibraryExW(L"python3.dll", NULL, 0);
    if (!mod) {
        return GetLastError();
    }
    unsigned long *version = (unsigned long *)GetProcAddress(mod, "Py_Version");
    if (!version || *version < 0x030A0000 || *version >= 0x04000000) {
        FreeLibrary(mod);
        return ERROR_NO_PYTHON3;
    }
    *mainFunction = GetProcAddress(mod, "Py_Main");
    if (!*mainFunction) {
        return HRESULT_FROM_WIN32(GetLastError());
    }
    return 0;
#endif
}

static int
launch_by_dll(void *main_func_ptr, wchar_t *executable, int argc, wchar_t **argv, int *exit_code)
{
    int (*main_func)(int argc, wchar_t **argv) = (int (*)(int, wchar_t **))main_func_ptr;

    // We have a Py_Main() to call, so let's create the argv that we need
    wchar_t **newArgv = (wchar_t **)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, argc * sizeof(wchar_t *));
    if (!newArgv) {
        return print_error(0, L"Failed to allocate command line");
    }

    newArgv[0] = executable;
    for (int i = 1; i < argc; ++i) {
        newArgv[i] = argv[i];
    }

    // Our caller assumes that any error result happens before we launch. From
    // this point on, exit_code is set (possibly to an error), and so we should
    // only return 0.

    *exit_code = (*main_func)(argc, newArgv);

    HeapFree(GetProcessHeap(), 0, newArgv);
    return 0;
}

int
wmain(int argc, wchar_t **argv)
{
    int exit_code;
    wchar_t executable[MAXLEN];
    int err = get_executable(executable, MAXLEN);
    if (err) {
        return print_error(err, L"Failed to get target path");
    }

    void *main_func = NULL;
    err = try_load_python3_dll(executable, MAXLEN, (void **)&main_func);
    switch (err) {
    case 0:
        err = launch_by_dll(main_func, executable, argc, argv, &exit_code);
        if (!err) {
            return exit_code;
        }
        break;
    case ERROR_NO_PYTHON3:
        // expected for incompatible runtimes - fall through to the .exe
        break;
    case ERROR_DLL_LOAD_DISABLED:
        break;
    default:
        // Errors at non-fatal steps (such as "python3.dll not found") will not
        // have the top bit set. Perhaps we should warn/log them anyway, but not
        // to the console
        if (!(err & 0x80000000)) {
            break;
        }
        // Other errors indicate that we ought to have succeeded but didn't, so
        // display a message but still fall back to a regular launch.
        // Most users will be launching CPython, which should have this DLL and
        // prefer to load directly, so this is helpful.
        print_error(err, L"Failed to load runtime DLL; "
                         L"attempting to launch as a new process.");
        break;
    }

    err = launch(executable, NULL, 0, (DWORD *)&exit_code);
    if (!err) {
        return exit_code;
    }

    const wchar_t *fmt = L"Failed to launch '%ls'";
    DWORD n = wcslen(fmt) + wcslen(executable) + 1;
    wchar_t *message = (wchar_t *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n * sizeof(wchar_t));
    if (!message) {
        err = print_error(0, L"Failed to launch, and failed to allocate error message.");
    } else {
        swprintf_s(message, n, fmt, executable);
        err = print_error(err, message);
        HeapFree(GetProcessHeap(), 0, message);
    }

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
