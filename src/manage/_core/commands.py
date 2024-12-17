import json
import logging
import os
import sys

from pathlib import Path

from .config import load_config, config_append, config_bool
from .exceptions import ArgumentError
from .logging import LOGGER

COMMANDS = {}

"""
Command-line arguments are defined in CLI_SCHEMA as a mapping from argument
name to a tuple containing the attribute name and the value to assign when the
argument is provided. The special _NEXT value indicates to read the assigned
value from the next argument (separated by a space, a colon or an equals sign).

Subcommands are included as dicts with subcommand-specific arguments, and are
also defined as subclasses of BaseCommand. Arguments should have default values
set on the class, and a CMD variable containing the subcommand name.

class ExampleCommand(BaseCommand):
    CMD = "example"
    attr = False # default value

    def execute(self):
        ...

CLI_SCHEMA = {
    "example": {
        # passing -a, /a, etc. sets attr=True
        "a": ("attr", True),
        # passing -attr:123, /attr=123, --attr 123, etc. sets attr='123'
        "attr": ("attr", _NEXT),
    }
}

Supported values from configuration files are defined in CONFIG_SCHEMA as a
recursive dict (to match JSON structure). The schema values are tuples of the
value type, an optional merge function, and zero or more additional options.

CONFIG_SCHEMA = {
    "attribute_name": (value_type, merge, ...),
    "command": {
        "command_specific_attribute_name": ...
    }
}

The type is a callable to coerce the value into the correct type - it will not
be used in isinstance() checks.

The merge function takes the existing value and the new value and returns the
value to store. If None, the new value always overwrites any existing value.
This is used when loading multiple configuration files.

Each option is a string literal to enable special processing:
* 'env' to expand %ENVIRONMENT% variables in strings before conversion
* 'path' to make a Path object, resolved against the config file's location
* 'uri' to call 'as_uri()' (so it chains with 'path'), and ensure the argument
  is vaguely URI-shaped and minimally exploitable.

Arguments passed on the command line always override any config files.
"""

_NEXT = object()

CLI_SCHEMA = {
    "v": ("log_level", logging.INFO),
    "vv": ("log_level", logging.DEBUG),
    "verbose": ("log_level", logging.INFO),
    "q": ("log_level", logging.WARN),
    "qq": ("log_level", logging.CRITICAL),
    "quiet": ("log_level", logging.WARN),
    "config": ("config_file", _NEXT),
    "y": ("confirm", False),
    "yes": ("confirm", False),
    "?": ("show_help", True),
    "h": ("show_help", True),

    "list": {
        "f": ("format", _NEXT),
        "format": ("format", _NEXT),
        "one": ("one", True),
        "1": ("one", True),
    },

    "install": {
        "s": ("source", _NEXT),
        "source": ("source", _NEXT),
        "t": ("target", _NEXT),
        "target": ("target", _NEXT),
        "f": ("force", True),
        "force": ("force", True),
        "dry-run": ("dry_run", True),
        # Set when the manager is doing an automatic install.
        # Generally wouldn't be set by a manual invocation.
        "automatic": ("automatic", True),
    },

    "uninstall": {
        "purge": ("purge", True),
    },
}


CONFIG_SCHEMA = {
    # Not meant for users to specify, but to track which files were loaded
    "config_files": (str, config_append, "path"),

    "log_level": (int, min),
    "confirm": (config_bool, None, "env"),
    "install_dir": (str, None, "env", "path"),
    "global_dir": (str, None, "env", "path"),
    "download_dir": (str, None, "env", "path"),

    "default_tag": (str, None, "env"),

    # Overrides for launcher executables. Not expected to be commonly used
    "launcher_exe": (str, None, "path"),
    "launcherw_exe": (str, None, "path"),

    "list": {
        "format": (str, None, "env"),
    },

    "install": {
        "source": (str, None, "env", "path", "uri"),
    },
}


def _default_launcher_exe():
    from importlib.resources import files
    exe = Path(files("manage") / "launcher.exe")
    if not exe.is_file():
        LOGGER.warn("Launcher not found at %s", exe)
    return exe


def _default_launcherw_exe():
    from importlib.resources import files
    exe = Path(files("manage") / "launcherw.exe")
    if not exe.is_file():
        LOGGER.warn("Launcher not found at %s", exe)
    return exe


class BaseCommand:
    log_level = logging.INFO
    config_file = None
    confirm = True

    root = None
    download_dir = None
    global_dir = None
    install_dir = None

    launcher_exe = None
    launcherw_exe = None

    default_tag = "3"

    show_help = False

    def __init__(self, args, root=None):
        cmd_args = {
            k: v for k, v in
            [*CLI_SCHEMA.items(), *CLI_SCHEMA.get(self.CMD, {}).items()]
            if not isinstance(v, dict)
        }
        set_next = None
        seen_cmd = False
        _set_args = set()
        self.args = []
        for a in args:
            if set_next:
                setattr(self, set_next, a)
                _set_args.add(set_next)
                set_next = None
            elif a.startswith(("-", "/")):
                a, sep, v = a.partition(":")
                if not sep:
                    a, sep, v = a.partition("=")
                try:
                    key, value, *opts = cmd_args[a.lstrip("-/").lower()]
                except LookupError:
                    raise ArgumentError(f"Unexpected argument: {a}")
                if value is _NEXT:
                    if sep:
                        setattr(self, key, v)
                        _set_args.add(key)
                    else:
                        set_next = key
                else:
                    setattr(self, key, value)
                    _set_args.add(key)
            elif not seen_cmd:
                if a.lower() != self.CMD:
                    raise ArgumentError(f"expected '{self.CMD}' command, not '{a}'")
                seen_cmd = True
            else:
                self.args.append(a)

        # Apply log_level from the command line first, so that config loading
        # is logged if desired.
        LOGGER.setLevel(self.log_level)

        LOGGER.debug("Arguments: %r", self.args)
        LOGGER.debug("Options: %r", {a: getattr(self, a) for a in {a[0] for a in cmd_args.values()}})

        self.root = Path(root or self.root or sys.prefix)
        try:
            config = load_config(self.root, self.config_file, CONFIG_SCHEMA)
        except Exception as ex:
            LOGGER.warn("Failed to read configuration file from %s", self.config_file)
            raise

        LOGGER.debug("Config: %r", config)

        # Top-level arguments get updated manually from the config
        # (per-command config gets loaded automatically below)

        # Update log_level from config if the config file requested more output
        # than the command line did.
        new_log_level = config.get("log_level")
        if new_log_level is not None and new_log_level < self.log_level:
            self.log_level = new_log_level
            LOGGER.setLevel(self.log_level)

        # Update directories from configuration
        # (these are not available on the command line)
        self.root = config.get("root") or self.root
        self.install_dir = config.get("install_dir") or (self.root / "pkgs")
        self.global_dir = config.get("global_dir") or (self.root / "bin")
        self.download_dir = config.get("download_dir") or (self.root / "pkgs")

        self.default_tag = config.get("default_tag") or self.default_tag

        if not self.launcher_exe:
            self.launcher_exe = _default_launcher_exe()
        if not self.launcherw_exe:
            self.launcherw_exe = _default_launcherw_exe()

        # If our command has any config, load them to override anything that
        # wasn't set on the command line.
        try:
            cmd_config = config[self.CMD]
        except LookupError:
            pass
        else:
            arg_names = frozenset(a[0] for a in cmd_args.values())
            for k, v in cmd_config.items():
                if k in arg_names and k not in self._set_args:
                    setattr(self, k, v)
                    _set_args.add(k)


    def __init_subclass__(subcls):
        COMMANDS[subcls.CMD] = subcls

    def execute(self):
        raise NotImplementedError(f"'{type(self).__name__}' does not implement 'execute()'")

    def help(self):
        print("Python Manager $VERSION")
        print("$COPYRIGHT")
        print()
        print("Subcommands:")
        for cmd in sorted(COMMANDS):
            print("    {:<16} {}".format(cmd, getattr(COMMANDS[cmd], "HELP_LINE", "")))
        print()
        print("Global options:")
        print("    -v, --verbose    Increased output (log_level={})".format(logging.INFO))
        print("    -vv              Further increased output (log_level={})".format(logging.DEBUG))
        print("    -q, --quiet      Less output (log_level={})".format(logging.WARN))
        print("    -qq              Even less output (log_level={})".format(logging.CRITICAL))
        print("    -y, --yes        Always confirm prompts (confirm=False)")
        print("    --config=PATH    Override configuration with JSON file")
        print()


class ListCommand(BaseCommand):
    CMD = "list"
    HELP_LINE = "Shows all installed Python runtimes"

    format = "table"
    one = False

    def execute(self):
        from .list_command import execute
        execute(self)

    def help(self):
        super().help()
        print("List options:")
        print("    -f, --format=<table,json,jsonl,exe,prefix>")
        print("                     Specify output formatting (list.format=...)")
        print("    -1, --one        Only display first result")
        print("    <TAG>            Filter results (Company\\Tag format)")
        print()


class InstallCommand(BaseCommand):
    CMD = "install"
    HELP_LINE = "Download new Python runtimes"

    source = None
    target = None
    force = False
    dry_run = False
    automatic = False

    def __init__(self, args, root=None):
        super().__init__(args, root)

        if not self.source:
            from importlib.resources import files
            source = Path(files("manage") / "index.json")
            if not source.is_file():
                raise ArgumentError("No source feed specified.")
            self.source = source.as_uri()
        elif "://" not in self.source:
            try:
                self.source = Path(self.source).absolute().as_uri()
            except Exception as ex:
                print(ex)
                raise


    def execute(self):
        from .install_command import execute
        execute(self)

    def help(self):
        super().help()
        print("Install options:")
        print("    -s, --source=<URI>")
        print("                     Specify index.json to use (install.source=...)")
        print("    -t, --target=<PATH>")
        print("                     Extract runtime to location instead of installing")
        print("    -f, --force      Re-download and overwrite existing install")
        print("    --dry-run        Choose runtime but do not install")
        print("    <TAG> <TAG> ...  One or more tags to install (Company\\Tag format)")
        print("                     If omitted, only refreshes shortcuts for installed versions.")
        print()


class UninstallCommand(BaseCommand):
    CMD = "uninstall"
    HELP_LINE = "Remove runtimes from your machine"

    confirm = True
    purge = False

    def execute(self):
        from .uninstall_command import execute
        execute(self)

    def help(self):
        super().help()
        print("Uninstall options:")
        print("    --purge          Remove all runtimes, shortcuts, and cached files. Ignores tags.")
        print("    <TAG> <TAG> ...  One or more runtimes to uninstall (Company\\Tag format)")
        print()


#class RunCommand(BaseCommand):
#    CMD = "run"
#    HELP_LINE = "Launch a script in a dedicated environment"


class HelpCommand(BaseCommand):
    CMD = "help"
    HELP_LINE = "Open online documentation for the requested topics"

    # TODO: Help command
    #def execute(self):
    #    pass


def find_command(args, root):
    for a in args:
        try:
            cls = COMMANDS[a.lower()]
        except LookupError:
            continue

        return cls(args, root)
    raise LookupError("Failed to find command")


def show_help(args):
    for a in args:
        try:
            cls = COMMANDS[a.lower()]
        except LookupError:
            continue

        cls([cls.CMD, "-?"]).help()
        return
    BaseCommand().help()