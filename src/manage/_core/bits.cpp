#include <Python.h>
#include <windows.h>
#include <bits.h>
#include <typeinfo>

#include "helpers.h"

static PyObject *error_from_bits_hr(IBackgroundCopyManager *bcm, HRESULT hr) {
    LPWSTR err;
    HRESULT hr2 = bcm->GetErrorDescription(hr, LANGIDFROMLCID(GetThreadLocale()), &err);
    if (SUCCEEDED(hr2)) {
        size_t n = wcslen(err);
        while (n > 0 && wcschr(L"\r\n\t ", err[--n])) {
            err[n] = L'\0';
        }
        PyErr_Format(PyExc_OSError, "%ls (0x%08X)", err, (unsigned int)hr);
        CoTaskMemFree(err);
    } else {
        PyErr_SetFromWindowsErr(hr2);
    }
    return NULL;
}


static HRESULT get_job_progress(IBackgroundCopyJob *job, int *progress, int *already_complete) {
    HRESULT hr;
    BG_JOB_STATE job_state;
    BG_JOB_PROGRESS job_progress;
    if (FAILED(hr = job->GetState(&job_state))) {
        return hr;
    }

    *already_complete = 0;

    switch (job_state) {
    case BG_JOB_STATE_QUEUED:
    case BG_JOB_STATE_CONNECTING:
    case BG_JOB_STATE_CANCELLED:
        *progress = 0;
        break;
    case BG_JOB_STATE_TRANSFERRED:
        *progress = 100;
        break;
    case BG_JOB_STATE_ACKNOWLEDGED:
        *progress = 100;
        *already_complete = 1;
        break;
    case BG_JOB_STATE_TRANSFERRING:
    case BG_JOB_STATE_SUSPENDED:
        if (FAILED(hr = job->GetProgress(&job_progress))) {
            return hr;
        }
        // probably an unnecessary sanity check
        if (job_progress.FilesTransferred >= job_progress.FilesTotal
            || job_progress.BytesTransferred >= job_progress.BytesTotal) {
            *progress = 100;
        } else if (job_progress.BytesTotal == BG_SIZE_UNKNOWN) {
            *progress = (job_progress.FilesTransferred * 100) / job_progress.FilesTotal;
        } else {
            *progress = (job_progress.BytesTransferred * 100) / job_progress.BytesTotal;
        }
        break;
    case BG_JOB_STATE_TRANSIENT_ERROR:
    case BG_JOB_STATE_ERROR:
        return S_FALSE;
    }
    if (*progress < 0) {
        *progress = 0;
    } else if (*progress > 100) {
        *progress = 100;
    }
    return S_OK;
}


extern "C" {

PyObject *coinitialize(PyObject *, PyObject *args, PyObject *kwargs) {
    HRESULT hr = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED);
    if (FAILED(hr)) {
        PyErr_SetFromWindowsErr(hr);
        return NULL;
    }
    Py_RETURN_NONE;
}


// Returns a capsule containing the BackgroundCopyManager instance
PyObject *bits_connect(PyObject *, PyObject *args, PyObject *kwargs) {
    IBackgroundCopyManager *bcm = NULL;
    HRESULT hr = CoCreateInstance(
        __uuidof(BackgroundCopyManager),
        NULL,
        CLSCTX_LOCAL_SERVER,
        __uuidof(IBackgroundCopyManager),
        (void**)&bcm
    );
    if (FAILED(hr)) {
        PyErr_SetFromWindowsErr(hr);
        return NULL;
    }
    return make_capsule(bcm);
}


// (conn, job_id) -> job
PyObject *bits_find_job(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"conn", "job_id", NULL};
    IBackgroundCopyManager *bcm = NULL;
    Py_buffer job_id;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&y*:bits_find_job", keywords,
        from_capsule<IBackgroundCopyManager>, &bcm, &job_id
    )) {
        return NULL;
    }
    if (job_id.len < sizeof(GUID)) {
        PyBuffer_Release(&job_id);
        PyErr_SetString(PyExc_ValueError, "'job_id' must be a serialized job ID");
        return NULL;
    }

    PyObject *r = NULL;
    IBackgroundCopyJob *job = NULL;
    GUID job_guid = *(GUID *)job_id.buf;

    HRESULT hr = bcm->GetJob(job_guid, &job);

    if (SUCCEEDED(hr)) {
        r = make_capsule(job);
    } else {
        error_from_bits_hr(bcm, hr);
    }

    PyBuffer_Release(&job_id);
    return r;
}


// (conn, job) -> job_id
PyObject *bits_serialize_job(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"conn", "job", NULL};
    IBackgroundCopyManager *bcm = NULL;
    IBackgroundCopyJob* job = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&O&:bits_serialize_job", keywords,
        from_capsule<IBackgroundCopyManager>, &bcm, from_capsule<IBackgroundCopyJob>, &job)) {
        return NULL;
    }

    PyObject *r = NULL;
    GUID job_id;
    HRESULT hr = job->GetId(&job_id);
    if (SUCCEEDED(hr)) {
        r = PyBytes_FromStringAndSize((char *)&job_id, sizeof(job_id));
    } else {
        error_from_bits_hr(bcm, hr);
    }

    return r;
}


// (conn, name, url, path) -> job
PyObject *bits_begin(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"conn", "name", "url", "path", NULL};
    IBackgroundCopyManager *bcm = NULL;
    wchar_t *name = NULL;
    wchar_t *url = NULL;
    wchar_t *path = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&O&O&O&:bits_begin", keywords,
        from_capsule<IBackgroundCopyManager>, &bcm, as_utf16, &name, as_utf16, &url, as_utf16, &path
    )) {
        return NULL;
    }

    PyObject *r = NULL;
    GUID jobId;
    IBackgroundCopyJob* job = NULL;
    HRESULT hr;
    if (SUCCEEDED(hr = bcm->CreateJob(name, BG_JOB_TYPE_DOWNLOAD, &jobId, &job))
        && SUCCEEDED(hr = job->AddFile(url, path))
        && SUCCEEDED(hr = job->SetPriority(BG_JOB_PRIORITY_FOREGROUND))
        && SUCCEEDED(hr = job->Resume())
    ) {
        r = make_capsule(job);
    } else {
        if (job) {
            job->Release();
        }
        error_from_bits_hr(bcm, hr);
    }

    PyMem_Free(path);
    PyMem_Free(url);
    PyMem_Free(name);

    return r;
}


// (job)
PyObject *bits_cancel(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"conn", "job", NULL};
    IBackgroundCopyManager *bcm = NULL;
    IBackgroundCopyJob* job = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&O&:bits_cancel", keywords,
        from_capsule<IBackgroundCopyManager>, &bcm, from_capsule<IBackgroundCopyJob>, &job)) {
        return NULL;
    }
    HRESULT hr = job->Cancel();
    if (FAILED(hr)) {
        return error_from_bits_hr(bcm, hr);
    }
    Py_RETURN_NONE;
}


// (job) -> int[0..100] or exception
PyObject *bits_get_progress(PyObject *, PyObject *args, PyObject *kwargs) {
    static const char * keywords[] = {"conn", "job", NULL};
    IBackgroundCopyManager *bcm = NULL;
    IBackgroundCopyJob* job = NULL;
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O&O&:bits_get_progress", keywords,
        from_capsule<IBackgroundCopyManager>, &bcm, from_capsule<IBackgroundCopyJob>, &job)) {
        return NULL;
    }

    PyObject *r = NULL;
    int progress = 0, already_complete = 0;

    HRESULT hr = get_job_progress(job, &progress, &already_complete);

    if (hr == S_FALSE) {
        IBackgroundCopyError *error = NULL;
        BG_ERROR_CONTEXT context;
        HRESULT hr_error;
        LPWSTR str_error;
        hr = job->GetError(&error);
        if (SUCCEEDED(hr = job->GetError(&error))
            && SUCCEEDED(hr = error->GetError(&context, &hr_error))
            && SUCCEEDED(hr = error->GetErrorDescription(LANGIDFROMLCID(GetThreadLocale()), &str_error))) {
            size_t n = wcslen(str_error);
            while (n > 0 && wcschr(L"\r\n\t ", str_error[--n])) {
                str_error[n] = L'\0';
            }

            PyErr_Format(PyExc_OSError, "%ls (0x%08X)", str_error, (unsigned int)hr_error);
            CoTaskMemFree(str_error);
            error->Release();
            return NULL;
        }
        if (error) {
            error->Release();
        }
    }

    if (SUCCEEDED(hr)) {
        if (progress == 100 && !already_complete) {
            hr = job->Complete();
            if (SUCCEEDED(hr)) {
                r = Py_BuildValue("i", progress);
            }
        } else {
            r = Py_BuildValue("i", progress);
        }
    }

    if (FAILED(hr)) {
        return error_from_bits_hr(bcm, hr);
    }

    return r;
}

}

