# pymanager

Proof-of-concept for Python install manager app.

See [the draft PEP text](https://github.com/zooba/pymanager/blob/pep/pep-draft.md)
for additional information on how to use this.

# Build

To build and run locally:

```
> python -m pip install pymsbuild
> python -m pymsbuild
> python scripts\generate-nuget-index.py python-manager\index.json
> python-manager\py-manage.exe
```

The `python-manager\\py-manage` executable is the main entry point. No aliases
are created by a regular build, they are part of the MSIX installation process.

# Tests

To run the test suite locally:

```
> python -m pip install pymsbuild pytest
> python -m pymsbuild -c _msbuild_test.py
> python -m pytest
```

This builds the native components separately so that you can quickly iterate on
the Python code. Any updates to the C++ files will require running the
``pymsbuild`` step again.

# Package

To produce an (almost) installer app package:

```
> python -m pip install pymsbuild
> python package.py
```

This will rebuild the project and produce MSIX and APPXSYM packages.
Customization of output paths is future work.

You will need to sign the MSIX package before you can install it. This can be a
self-signed certificate, but it must be added to your Trusted Publishers.
Alternatively, rename the file to ``.zip`` and extract it to a directory, and
run ``Add-AppxPackage -Register <path to dir>\appxmanifest.xml`` to do a
development install. This should add the global aliases and allow you to test
as if it was properly installed.

# Contributions

Please contribute in [the discussion](https://discuss.python.org/t/pre-pep-a-python-installation-manager-for-windows/74556)
right now. This is only a prototype, and may change significantly before it is
ever used for anything.
