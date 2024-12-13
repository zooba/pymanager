```
PEP: TBD
Title: A Python Installation Manager for Windows
Author: Steve Dower
PEP-Delegate: TBD
Discussions-To: TBD
Status: Draft
Type: Standards Track
Topic: Release
Created: 12-12-2024
Python-Version: N/A
Post-History: TBD
Resolution: TBD
```


Abstract
========

Installation of the python.org Python distribution on Windows is complex.
There are three main approaches with roughly equivalent levels of user
experience, and yet all of these suffer from different limitations, including
failing to satisfy modern usage scenarios. This PEP proposes a design for
a single install workflow tool that satisfies all the needs of the existing
installers, while avoiding most of their limitations, and provides the core
team with a long-term plan for releasing pre-built distributions.


Background
==========

There are a large range of needs users may have that lead to them wanting
to install a Python runtime. Many, likely most, are interesting in running
(perhaps writing) short scripts, such as those that perform a simple task,
or help teach someone a concept. Some users are looking for a specific version
to integrate with existing code or another application. Some are after a full
set of different interpreter versions to perform testing.

In this section, we discuss the expectations that users have of "installing
Python", provide an overview of the existing installers for Windows, and
identify some of the gaps and challenges inherent in these offerings.

Expectations
------------

Based on significant anecdotal experience and analysis of quantitative data
available (though not necessarily public), we make the following assertions
about the majority of Python users on Windows:

* most users just want the latest stable version
* most users want a "one-click" (or fewer) install
* most users do not want to use administrator privileges
* most users will benefit from installing maintenance updates
* most users expect the ``python`` command to work after installation

The primary support for these assertions is that the most popular installers
actively chosen by users are the latest stable release on python.org, and
the latest stable release on the Windows Store, both of which meet these
requirements.

We make the following assumptions about other significant sets of users.
These may have some overlap between groups, and at least some users expect
all of them.

* some users want to install Python programmatically
* some users want to install a particular version
* some users want to install many versions
* some users want to install for all users of their machine
* some users do not want Start Menu shortcuts
* some users want to install as part of their project's build process
* some users want to install as part of their project's install process
* some users intend to never update their install

These assumptions have all been demonstrated over time to exist, though the
relative importance has not been quantified. The Nuget packages and the
embeddable distro can meet most of these needs.

Traditional Installer
---------------------

The traditional installer is an executable downloadable directly from
python.org that installs the entire development kit for Python. This includes
the CPython interpreter, the standard library, Python headers and import
libraries, builds of Tcl and Tk, the documentation as HTML files, the runtime
and standard library test suite, Start Menu shortcuts for Python and IDLE,
debugging symbols and debug builds of the binaries, the ``py.exe`` launcher
and its file associations, and functionality to modify the user's ``PATH``
environment variable, enable long-path support on their system, pre-generate
``.pyc`` files for the standard library, and install pip.
As of 3.13, it also includes a set of experimental free-threaded binaries.
Many of these components are optional.

After downloading the executable, users are presented with a "quick install"
option, which installs into their user directory with most options enabled.
We believe that most users select this option.

A second option alongside the quick install takes the user to two pages worth
of options, listing the components that they need not install, as well as other
options such as the install directory and whether to install for all users.

All of these options may be specified on the command line, and there is also an
option to proceed with the install without displaying any UI.
Based on feedback and bug reports, all of these options are used by at least
some users. However, as we do not track install telemetry, we have no way to
know which options are more important than others.

Behind the scenes, the traditional installer is a Burn bundle, generated using
the Wix Toolset installer framework, containing multiple MSI files with each
feature. This framework is used extensively by Microsoft themselves, and
provides the most direct method of using Windows Installer. The bundle is a
custom application, based on their template, which allows us to customise the
overall behaviour of the installer to determine precisely which MSI files
should actually be installed. The process of copying files, updating the
registry, and generating shortcuts is handled entirely by Windows Installer.

Windows Store
-------------

The Windows Store packages for CPython are produced as part of our normal
release process using almost all identical binaries to the other packages.
Due to being in an app store package, the primary ``python.exe`` is enhanced
to be able to determine its location properly, and default ``pip.exe`` and
other shortcuts are included to make up for the lack of ``PATH`` environment
variable settings.

These packages are installed by searching for Python in the Microsoft Store
app, which will find results for each major version since 3.8. Users then have
to select a version and install it. These packages include the CPython
interpreter, standard library, Tcl/Tk, IDLE and pip, and create file
associations, Start Menu shortcuts, and global commands for ``python.exe``,
``python3.exe``, ``python3.X.exe``, ``pip[3[.X]].exe`` and ``idle[3[.X]].exe``.
No ``PATH`` modification is possible or required, though users may need to
manage their global shortcuts through the "Manage App Execution Alias" settings
page.

In addition, Microsoft has added to a clean Windows install a default
``python.exe`` command. This captures attempts by users to launch Python on
a machine that has not yet installed it. When launched directly, the command
will open the Microsoft Store app to the page containing the recommended
Python app, typically the latest version. This app is entirely controlled by
Microsoft. Based on telemetry associated with the Python app (which _is_
controlled by the upstream Python project), approximately 300,000 installs
per month come through this redirector, making up about 90% of the total
installs of that version.

Behind the scenes, the Store package is based on Microsoft's new installer
technology for apps known as APPX or MSIX. These are essentially plain ZIP
files with a small amount of metadata, except that installation is handled
by the operating system. They are always extracted to a fixed location,
accessible to all users but not modifiable by any, and automatically updated
to the latest release. User's own data is stored in an OS-managed location in
their user profile, and is able to be reset, backed-up and restored using
regular OS functionality.

Nuget Package
-------------

The Nuget packages for CPython are produced and published as part of our
normal release process. The contents are identical to the traditional
installer. A Nuget package is published to nuget.org, which is a package
manager typically associated with .NET languages, but highly integrated with
any project supported by Visual Studio. This makes it a nice format for users
who want a lightweight install of Python as part of their regular build process,
and can simplify embedding scenarios.

The packages are installed using any tool capable of using the Nuget API, or
may be downloaded directly once the URL of the package is known. The package is
a plain ZIP file with some metadata. It contains the CPython interpreter, the
standard library, development headers and import libraries, and pip. It does
not execute any code at install time, and users must locate the package
themselves in order to launch the ``python.exe`` contained within.

Embeddable Distro
-----------------

The embeddable distro for CPython is produced and published as part of our
normal release process. It is published to python.org alongside the
traditional installer. The contents are identical, however, the layout is
changed to store all binaries at the top level, with the standard library
packed into a ZIP file. A ``._pth`` file is included to override ``sys.path``
so that only the files that are part of the distro are used, and environment
variables or registry entries are ignored.

This package does not include pip, as the intention is for it to be embedded
into a broader application. Other libraries should be installed at build time,
but after distribution, the runtime is meant as an internal implementation
detail of the app it is part of.

Challenges
----------

There are numerous challenges we face with the current set of installers,
which largely break down into two categories: mismatched or unachievable 
user expectations, and general unreliability.

The traditional installer has the highest level of unreliability. The Windows
Installer technology is very old, and effectively no longer under development.
While its basic functionality is okay, interference may come from many sources,
such as virus scanners, other installers, system configuration, admin policies,
and even other files in the same directory as the installer. On top of this,
most of its advanced and beneficial functionality such as update patches,
incremental updates, and automatic rollback are unimportant for Python users.

Most user expectations are _defined_ by the traditional installer, and so by
definition, it meets them. One primary gap is that it is not able to create an
"unmanaged" install - that is, the equivalent of only copying files onto the
user's system without registration. If you have installed it once, and you
try to install it again, you will only even be able to manage (or upgrade) the
existing install. This can lead to installs moving on update, which will
break users.

Additionally, the ``PATH`` environment variable cannot be intelligently
modified - at best, we can prepend or append the install path. This usually
results in the most recent install of Python being the highest priority. For
example, if the user has Python 3.14 installed and then installs (or updates)
3.13, the ``python`` command will switch from the later version to the earlier
version.

The ``py.exe`` launcher, defined in PEP 397 and implicitly updated by PEP 514,
is an attempt to avoid this particular issue. It uses its own logic for finding
installed versions without relying on ``PATH``. However, the PEP 514 logic does
not allow for prerelease or experimental builds to be treated specially, and so
``py.exe`` often prefers these builds by default over the non-experimental
version expected by the user.

The Windows Store package is very reliable, with the exception of the global
shortcuts. Rather than modifying ``PATH`` to add its own directory, these
shortcuts are created in a single OS managed directory that has all the
shortcuts defined by any app. Users are able to modify their ``PATH`` to exclude
or de-prioritise this directory, leading to unreliable or inconsistent
behaviour, and historically we have also seen this be caused by installers.
For example, installing Python from the Store followed by Python from the
traditional installer with its ``PATH`` modification enabled will almost always
shadow the Store package's Python with the later install.

User expectations that are un-met by the Store package tend to be performance
and technical. Due to the overhead of launching an app, Python starts up slower.
Because apps are designed to be isolated from each other, it is more difficult
to use hidden directories (such as ``AppData`` or ``TEMP``) to communicate
between different versions of Python, as each version has its own space. Apps
are subject to stricter security requirements that legacy applications start
disabled, such as DLL hijacking protection, which causes some libraries to fail.
The ``python3`` and ``python`` shortcuts are managed through system settings,
and the user interface is not very good (and not going to be improved, according
to Microsoft). Without managing these, it is relatively easy for an undesired
version to be launched, though in general the targets can only be changed
manually by the user, and not by merely installing another app.

Both the Nuget package and the embeddable distro are as simple and reliable to
install as extracting an archive file, though it's worth noting that for many
Python users this is not a common task. They provide no install management at
all, and cannot be reliably updated other than by deleting and re-extracting.
User expectations that are un-met are almost always due to users selecting the
wrong installer. Both these packages are for specialised cases, and while they
are documented as such, the attraction of a plain ZIP file leads some users to
failure.

Overview of PyManager
=====================

("PyManager" name open for bikeshedding)

PyManager is the internal name of our proposed replacement installer. It will
be distributed in the Windows Store, as well as on python.org as an MSIX
package. Downloading from either source will get an identical package, and
both will support automatic updates from the Store when new releases are made.

The user visible name will be "Python Install Manager", published by the
Python Software Foundation. After publishing, we will request that Microsoft
adjust their ``python.exe`` stub to open to this new app.

Our primary scenario to address is the user who has a clean Windows install,
who types ``python`` at the terminal, expecting to start an interactive
session. We choose this scenario because it requires the least amount of prior
knowledge, and we aim to make the user successful without having to seek advice.

When our user executes ``python``, they will launch Microsoft's redirector, that
opens to our Store page. The app is available for free, so the user can click
the very prominent "Get" button, which will download and install the app. They
then return to the terminal and re-run their previous command.

The ``python`` command has now been replaced by our own, part of the PyManager
app, with the ability to download, install and execute runtimes on-demand.
As the user has not specified a specific command, nor have they requested a
particular version, the command reads the latest available version from a feed
hosted on python.org, downloads, installs, and then launches the interpreter.

Later, the user runs an existing script containing a ``#! /usr/bin/python3.12``
shebang line. The command reads the intended target from the command and looks
for an existing install providing that command. Not finding one already
installed, but finding it in the online feed, we ask the user whether to
install it. If the user says yes, it gets installed and the script is run
with the correct version. If not, the script is run with the default version,
even though it doesn't match the shebang.

> It's worth remembering that Windows does not natively process shebang lines;
> we offer it as compatibility emulation, but if we don't process it then nobody
> will.

When the user decides they have had enough of Python, they open the system list
of installed applications, find "Python Install Manager" and remove it. This
cleans up all installs and temporary files, though it leaves any files outside
of its own install, including virtual environments.

> More specific install and uninstall commands are described below.
> This example only covers the case of a user with no additional information.


PyManage.exe Commands
---------------------

The default behaviour of launching the console app is to execute the default
Python interpreter. Unless overridden, this will be the highest version,
non-prerelease, non-experimental runtime.

As with the ``py.exe`` launcher, the first argument may be used to specify a
preferred version, either as an option starting with ``-3`` or ``-V:``.
The value following ``-V:`` is a ``Company\\Tag`` pair, as defined in PEP 514,
where either part may be omitted. If no slash is found, the text is assumed to
be a tag belonging to ``PythonCore``, that is, official distributions from the
upstream project. An option beginning with ``-3``, such as ``-3.13-arm64`` is
also interpreted as a tag belonging to ``PythonCore``.

> In this document, all command line options will be shown with one or two
> hyphens. In implementation, all options will support one or two hyphens or a
> forward slash, to be consistent with both Windows and UNIX conventions.

As an alternative to the version specification, one of the following subcommands
may be used. These must be the first argument, and must be spelled exactly, or
else they will be passed to a Python runtime as a filename. (See Backwards
Compatibility.)

Subcommands are shown here under the ``python`` command. Alternate names are
discussed in Specification.


Install subcommand
------------------

```
python install [--force] [--upgrade] [--source <URL>] [--target <DIR>] [tag ...]
```

This subcommand will install one or more runtimes onto the current machine.
The tags are ``Company\\Tag`` pairs (or just ``Tag`` if no slash is included),
are are used for a PEP 514 compatible search of the index file.

The default index file is hosted on python.org, and contains install information
including package URLs and hashes for all installable versions. An alternate
index may be specified by the user or their administrator (see Configuration
below). Entries in the index file list the full tags they should be installed
for, and if an exact match is found the package will be selected. In the case
of no exact match, a prefix match will be used. In both cases, numbers in the
tag are treated logically - that is, ``3.1`` is a prefix of ``3.1.2`` but not of
``3.10``.

If a tag is already satisfied by an existing install, nothing will be installed.
The user must pass an ``--upgrade`` or ``--force`` option to replace the
existing install.

Calling the command without providing any tags will refresh all installs, such
as regenerating metadata or shortcuts. Passing ``--upgrade`` with no tags will
attempt to replace all installs with newer compatible versions, though as this
may be destructive we reserve the right to disable this command and require tags
be listed explicitly.

If a ``--target <DIR>`` option is passed with only a single tag, that runtime
will be extracted to the specified directory without being registered as an
install. This is intended to cover embedding cases, or downloading the files for
incompatible platforms. Passing multiple tags with ``--target`` is an error.

TODO: Some kind of --list or --search option?


Uninstall subcommand
--------------------

```
python uninstall [--yes] [--purge] [tag ...]
```

This subcommand will uninstall one or more runtimes on the current machine. Tags
are exactly as for the install command, including prefix matching, but only
inspect existing installs. Unless the ``--yes`` option is passed, the user will
be prompted before uninstalling each runtime.

If the ``--purge`` option is passed with no tags, then (after confirmation) all
runtimes will be removed, along with shortcuts and any cached files.


List subcommand
---------------

```
python list [--format <FMT>] [-1] [tag ...]
```

This subcommand will list any or all installs matching the specified tags. If
no tags are provided, lists all installs. If ``-1`` is provided, only lists the
first result.

The default format is user-friendly. Other formats will include machine-readable
and single string formats (e.g. ``--format=prefix`` simply prints ``sys.prefix``
on a line by itself). The exact list of formats is left to implementation.


Help subcommand
---------------

```
python help <TOPIC>
```

This subcommand will open the online Python documentation to a search results
page for the topic. Normal command-line parsing is ignored following the
subcommand, so that (provided the process launched), queries can be typed
directly without being misinterpreted by quoting rules.

If no topic is specified, opens the PyManager documentation, which is local to
the app and does not require network access.

Handling the risk of command injection into a browser is an exercise left to the
implementation.


Replacing other installers
--------------------------

Our intent is to immediately stop publishing individual versions to the Windows
Store, and to deprecate and phase out the traditional installer and Nuget
packages over a period of time (TBD). The embeddable distro would remain, but
its listing on python.org download pages would be phased out and it would be
available only through PyManager.

PyManager can be made available as an app package downloadable manually from
python.org, and the double-click install experience is generally smooth.
We can also make it available as a trivial MSI, with no user interface or
options, to enable some automated deployment scenarios that do not work with the
newer technology. This MSI would be discouraged for most users, but would be
listed on python.org download pages.

It's worth noting that there is no way to make the MSI install fully compatible
with a Store install, and users with both will likely encounter confusion or
problems. However, denying them the option is overall worse.

Our release processes will start publishing plain ZIP packages to python.org.
These will be available from the FTP pages, but will not be listed directly on
regular download pages.

Third-party tools that currently distribute their own builds of CPython will be
welcome to use ours. Officially, they will only be supported when installing
using PyManager, though there is no intent to prevent anyone from using our
index directly unless genuine abuse is detected.


Project ownership and development
---------------------------------

PyManager will be developed and maintained in its own repository adjacent to
the CPython repository, and under the same terms. The CPython CLA will apply,
and all (and only) core developers will have commit rights.

PyManager releases are independent from CPython releases. There is no need for
versions to match, or releases to be simultaneous. Unless otherwise arranged,
the PyManager release manager is whoever is the build manager for Windows.


Rationale
=========

TODO: What other decisions are controversial enough to need explicit rationales?


The python.exe command
----------------------

Adding additional functionality to the ``python.exe`` alias exposed by PyManager
is a critical factor in enabling users to succeed without having to seek out
additional resources. Users already know to launch ``python.exe`` under that
name, and have likely obtained PyManager by doing so. Their next step will be
to launch the same command, expecting sensible behaviour, and this is how we can
provide that.

We are not proposing modifying the default ``Programs/python.c`` and thereby
affecting all builds of CPython. The program contained in PyManager will be in
an entirely separate repository - it's only an alias, and only for the case
where a user has installed PyManager from the Windows Store.


Interaction with venv
---------------------

An activated virtual environment, as implemented by the standard library
``venv`` module, will modify the user's ``PATH`` environment variable to ensure
that the venv launcher will take precedence over other executables. As a result,
when a venv has been activated, PyManager can only be launched by its aliases
other than ``python``.

This means that virtual environments will behave correctly with no additional
support from PyManager.

Based on experience with the ``py.exe`` launcher, where it was found that users
expected ``py`` to launch an active virtual environment, we would argue that
PyManager as proposed only behaves correctly _because_ it uses ``python`` as the
main alias. This choice allows other aliases to explicitly ignore an active
environment, because the preferred alias will use it as intended.

Were we to change the decision to use ``python`` as the primary alias, we would
have to design and implement interaction modes that enable PyManager to find and
use virtual environments, including those that are not created or managed by
PyManager itself. This is a significant expansion of scope, and carries
significant risk, as the current proposal is entirely constrained to PyManager
being aware of and responsible for all of its installs.


Specification
=============


Global Aliases
--------------

PyManager is a console-only application, though the possibility of a GUI being
added is left open for future work.

It provides a single application, `PyManager.exe`, with multiple global aliases
as well as a windowed version `PywManager.exe` that is identical but does not
create a console.

The following aliases are created:

* ``PyManager.exe`` - the full name should be an alias, for disambiguation in
  any context.
* ``python.exe`` - the command expected by most users
* ``pyx.exe`` - in testing, a shorter name was found to be useful
* ``PywManager.exe`` - same executable without forcing a console
* ``pythonw.exe`` - same executable without forcing a console

The windowed versions are only able to launch existing installs, and will simply
fail if no suitable install is found. The explicit management commands will
work, allowing silent installs.

The use of ``python.exe`` as a global alias, despite this command being more
functional than a typical runtime, is essential for the smooth flow of a user
coming to Python with limited information about how to use it. Advanced users
are able to disable this alias if desired, though would more likely prefer to
simply avoid it by using the other entry points described in later sections.

Start Menu Shortcuts
--------------------

A Start Menu shortcut will be added to launch PyManager documentation in the
user's default web browser. No applications are added to the Start Menu.

Environment Variables
---------------------

No environment variables can be updated automatically when installing a Store
app, and so no updates will be done automatically. The core commands should
already be available on a correctly functioning machine.

One directory within the user's install of PyManager is set aside for generated
aliases. If desired, the user can add this directory to their ``PATH``
themselves. The contents of this directory will be managed by PyManager, and
will contain executables to directly launch installed runtimes (for example,
``python3.exe`` and ``python3.13.exe`` for an install of Python 3.13). Whenever
aliases are added to this directory, ``PATH`` will be checked and if it is
missing, the user will be presented a message containing the path to add.

Scripts installed by packages installed into a runtime will be in yet another
directory. Due to the current design, we do not believe it is safe to have them
all install into a single directory, or a directory shared by multiple runtimes.
However, a future development may include a command for PyManager to generate
its own entry points based on metadata in installed packages.

Configuration
-------------

PyManager may be configured using a hierarchy of JSON-based configuration files.
Command line options always override configuration file options. Configuration
files in user editable locations may be disabled by a configuration or
command-line option.

In ascending order of priority, these will be located:

* within the app package
* under an admin-only location (TBD)
* under ``%AppData%\\Python\\PyManager``
* specified with the ``-c`` command line option

The specific behaviour of each configuration option is left to implementation.
However, a number of intended options are discussed in other sections.

Index Schema
------------

The index file is made available either online or locally, and provides
PyManager with all the information needed to find, select, install, and manage
any Python runtime.

The index is stored as JSON. The main top level key is ``versions``, which
contains a list of objects. Each version object has its own schema version, and
there is no overall file schema version. Future changes may add additional
top-level keys to provide functionality that cannot be safely integrated into
an existing one.

A second top-level key ``next`` contains an optional URL to another index. This
may be used if PyManager cannot find a suitable package in the included
versions. The intent is to allow for older indexes to be archived and only
accessed when required, reducing the size of the initial download without
cutting off users from older versions.

The initial schema is shown below.

```
SCHEMA = {
    "versions": [
        {
            # Should be 1.
            "schema": int,

            # Unique ID used for install detection/side-by-side.
            # Must be valid as a filename.
            "id": str,

            # Name to display in the UI
            "displayName": str,

            # Version used to sort packages. Also determines prerelease status.
            # Should follow Python's format, but is only compared among releases
            # with the same Company.
            "sort-version": Version,

            # Company field, used for filtering and displayed as the publisher.
            "company": str,

            # Default tag, mainly for UI purposes.
            # It should also be specified in 'install-for' and 'run-for'.
            "tag": str,

            # List of tags to install this package for. This does not have to be
            # unique across all installs; the first match will be selected.
            "install-for": [str],

            # List of tags to run this package for. Does not have to be unique
            # across all installs; the first match will be selected. The target
            # is the executable path relative to the root of the archive.
            "run-for": [{"tag": str, "target": str}, ...],

            # List of global CLI aliases to create for this package. Does not
            # have to be unique across all installs; the first match will be
            # created.
            "alias": [{"name": str, "target": str, "windowed": int}, ...],

            # List of shortcuts to create for this package. Additional keys on
            # each instance are allowed based on the value of 'kind'.
            # At present, no values of 'kind' are defined, and so this key
            # should be empty or omitted.
            # TODO: Define 'registry' kind to create PEP 514 compatible entries
            "shortcuts": [{"kind": str, "name": str, "target": str}, ...]

            # Default executable path, relative to the root of the archive
            "executable": str,

            # URL to download the package archive from
            "url": str,

            # Optional set of hashes to validate the download. Hashes are stored
            # as hex digests. Any hash supported by hashlib without OpenSSL is
            # permitted.
            "hash": {
                "<hash_name>": str,
            }
        }
    ],

    # URL to the next index file
    "next": str,
}
```

Inline Script Metadata
----------------------

PEP 723 introduced inline script metadata, a structured comment intended for
third-party tools to interpret and then launch a Python script in the correct
environment. An example taken from that PEP:

```
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests<3",
#   "rich",
# ]
# ///
```

PyManager has no integrated support for installing dependencies, and does not
propose adding any. However, we can make use of the ``requires-python`` value
when present (and not overridden on the command line) to select a suitable
runtime for the script.

While the example above uses a minimum version constraint, we expect the more
valuable scenario to be when a specific runtime version is requested. This would
result in a trivial ``python my-script.py`` being able to select the intended
runtime automatically.

Future work may include adding an additional subcommand to use built-in tools
to create temporary virtual environments and install dependencies. This is not
being proposed at this time.


Shebang Processing
------------------

For limited compatibility with scripts designed for sh-like shells, PyManager
will check scripts for a shebang line. A shebang line specifying a Python
command will be used (when not overridden on the command line) to select a
suitable runtime for the script.

Unlike the support currently in the ``py.exe`` launcher, we propose to reduce
this functionality to only support Python commands where the command matches
a global alias listed for an install. (The existing launcher is able to run any
executable, and attempts to extract version information from the command, rather
than simple matching.)

The specific patterns to be detected are left to the implementation.


Backwards Compatibility
=======================

Unfortunately, due to the existing situation, there is no way to make any change
to installation without requiring users to make changes to their systems. These
are quite reasonably seen as compatibility breaks, although we have never
promised compatibility between installers and certainly not between different
major versions.

Python versions prior to the first release of PyManager can be backfilled into
the python.org index, either based on newly repackaged archives or using the
almost equivalent packages from Nuget (the latter does not include Tcl/Tk,
making them significantly incompatible for some users, but this is likely okay
for especially old versions).

Users who currently rely on the traditional installer will find themselves
having to switch to a significantly different workflow. This will particularly
impact those who have scripted downloads and installs. The deprecation period
of two releases will allow time to transition, and the traditional installer
will have additional output and warnings added to direct users to the newer
options.

Users currently using Store packages are already manually installing each
version, as there is no predictable way to adopt new versions. One potentially
significant change is that Python through PyManager will not launch with an
app identity (TODO: link to MSFT docs), which may cause some OS functionality to
fail. This functionality would already have failed under any other installer, so
it is considered unlikely that users who rely on it will be broken by surprise.
If necessary, newer OS APIs may allow us to enable an app identity for new
releases, although this would be a change to CPython itself and not to the
installer.

Users currently using Nuget packages will also have to change to a new workflow.
Further investigation is required to determine how best to support this, as it
is possible that the PyManager MSIX package may not be installable on all
continuous integration systems. No differences are anticipated between a package
installed by PyManager compared to one installed by Nuget.

Users using the embeddable distro may have to change to a new method for
discovering the URL to the packages, though the recommendation would be to use
PyManager to discover and install. No differences are anticipated due to the
change of installer, and the embeddable distro package would be identical to
today.

Security Implications
=====================

TODO (but in short, no worse than the traditional installer's default settings)


How to Teach This
=================

As covered earlier, a central goal of this proposal is that "type 'python' in
your terminal" will be sufficient instruction for the most basic cases. Thanks
to the redirector added by Microsoft, following this instruction will at least
result in something useful happening, and with PyManager we can ensure that
"something useful" means that the user is running the latest version.

To explain what is actually happening, we propose the following as introductory
text:

Python is managed using an installer tool, known as PyManager. After this tool
is installed, you can run ``python`` to launch the interpreter, and it will
choose the best version already installed, available online, or referenced by
the script you are launching (if any). If you have a preference for a particular
version, you can specify it with ``python -V:<version>`` followed by the rest of
your command.

To install a version of Python without running any command, use ``python install
<version>``. You can see all of your installs with ``python list`` and remove
them with ``python uninstall <version>``. Add ``-?`` to any of these commands to
see all the options that are available.

Because each version of Python will be shared by all your projects, we recommend
using virtual environments. This will usually be created for a particular Python
version by running ``python -V:<version> -m venv .venv``, and activated with
``.venv\Scripts\Activate``. Now, rather than the install manager, ``python``
will always launch your virtual environment, and any packages you install are
only available while this environment is active. To get access to the manager
again, you can ``deactivate`` the environment, or use ``py-manage <command>``.


Reference Implementation
========================

The reference implementation is available at https://github.com/zooba/pymanager/
with a precompiled MSIX package under the Releases at
https://github.com/zooba/pymanager/releases. This sample includes a bundled
index, rather than a hosted one, and references a range of existing Nuget
packages to allow install testing.


Rejected Ideas
==============

[Why certain ideas that were brought while discussing this PEP were not ultimately pursued.]


Open Issues
===========

[Any points that are still being decided/discussed.]


Footnotes
=========

[A collection of footnotes cited in the PEP, and a place to list non-inline hyperlink targets.]


Copyright
=========

This document is placed in the public domain or under the
CC0-1.0-Universal license, whichever is more permissive.
