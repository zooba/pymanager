```
PEP: TBD
Title: A Python Installation Manager for Windows
Author: Steve Dower
PEP-Delegate: TBD
Discussions-To: https://discuss.python.org/t/pre-pep-a-python-installation-manager-for-windows/74556
Status: Draft
Type: Standards Track
Topic: Release
Created: 12-12-2024
Python-Version: N/A
Post-History: 18-12-2024
Resolution: TBD
```


Abstract
========

Installation of the python.org Python distribution on Windows is complex.
There are three main approaches with roughly equivalent levels of user
experience, and yet all of these suffer from different limitations, including
failing to satisfy modern usage scenarios. This PEP proposes a design for
a single Windows install workflow tool that satisfies all the needs of the
existing installers for the platform, while avoiding most of their limitations,
and provides the core team with the ability to manage releases for many years
to come.


Background
==========

There are a large range of needs users may have that lead to them wanting
to install a Python runtime. Many, likely most, are interested in running
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

As well as the intended uses, it is understood that many users will (attempt to)
use the traditional installer for other scenarios, such as unregistered installs
and automated CI system installs. While better alternatives are available, they
are not as obvious, and the hope is that a future design would make these
scenarios easier.

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

Embeddable Package
------------------

The embeddable package for CPython is produced and published as part of our
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

As well as its intended use, some users attempt to use this package as a
development kit rather than a runtime package. This is believed to be due to
those users preferring to avoid "heavyweight" installers, and believing that
this package is intended to be a "portable" install (extract and run), likely
because it is the only ZIP file option listed on the python.org download pages
(speaking to the importance of clarity and limiting options on those pages).
It is hoped that a future installer design will avoid or limit this confusion.

Alternate Distributions
-----------------------

While outside of our purview as the core team, alternate distributions of Python
for Windows often use a project, workflow or environment-centric model for
installation of the runtime. By this, we mean that the tool is installed first,
and is used to create a working space that includes a runtime, as well as other
dependencies. Examples of these tools include conda and uv.

Two observations are worth making about these tools. Firstly, they are often
praised for being low impact, in that they usually don't install additional
entry points or files for the runtime, making the install fast and also isolated
to a single project. Secondly, their users often appreciate the ease of
selecting a particular version of a runtime, or alternatively, not having to
select at all because existing specifications (or constraints) can choose for
them.

These tools tend to meet many of the second set of expectations described above,
usually combining multiple tasks in a single command to reduce the cognitive
overhead of learning how to use and combine multiple commands.

It's also worth pointing out that the core team does not view these alternate
distributions as competitors to any upstream distribution. They are a
fundamental piece of how the open source ecosystem is intended to work. Our own
distributions are a convenience for those who choose to use them, as not all
scenarios are well served by a workflow tool or even a pre-built package.


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

Primary User Scenario
---------------------

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
preferred version, either as an option starting with ``-V:`` or ``-3``.
The value following ``-V:`` is a ``Company\\Tag`` pair, as defined in PEP 514,
where either part may be omitted. If no slash is found, the text is assumed to
be a tag belonging to ``PythonCore``, that is, official distributions from the
upstream project. An option beginning with ``-3``, such as ``-3.13-arm64`` is
also interpreted as a tag belonging to ``PythonCore``.

As a reminder, PEP 514 updates the generic identification for Python runtimes
from a basic ``x.y`` version to allow for distributors to specify their own
"Company". This can be any text, but is ideally easy to type, and unique enough
to avoid collisions. Anywhere we use "tag" as a placeholder in this PEP, a
``Company\\Tag`` pair is permitted unless a separate field for company is
available. The Company for python.org releases is ``PythonCore``, for
compatibility with the registry keys used by earlier releases.

> In this document, all command line options will be shown with one or two
> hyphens. In implementation, all options will support one or two hyphens or a
> forward slash, to be consistent with both Windows and UNIX conventions.

As an alternative to the version specification, one of the following subcommands
may be used. These must be the first argument, and must be spelled exactly, or
else they will be passed to a Python runtime as a filename. (See Backwards
Compatibility.)

Subcommands are shown here under the ``python`` command. Alternate names are
discussed in Specification. Alternatives to adding subcommands are discussed in
Rejected Ideas.


Install subcommand
------------------

```
python install [-s|--source <URL>] [-f|--force] [-u|--upgrade] [tag ...]
python install [-s|--source <URL>] [-t|--target <DIR>] [tag ...]
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

TODO: Install using version range rather than tag

If a tag is already satisfied by an existing install, nothing will be installed.
The user must pass an ``--upgrade`` or ``--force`` option to replace the
existing install; the former will only replace it with a newer version, while
the latter will remove and replace even with the same version.

Calling the command without providing any tags will refresh all installs, such
as regenerating metadata or shortcuts. Passing ``--upgrade`` with no tags is an
error.

If a ``--target <DIR>`` option is passed with only a single tag, that runtime
will be extracted to the specified directory without being registered as an
install (or generating aliases or shortcuts). This is intended to cover
embedding cases, or downloading the files for incompatible platforms. Passing
multiple tags with ``--target`` is an error.

TODO: Some kind of --list or --search option?


Uninstall subcommand
--------------------

```
python uninstall [-y|--yes] [--purge] [tag ...]
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
python list [-f|--format <FMT>] [-1|--one] [tag ...]
```

This subcommand will list any or all installs matching the specified tags. If
no tags are provided, lists all installs. If ``--one`` is provided, only lists
the first result.

The default format is user-friendly. Other formats will include machine-readable
and single string formats (e.g. ``--format=prefix`` simply prints ``sys.prefix``
on a line by itself). The exact list of formats is left to implementation.


(DROPPED) Help subcommand
-------------------------

> **Note: This idea is on its way to being dropped, but leaving the text in the
> draft for now in case it triggers any better ideas.**

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


Interaction with py.exe
-----------------------

The ``py.exe`` launcher exists to provide some of the functionality that will be
replicated by PyManager - specifically, the ability to launch an already
installed runtime. Despite its long history, the launcher does not seem to have
become the preferred method for most users, with many preferring the global
modifications to the ``PATH`` environment variable, and others requesting
additional commands ``python3.exe`` and ``python3.x.exe`` for alignment with
POSIX (which does not include a ``py`` command in standard distros).

When installing a runtime, PyManager will be able to generate a number of
aliases and shortcuts as defined by the install specification. One such shortcut
will be the registration details specified by PEP 514 and used by the ``py.exe``
launcher to locate installs. As a result, a runtime installed with PyManager
will be found and launched correctly by ``py.exe``.

Because PyManager provides some equivalent functionality to ``py.exe``, it may
be useful to provide ``py`` as an alias for PyManager. This allows users to
continue to use a familiar command while also having direct access to the new
functionality. Differences in shebang handling, configuration, and behaviour
inside active virtual environments may require some transition, and users may
prefer to retain the old ``py.exe``.

Due to how the existing ``py.exe`` launcher configures itself, and how the MSIX
package for PyManager is constrained, it is not possible for PyManager's ``py``
alias to override the launcher. As a result, users who install the launcher will
always find ``py`` resolving to the launcher. Ultimately, the only way to
resolve this in favour of PyManager is to uninstall the launcher.


Interaction with venv
---------------------

An activated virtual environment, as implemented by the standard library
``venv`` module, will modify the user's ``PATH`` environment variable to ensure
that the venv launcher will take precedence over other executables. As a result,
when a venv has been activated, PyManager can only be launched by its aliases
other than ``python``.

This means that virtual environments will behave as they do today with no
additional support from PyManager. It is possible that users may come to prefer
the richer PyManager interface over the limited venv interface, however, any
changes to that would have to occur in the ``venv`` module and be associated
with a CPython release. They are outside the scope of this PEP.

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


Interaction with existing installs
----------------------------------

As proposed, PyManager is not aware of existing Python installs, or those
installed by any other method. While it is technically possible to discover some
of them (specifically, those that follow PEP 514), it is not possible to provide
equivalent behaviour.

As users of existing installs are already able to use them, and the only
scenario where PyManager may interfere is when users have manually configured
their ``PATH`` environment to deprioritise the existing install, we believe that
no action is required here.

As many past versions of CPython for which we still have installers or binaries
available may be added to the official python.org feed, allowing users to
migrate all past installs to PyManager if they wish.

Future work may include commands or options to register existing installs with
PyManager. None are proposed for the initial release.


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

* ``python.exe`` - the command expected by most users
* ``PyManager.exe`` - the full name should be available as an alias, so that it
  can be accessed when ``python`` is overridden (e.g. virtual environments)
* ``py.exe`` - a short alias to mimic the existing launcher
* ``PywManager.exe`` - same executable without forcing a console
* ``pythonw.exe`` - same executable without forcing a console
* ``pyw.exe`` - same executable without forcing a console

The windowed versions are only able to launch existing installs, and will simply
fail if no suitable install is found. The explicit management commands will
work, allowing silent installs to be triggered by other applications, but will
not automatically install.

The use of ``python.exe`` as a global alias, despite this command being more
functional than a typical runtime, is essential for the smooth flow of a user
coming to Python with limited information about how to use it. Advanced users
are able to disable this alias if desired, though would more likely prefer to
simply avoid it by using the other entry points described in later sections.

Further discussion about the decision to use ``python.exe`` as a global alias
can be found in the Rejected Ideas section.


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

PyManager is configured using a hierarchy of JSON-based configuration files.
Command-line options always override configuration file options. Configuration
files in user editable locations may be disabled by a configuration or
command-line option.

In ascending order of priority, these will be located:

* within the app package
* specified by admin-only configuration (see below)
* under ``%AppData%\\Python\\PyManager``
* specified with the ``-c`` command line option

The specific behaviour of each configuration option is left to implementation.
However, a number of intended options are discussed in other sections.

App package configuration is provided to allow PyManager to be embedded in other
applications or packages. For example, an alternative distribution may want to
include PyManager but have it locate installs from their own index. The app
package configuration allows reusing our build and overriding the default
settings.

Admin-only configuration is provided to allow administrators to manage systems
under their control using existing tools, such as group policy or registry
updates. By design, these controls cannot be overridden, such that it is
possible for administrators to deploy policy that prevents or limits the use of
PyManager. These controls are essential to allow PyManager to be deployed safely
into certain environments, and without them, it would simply be disallowed and
those users would have no access to Python.

This admin-only configuration is primarily a path to a configuration file that
an administrator can deploy to any controlled location. Additional configuration
settings as needed for essential control may also be provided directly, rather
than requiring the use of the config file. For example, the option to disable
certain subcommands or override the default index may be provided to allow
simple restrictions without file deployments.


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

            # Specifies platforms to consider this package for.
            # Initially, 'win32' is the only supported value. Others may be
            # defined in the future. This condition is evaluated silently, and
            # is not intended to replace platform requests in "install-for".
            "platform": [str],

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
            # TODO: Define 'registry' kind to create PEP 514 entries
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

    # Full or partial URL to the next index file
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

Without doubt, enabling some subcommands on the default ``python.exe`` alias has
compatibility implications, specifically in that a small number of unusual
filenames will not be executable as scripts without additional arguments or
path qualification. These conditions are considered to be very rare compared to
alternative designs (see Rejected Ideas), to have acceptable workarounds, and to
only affect users who have knowingly changed their Python command by installing
the PyManager app from the Windows Store. Users who use the generated aliases or
virtual environments are entirely unimpacted. The anticipated benefit is that
the ``python`` command will remain useful and relevant (see the Primary User
Scenario above), whereas any alternative would result in the ``python`` command
behaving inconsistently and likely becoming generally discouraged.

Due to the existing installer situation, there is no way to make any change
to installation without requiring users to make changes to their systems. These
are quite reasonably seen as compatibility breaks, although we have never
promised compatibility between installers and certainly not between different
major versions. Users have always been responsible for installing new major
versions, and so there are no silent compatibility breaks here. Nothing changes
for a user until they choose to make a change.

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

In this section we compare the security implications of the installer itself to
the existing installers. The implications of Python being installed on a machine
are out of scope, and the ability of a malicious user to execute the installer
is also out of scope.

The typical risk introduced by an installer is that an elevated install may make
changes to a system that allow a low-privileged user to later affect a
high-privilege user. For example, by inappropriately setting access control on
shared folders. For PyManager, this risk only exists in the initial installation
of the manager itself. Once installer, the manager only operates as the same
privilege level as the user, and therefore cannot introduce any escalation path.

The proposed PyManager has two install options that are fundamentally
equivalent, with a third potential option that introduces some additional and
typically unnecessary risks.

The first two options are to download and install using the Microsoft Store app,
or to download and install the MSIX from python.org. In both of these cases,
the operating system is responsible for the actual install, as well as managing
sandboxing and isolation of the running application. The greatest risk here is
that a user installs the incorrect application, which may occur due to an
imitation page in the Store, or a fake download site containing another
installer. Users have the opportunity to verify the publisher before installing
any MSIX, and the publisher is verified cryptographically for a direct MSIX
install, and through third-party business verification for the Store.

The third potential install option is the trivial MSI described earlier in
"Replacing other installers". This installer would require running as a
high-privilege user in order to install into the Program Files directory and
modify the system ``PATH`` environment variable to include the installed
aliases. Each user has their own configuration and install location, including
the generated aliases, and so this installer does not affect any per-user
settings.

Hence, all files installed by the PyManager installers are restricted to either
Administrator or Trusted Installer, and all state, including installed runtimes,
are stored in per-user directories.

Once PyManager is installed on a machine, it is likely that a malicious user may
attempt to use it to install Python. The admin-only configuration described
earlier in "Configuration" is intended to control these scenarios. Ultimately,
though, an attacker is able to do whatever a user may do, and only a complete
application whitelisting approach can prevent the use of Python.

Runtime installs by PyManager are fully accessible by, and modifiable by, the
current user. This is equivalent to typical installs using the traditional
installer or a Nuget package, but is more vulnerable to tampering than a Store
install or a per-machine install with the traditional installer. It is not
possible to fully protect an install from the user who installed it, but it may
be valuable to consider removing modify permissions after install (though the
user may, of course, restore them). This at least increases the difficulty in
tampering.

The shortcuts generated by PyManager when installing a runtime are designed to
use a signed, unmodified executable that uses an adjacent data file to launch
the correct target. This can be easily abused to direct the launcher to launch
an alternative, however, the only way to resolve this would sacrifice the trust
in the executable itself, making it trivial to replace it instead of the data.
Such risk already exists, and is equivalent to replacing the script that a user
may launch, or any part of the standard library.

PyManager has no mechanism to perform a per-machine install. This may be useful
functionality to some users, as it would allow an install to be completely
unmodifiable by the regular user (excluding virtual environments and the user
site folders). Such functionality may be manually imitated by an administrator
using PyManager and other OS commands, but it is not considered a critical
workflow. The recommended alternative is for an administrator to provide
PyManager and override its configuration.

**TODO: More concerns?**


How to Teach This
=================

As covered earlier, a central goal of this proposal is that "type 'python' in
your terminal" will be sufficient instruction for the most basic cases. Thanks
to the redirector added by Microsoft, following this instruction will at least
result in something useful happening, and with PyManager we can ensure that
"something useful" means that the user is running the latest version.

To explain what is actually happening, we propose the following as introductory
text:

> Python is managed using an installer tool, known as PyManager. After this tool
> is installed, you can run ``python`` to launch the interpreter, and it will
> choose the best version already installed, available online, or referenced by
> the script you are launching (if any). If you have a preference for a
> particular version, you can specify it with ``python -V:<version>`` followed
> by the rest of your command.

> To install a version of Python without running any command, use ``python
> install <version>``. You can see all of your installs with ``python list`` and
> remove them with ``python uninstall <version>``. Add ``-?`` to any of these
> commands to see all the options that are available.

> Because each version of Python will be shared by all your projects, we
> recommend using virtual environments. This will usually be created for a
> particular Python version by running ``python -V:<version> -m venv .venv``,
> and activated with ``.venv\Scripts\Activate``. Now, rather than the install
> manager, ``python`` will always launch your virtual environment, and any
> packages you install are only available while this environment is active. To
> get access to the manager again, you can ``deactivate`` the environment, or
> use ``py-manage <command>``.

**TODO: When/how to teach indexes**

**TODO: When/how to teach configuration files**

**TODO: When/how to teach advanced deployment**

**TODO: How to update platform-generic documentation (e.g. on package READMEs)**

Reference Implementation
========================

The reference implementation is available at https://github.com/zooba/pymanager/
with a precompiled MSIX package under the Releases at
https://github.com/zooba/pymanager/releases. This sample includes a bundled
index, rather than a hosted one, and references a range of existing Nuget
packages to allow install testing.

Rejected Ideas
==============

Don't add subcommands to python.exe
-----------------------------------

Making ``python.exe`` an alias to the manager application is controversial, as
it involves a minor change to the familiar interface. However, it is this very
familiarity that makes it important that we provide it!

When the manager is installed, it cannot include a runtime that is ready to use
(see following rejected idea). As a result, there is no ``python.exe`` that can
be used. However, if no command is provided by that name, users will go from a
helpful prompt on first run to an opaque error on the second.

By making ``python.exe`` an alias for the manager app itself, and by making the
default behaviour of the manager be to install and/or launch the default version
of Python, we get the best combination of user friendly behaviours.
Additionally, because the manager can inspect scripts for inline metadata or
shebangs, we can continue to meet user expectations as their needs become more
advanced, and allowing the use of ``-V:<TAG>`` options ensures that the
``python`` command remains the ubiquitous method for launching Python.

The subcommands are a very limited set of names that are incredibly uncommon to
use as unadorned filenames on Windows. In practically every non-contrived
scenario, Python scripts use a ``.py`` extension, and ``install.py`` will not be
confused for the subcommand. Using a leading dot (``.\\install``) or any other
part of the path allows the rare use of an extensionless name to still be
invoked, and any command-line option preceding the subcommand at all will cause
it to be treated as a regular Python command (for example, ``python -s install``
will not use the subcommand).


Include a runtime pre-installed with the manager
------------------------------------------------

It is very important for stability and updates that runtime releases are
fully independent of the manager. Updating the manager should be possible
without affecting any existing runtime installs, and likewise there should be
no requirement to update the manager to get a newer runtime.

Hypothetically, if we were to include Python 3.14.0 with the manager such that
it did not need to be installed, it would be a breaking change to later replace
that with 3.15.0. As we only have a single install for the manager, this would
result in the newest installs getting the oldest runtime.

As a result, the best we can offer is to bundle the package of the latest
runtime, and extract from that on demand. Then a later update can replace the
pre-cached package without affecting an existing install. This approach,
however, does not provide a usable ``python.exe`` on first install, which is the
main reason we would want to consider it (see the previous rejected idea).


Use a built-in module rather than subcommands
---------------------------------------------

Two alternatives to using commands like ``python list`` or ``python install``
that have been proposed are to use either dedicated modules, invoked like
``python -m list`` and ``python -m install``, or a single dedicated module
invoked like ``python -m manage list``. This idea is rejected on the basis that
it attempts to reuse existing semantics for a scenario that cannot be reliably
implemented by those semantics, and so will require a special case that is
harder to explain, understand, and maintain.

The main reason this idea is rejected is due to the interaction of two otherwise
desirable semantics: first, that the default ``python`` command should launch
the latest available runtime as if it were launched directly; and second, that
the behaviour of ``-m`` should not be treated as a special case in some
circumstances. If the first part was dropped, we would freely modify the command
to behave as users expect - nobody would be raising compatibility concerns at
all if we were agreed to completely break compatibility. However, if the second
constraint were dropped, users would bear the burden of the ensuring confusion.
(We aren't proposing dropping either - this is a rejected idea, after all - but
it helps to illustrate what the options are.)

First, since one of the subcommands is intended to install your first runtime,
we cannot treat ``python -m [manage] install`` as if it is running through the
default runtime - there isn't one! It inherently requires special case handling
in order to read the command and execute it through a different program.

Additionally, Python allows other options to precede or mingle with the ``-m``,
which would have to be supported by this special case.

Finally, the semantics of the ``-m`` option include searching the initial
``sys.path`` for matching module names. This is a considerably more broad search
than a bare name. ``python -m install`` would gladly execute ``install.py``,
``install.pyc``, ``install.pyd``, ``install\\__init__.py``, and others after
searching a number of directories found by inspecting the file system, the
environment, the registry, as well as any transitively included paths found in
those. Compared to ``python install``, which would _only_ look for a file called
precisely ``install`` in the current working directory, the ``-m`` behaviour is
far more likely to be already relied upon by real scenarios. (For example,
Django projects typically have a ``manage.py`` script, meaning that ``python -m
manage`` would always behave incorrectly by some measure.)

Changing ``python -m install`` to *not* behave like ``-m``, but instead to
execute an internal command, is vastly more likely to break users than changing
``python install``. As such, this idea is rejected.


Use a new command-line option rather than subcommands
-----------------------------------------------------

A reasonable alternative to subcommands is to specify their names with leading
punctuation, like an option rather than a subcommand. For example, this may look
like ``python /install ...`` rather than ``python install``, or ``python
--list``. Because some of these are currently errors for a normal CPython
interpreter, they could be added without any backwards compatibility concern.

Notably, however, the typical Windows format of a leading slash is not an error
in CPython. Windows users therefore cannot directly transfer existing knowledge
and must learn a new way to specify options. As we are proposing a Windows
specific tool, this is a terrible start. Additionally, those users familiar with
Unix-style command lines will recognise the misuse of options as commands.

We desire to create a clean interface, and starting with a design that includes
obvious warts or learning challenges is counter to that goal. Modern tools
universally use subcommands for these purposes, and so the idea to use something
different is rejected.


Improving the current traditional installer instead
---------------------------------------------------

Rather than creating a new install mechanism, we could invest in maintaining the
current installer. At this stage, however, our current installer is based
entirely on retired technology. Windows is no longer developing the Windows
Installer service, and Wix are no longer improving the version of their toolset
that we use. Migrating to a newer Wix Toolset is a significant amount of work,
and ultimately still leaves us tied to old technologies.

As mentioned earlier, the most beneficial functionality provided by Windows
Installer is not used for CPython, and generally has caused more issues than it
has ever solved (for example, accidental downgrades due to automatically
collected file version information).

The implementation of the Burn bundle, which is our primary source of installer
logic, is in C++ and integrated into a framework that few core developers are
familiar with. This makes maintenance challenging, and is not a good long term
position to take. Migrating desired features such as registration-free installs
into the Burn bundle is not possible (without writing the end-to-end
reimplementation and integrating it as an afterthought).

Our view is that maintaining the current traditional installer is at least as
much effort as implementing a new installer, and would not provide meaningful
benefits for the core team or for our users. As such, this idea is rejected.


Delete the Store package completely
-----------------------------------

Removing the Store packages would reduce the number of options users face when
choosing a Python runtime. By all measures apart from reliability and security,
the traditional installer is entirely sufficient as a substitute. The effort to
migrate parts of the ecosystem to more secure settings (such as not relying on
DLL hijacking) has largely occurred, but some packages remain that still only
work with less secure configurations, and moving all users back to these
configurations would ensure that users of these packages would not face the
issues they face today.

However, the majority of users of the Store packages appear to have no
complaints. Anecdotally, they are often fully satisfied by the Store install,
and particularly appreciate the ease and reliability of installation. (And on a
personal note, this author has been using Store packages exclusively since
Python 3.8 with no blocking issues.)

The greatest number of issues have been caused by misconfigured ``PATH``
variables and the default ``python.exe`` redirector installed by Microsoft. In
other words, entirely unrelated to our own package (though sometimes related to
unresolvable issues in our traditional installer). For the sake of the high
number of successful installs through this path, we consider the burden of
diagnosing and assisting impacted users to be worthwhile, and consider the idea
to simply drop the Store package rejected.

That said, when PyManager is published to the Store, we would plan to delist all
existing runtimes on the Store to ensure users find the manager. This only
impacts new installs, and anyone who has previously installed a particular
version (even on another machine, if they were logged in) will be able to
continue to use and install those versions.


Rely on WinGet or equivalents
-----------------------------

WinGet, Chocolatey, and other similar tools are not installers in the sense that
we require. They use their own repository of metadata to download, validate, and
run installers. Without our own installer, they have nothing to run, and so
cannot be used.

It is possible that their metadata will not support installing PyManager and
then running it to install a particular runtime. If this is the case, they may
need to investigate using our binary packages directly.

Currently, none of these install tools are officially supported by CPython, and
so we have no obligation to make them work.


Just publish the plain ZIP file
-------------------------------

Publishing the plain ZIP file is part of the plan, however, it will not be
visibly listed (for example, on the python.org downloads pages, though they will
be visible in the FTP view). An alternative would be to publish and list these
packages, and expect users to download and manually extract and configure them.

Given the desirable workflows we see, we believe that most users do not want to
configure a Python install at all. Not only do they not want to choose the
install location, they do not want to choose a version, or even have to search
for a download provider or instructions. However, they do want to be able to
find an install later, launch, update or remove it, or list all known installs.

It is also worth recognising that there will be more ZIP files than are
currently listed on the Download pages, and so the list of files will become
longer. Choosing the correct download is already challenging for users (those
who bypass the primary "Download" button and view the list of all available
versions and then files), and we have no desire to make it more challenging.

The index protocol and download list will be available for tools that wish to
use it, or for users who are willing to navigate JSON in order to find the URL.
While these are not supported uses, there is no reason to prevent them. The
``--target`` option on the install command provides a download and extract
operation.


Only publish PyManager to one place
-----------------------------------

Whether the Windows Store or python.org, it would be viable to publish to only
one location.

However, users strongly expect to be able to download *something* from
python.org. If we were to remove any option at all, we would inevitably hurt our
users. Without an MSIX available on python.org, users have no way to transfer
the package to another machine, or to fully script the initial install of the
manager.

Many users rely on the Windows Store app to install packages, and the built-in
redirector in Windows can only open to a Store page. As such, removing the Store
app is equivalent to denying hundreds of thousands of installs each month.

Additionally, automatic updates are only supported through the Store. We would
have to implement automatic updates manually if we did not publish there. It is
possible to have the MSIX from python.org find its own updates on the Store, and
we can assume that machines without access are responsible for their own
updates.

The two builds are practically identical. The only difference between the MSIX
we provide to the Store and the one that goes to python.org is package signing:
we sign the python.org package ourselves, while the Store package is signed as
part of the publish process. Otherwise, there is no additional cost to producing
and publishing both packages.


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
