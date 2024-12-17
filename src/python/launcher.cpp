#include <windows.h>
#include <stdio.h>

#include "_launch.h"

#define MAXLEN 32768

// HRESULT-compatible error codes
#define ERROR_NO_FILENAME   0xA0000001
#define ERROR_NO_PYTHON3    0xA0000002
#define ERROR_DLL_LOAD_DISABLED 0xA0000003

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
tryLoadPython3Dll(const wchar_t *executable, unsigned int bufferSize, void **mainFunction)
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
        return HRESULT_FROM_WIN32(GetLastError());
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


int
wmain(int argc, wchar_t **argv)
{
    wchar_t executable[MAXLEN];
    int err = get_executable(executable, MAXLEN);
    if (err) {
        fprintf(stderr, "FATAL ERROR: Failed to get target path (0x%08X)\n", err);
        return err;
    }

    int (*mainFunc)(int argc, wchar_t **argv);
    err = tryLoadPython3Dll(executable, MAXLEN, (void **)&mainFunc);
    if (!err) {
        // We have a Py_Main() to call, so let's create the argv that we need
        wchar_t **newArgv = (wchar_t **)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, argc * sizeof(wchar_t *));
        if (!newArgv) {
            err = GetLastError();
            fprintf(stderr, "FATAL ERROR: Failed to allocate command line (0x%08X)\n", err);
            return err;
        }
        
        newArgv[0] = executable;
        for (int i = 1; i < argc; ++i) {
            newArgv[i] = argv[i];
        }

        err = (*mainFunc)(argc, newArgv);

        HeapFree(GetProcessHeap(), 0, newArgv);
    } else {
        DWORD exitCode;
        err = launch(executable, 0, &exitCode);
        if (err) {
            fprintf(stderr, "FATAL ERROR: Failed to launch '%ls' (0x%08X)\n", executable, err);
        } else {
            err = (int)exitCode;
        }
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
