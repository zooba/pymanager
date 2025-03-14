import os
import sys

from . import __version__
from .config import (
    load_config,
    config_append,
    config_bool,
    config_split,
    config_split_append,
)
from .exceptions import ArgumentError
from .pathutils import Path

from . import logging
LOGGER = logging.LOGGER

COPYRIGHT = f"""Python installation manager {__version__}
Copyright (c) Python Software Foundation. All Rights Reserved.
"""


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
    "v": ("log_level", logging.VERBOSE),
    "vv": ("log_level", logging.DEBUG),
    "verbose": ("log_level", logging.VERBOSE),
    "q": ("log_level", logging.WARN),
    "qq": ("log_level", logging.ERROR),
    "quiet": ("log_level", logging.WARN),
    "config": ("config_file", _NEXT),
    "log": ("log_file", _NEXT),
    "y": ("confirm", False),
    "yes": ("confirm", False),
    "?": ("show_help", True),
    "h": ("show_help", True),

    "list": {
        "f": ("format", _NEXT),
        "format": ("format", _NEXT),
        "one": ("one", True),
        "1": ("one", True),
        "only-managed": ("unmanaged", False),
        "s": ("source", _NEXT),
        "source": ("source", _NEXT),
        "online": ("default_source", True),
    },

    "install": {
        "s": ("source", _NEXT),
        "source": ("source", _NEXT),
        "t": ("target", _NEXT),
        "target": ("target", _NEXT),
        "d": ("download", _NEXT),
        "download": ("download", _NEXT),
        "f": ("force", True),
        "force": ("force", True),
        "u": ("update", True),
        "update": ("update", True),
        "upgrade": ("update", True),
        "repair": ("repair", True),
        "refresh": ("refresh", True),
        "by-id": ("by_id", True),
        "dry-run": ("dry_run", True),
        "enable-shortcut-kinds": ("enable_shortcut_kinds", _NEXT, config_split),
        "disable-shortcut-kinds": ("disable_shortcut_kinds", _NEXT, config_split),
        # Set when the manager is doing an automatic install.
        # Generally won't be set by manual invocation
        "automatic": ("automatic", True),
        "from-script": ("from_script", _NEXT),
    },

    "uninstall": {
        "purge": ("purge", True),
        "by-id": ("by_id", True),
        # Undocumented aliases so that install and uninstall can be mirrored
        "f": ("confirm", False),
        "force": ("confirm", False),
    },
}


CONFIG_SCHEMA = {
    # Not meant for users to specify, but to track which files were loaded.
    # The base_config, user_config and additional_config options are for
    # configuration.
    "_config_files": (str, config_append, "path"),

    "log_level": (int, min),
    "confirm": (config_bool, None, "env"),
    "install_dir": (str, None, "env", "path"),
    "global_dir": (str, None, "env", "path"),
    "download_dir": (str, None, "env", "path"),
    "bundled_dir": (str, None, "env", "path"),
    "logs_dir": (str, None, "env", "path"),

    "default_tag": (str, None, "env"),
    "default_platform": (str, None, "env"),
    "automatic_install": (config_bool, None, "env"),
    "include_unmanaged": (config_bool, None, "env"),
    "shebang_can_run_anything": (config_bool, None, "env"),
    "shebang_can_run_anything_silently": (config_bool, None, "env"),
    # Typically configured to '%VIRTUAL_ENV%' to pick up the active environment
    "virtual_env": (str, None, "env", "path"),

    "list": {
        "format": (str, None, "env"),
        "unmanaged": (config_bool, None, "env"),
    },

    "install": {
        "source": (str, None, "env", "path", "uri"),
        "fallback_source": (str, None, "env", "path", "uri"),
        "enable_shortcut_kinds": (str, config_split_append),
        "disable_shortcut_kinds": (str, config_split_append),
    },

    # These configuration settings are intended for administrative override only
    # For example, if you are managing deployments that will use your own index
    # and/or your own builds.

    # Registry key containing configuration overrides. Each value specified
    # under this key will be applied to the configuration both before and after
    # all other configuration files (but not command-line options).
    # Default: HKEY_LOCAL_MACHINE\Software\Policies\Python\PyManager
    "registry_override_key": (str, None),

    # Specify a new base config file. This would normally be set in the registry
    # and will override earlier settings (including those in the registry).
    # The intent is to allow a registry override for just this one value to
    # reference a JSON file containing other admin overrides.
    "base_config": (str, None, "env", "path"),

    # Specify a user config file. This will normally use an environment variable
    # to locate the file under %UserProfile%.
    # Default: %AppData%\Python\PyManager.json
    "user_config": (str, None, "env", "path"),

    # Specify an additional config file. This would normally be a complete
    # environment variable to allow users to set this as they launch.
    # Default: %PYTHON_MANAGER_CONFIG%
    "additional_config": (str, None, "env", "path"),

    # Registry key to write PEP 514 entries into
    # Default: HKEY_CURRENT_USER\Software\Python
    "pep514_root": (str, None),

    # Directory to create Start shortcuts (Start Menu\Programs is assumed)
    # Default: Python
    "start_folder": (str, None),

    # Overrides for launcher executables
    # Default: .\launcher.exe and .\launcherw.exe
    "launcher_exe": (str, None, "path"),
    "launcherw_exe": (str, None, "path"),
}


# Will be filled in by BaseCommand.__init_subclass__
COMMANDS = {}


class BaseCommand:
    log_level = logging.INFO
    config_file = None
    confirm = True
    default_tag = None
    default_platform = None
    automatic_install = True
    include_unmanaged = True
    virtual_env = None
    shebang_can_run_anything = True
    shebang_can_run_anything_silently = False

    log_file = None
    _create_log_file = True
    keep_log = True
    _log_file = None

    root = None
    download_dir = None
    global_dir = None
    install_dir = None
    bundled_dir = None
    logs_dir = None

    pep514_root = None
    start_folder = None
    launcher_exe = None
    launcherw_exe = None

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
                key, value, *opts = cmd_args[set_next]
                if value is _NEXT and opts:
                    a = opts[0](a)
                setattr(self, key, a)
                _set_args.add(key)
                set_next = None
            elif not seen_cmd and a.lower() == self.CMD:
                # Check once to handle legacy commands with - prefix
                # Check again below to raise an error if the command was wrong
                seen_cmd = True
            elif a.startswith(("-", "/")):
                a, sep, v = a.partition(":")
                if not sep:
                    a, sep, v = a.partition("=")
                set_next = a.lstrip("-/").lower()
                try:
                    key, value, *opts = cmd_args[set_next]
                except LookupError:
                    raise ArgumentError(f"Unexpected argument: {a}")
                if value is _NEXT:
                    if sep:
                        if opts:
                            v = opts[0](v)
                        setattr(self, key, v)
                        _set_args.add(key)
                        set_next = None
                else:
                    setattr(self, key, value)
                    _set_args.add(key)
                    set_next = None
            elif not seen_cmd:
                if a.lower() != self.CMD:
                    raise ArgumentError(f"expected '{self.CMD}' command, not '{a}'")
                seen_cmd = True
            else:
                self.args.append(a)

        # Apply log_level from the command line first, so that config loading
        # is logged (if desired).
        LOGGER.reduce_level(self.log_level)

        self.root = Path(root or self.root or sys.prefix)
        try:
            config = load_config(self.root, self.config_file, CONFIG_SCHEMA)
        except Exception:
            LOGGER.warn("Failed to read configuration file from %s", self.config_file)
            raise

        # Top-level arguments get updated manually from the config
        # (per-command config gets loaded automatically below)

        # Update log_level from config if the config file requested more output
        # than the command line did.
        self.log_level = LOGGER.reduce_level(config.get("log_level"))

        # Update directories from configuration
        # (these are not available on the command line)
        self.root = config.get("root") or self.root
        _set_args.add("root")
        self.install_dir = self.root / "pkgs"
        self.global_dir = self.root / "bin"
        self.download_dir = self.root / "pkgs"
        self.logs_dir = None

        arg_names = frozenset(k for k, v in CONFIG_SCHEMA.items()
            if hasattr(type(self), k) and not isinstance(v, dict))
        for k, v in config.items():
            if isinstance(v, dict):
                continue
            if k in arg_names and k not in _set_args:
                setattr(self, k, v)
                _set_args.add(k)

        if not self.default_platform:
            # Currently, we always default to -64.
            self.default_platform = "-64"

        # If our command has any config, load them to override anything that
        # wasn't set on the command line.
        try:
            cmd_config = config[self.CMD]
        except (AttributeError, LookupError):
            pass
        else:
            arg_names = frozenset(CONFIG_SCHEMA[self.CMD])
            for k, v in cmd_config.items():
                if k in arg_names and k not in _set_args:
                    LOGGER.debug("Overriding command option %s with %r", k, v)
                    setattr(self, k, v)
                    _set_args.add(k)

        LOGGER.debug("Finished processing options for %s", self.CMD)


    def __init_subclass__(subcls):
        COMMANDS[subcls.CMD] = subcls

    def _get_one_argument_to_log(self, k):
        try:
            v = getattr(self, k)
        except AttributeError:
            return "<invalid option>"
        if isinstance(v, str) and v.casefold().startswith("http".casefold()):
            from .urlutils import sanitise_url
            return sanitise_url(v)
        return v

    def dump_arguments(self):
        try:
            arg_spec = CLI_SCHEMA[self.CMD]
        except LookupError:
            arg_spec = None
        else:
            LOGGER.debug("Command: %r", self.CMD)
        for k in sorted(set(k[0] for k in CLI_SCHEMA.values() if not isinstance(k, dict))):
            LOGGER.debug("Global option: %s = %s", k, self._get_one_argument_to_log(k))
        if arg_spec:
            for k in sorted(set(k[0] for k in arg_spec.values() if not isinstance(k, dict))):
                LOGGER.debug("Command option: %s = %s", k, self._get_one_argument_to_log(k))
            LOGGER.debug("Arguments: %r", self.args)

    def get_log_file(self):
        if not self._create_log_file:
            return None

        if self.log_file:
            self.keep_log = True
            return self.log_file

        if self._log_file:
            return self._log_file

        logs_dir = self.logs_dir
        if not logs_dir:
            logs_dir = Path(os.getenv("TMP") or os.getenv("TEMP") or os.getcwd())
        from _native import datetime_as_str
        self._log_file = logs_dir / "python_{}_{}_{}.log".format(
            self.CMD, datetime_as_str(), os.getpid()
        )
        return self._log_file

    def execute(self):
        raise NotImplementedError(f"'{type(self).__name__}' does not implement 'execute()'")

    @classmethod
    def subcommands_list(cls):
        cmd_help = [
            "    {:<16} {}".format(cmd, getattr(COMMANDS[cmd], "HELP_LINE", ""))
            for cmd in sorted(COMMANDS)
            if cmd[:1].isalpha()
        ]
        return fr"""
!G!Subcommands:!W!
{'\n'.join(cmd_help)}
""".lstrip().replace("\r\n", "\n")

    @classmethod
    def help_text(cls):
        return fr"""
!G!Global options:!W!
    -v, --verbose    Increased output (!B!log_level={logging.INFO}!W!)
    -vv              Further increased output (!B!log_level={logging.DEBUG}!W!)
    -q, --quiet      Less output (!B!log_level={logging.WARN}!W!)
    -qq              Even less output (!B!log_level={logging.ERROR}!W!)
    -y, --yes        Always confirm prompts (!B!confirm=false!W!)
    --config=!B!<PATH>!W!  Override configuration with JSON file
""".lstrip().replace("\r\n", "\n")

    def help(self):
        if type(self) is BaseCommand:
            LOGGER.print(self.subcommands_list())
        LOGGER.print(self.help_text())
        try:
            LOGGER.print(self.HELP_TEXT.lstrip())
        except AttributeError:
            pass

    def ask_yn(self, fmt, *args):
        "Returns True if the user selects 'yes' or confirmations are skipped."
        if not self.confirm:
            return True
        LOGGER.print(f"{fmt} [Y/n] ", *args, end="")
        try:
            resp = input().lower()
        except Exception:
            return False
        return not resp or resp.startswith("y")

    def ask_ny(self, fmt, *args):
        "Returns True if the user selects 'no' or confirmations are skipped."
        if not self.confirm:
            return True
        LOGGER.print(f"{fmt} [y/N] ", *args, end="")
        try:
            resp = input().lower()
        except Exception:
            return False
        return not resp or resp.startswith("n")

    def get_installs(self, *, include_unmanaged=False, set_default=True):
        from .installs import get_installs, get_matching_install_tags
        installs = get_installs(
            self.install_dir,
            include_unmanaged=include_unmanaged and self.include_unmanaged,
            virtual_env=self.virtual_env,
        )
        if set_default and not any(i.get("default") for i in installs):
            LOGGER.debug("Calculating default install")
            matching = get_matching_install_tags(
                installs,
                self.default_tag,
                default_platform=self.default_platform,
                single_tag=True,
            )
            if matching:
                if matching[0][0] not in installs:
                    raise RuntimeError("get_matching_install_tags returned value from wrong list")
                LOGGER.debug("Default install will be %s", matching[0][0]["id"])
                matching[0][0]["default"] = True
        return installs

    def get_install_to_run(self, tag=None, script=None, *, windowed=False):
        if script and not tag:
            from .scriptutils import find_install_from_script
            try:
                return find_install_from_script(self, script)
            except LookupError:
                pass
        from .installs import get_install_to_run
        return get_install_to_run(
            self.install_dir,
            self.default_tag,
            tag,
            windowed=windowed,
            include_unmanaged=self.include_unmanaged,
            virtual_env=self.virtual_env,
            default_platform=self.default_platform,
        )


class ListCommand(BaseCommand):
    CMD = "list"
    HELP_LINE = "Shows all installed Python runtimes"
    HELP_TEXT = r"""!G!List command!W!
> py list !B![options] [<FILTER> ...]!W!

!G!Options:!W!
    -f, --format=!B!<table,json,jsonl,powershell-json,id,exe,prefix>!W!
                     Specify output formatting (!B!list.format=...!W!)
    -1, --one        Only display first result
    --online         List runtimes available to install from the default index
    -s, --source=!B!<URL>!W!
                     List runtimes from a particular index
    --only-managed   Only list Python installs managed by the tool (!B!list.unmanaged=false!W!)
    <FILTER>         Filter results (Company\Tag with optional <, <=, >, >= prefix)

!B!EXAMPLE:!W! List all installed runtimes
> py list

!B!EXAMPLE:!W! Display executable of default runtime
> py list --one -f=exe

!B!EXAMPLE:!W! Show JSON details for all installs since 3.10
> py list -f=jsonl >=3.10

!B!EXAMPLE:!W! Find 3.12 runtimes available for install
> py list --online 3.12
"""

    format = "table"
    one = False
    unmanaged = True
    source = None
    default_source = False
    keep_log = False

    def execute(self):
        from .list_command import execute
        LOGGER.verbose("!W!%s", COPYRIGHT)
        if self.default_source:
            LOGGER.debug("Loading 'install' command to get source")
            inst_cmd = COMMANDS["install"](["install"], self.root)
            self.source = inst_cmd.source
        if self.source and "://" not in self.source:
            try:
                pass#self.source = Path(self.source).absolute().as_uri()
            except Exception as ex:
                raise ArgumentError("Source feed is not a valid path or URL") from ex
        execute(self)


class ListLegacy0Command(ListCommand):
    CMD = "-0"
    format = "legacy"
    unmanaged = True
    _create_log_file = False


class ListLegacy0pCommand(ListCommand):
    CMD = "-0p"
    format = "legacy-paths"
    unmanaged = True
    _create_log_file = False


class ListLegacyCommand(ListCommand):
    CMD = "--list"
    format = "legacy"
    unmanaged = True
    _create_log_file = False


class ListPathsLegacyCommand(ListCommand):
    CMD = "--list-paths"
    format = "legacy-paths"
    unmanaged = True
    _create_log_file = False


class InstallCommand(BaseCommand):
    CMD = "install"
    HELP_LINE = "Download new Python runtimes"
    HELP_TEXT = r"""!G!Install command!W!
> py install !B![options] <TAG> [<TAG>] ...!W!

!G!Options:!W!
    -s, --source=!B!<URI>!W!
                     Specify index.json to use (!B!install.source=...!W!)
    -t, --target=!B!<PATH>!W!
                     Extract runtime to location instead of installing
    -d, --download=!B!<PATH>!W!
                     Prepare an offline index with one or more runtimes
    -f, --force      Re-download and overwrite existing install
    -u, --update     Overwrite existing install if a newer version is available.
    --dry-run        Choose runtime but do not install
    --refresh        Update shortcuts and aliases for all installed versions.
    --by-id          Require TAG to exactly match the install ID. (For advanced use.)
    !B!<TAG> <TAG>!W! ...  One or more tags to install (Company\Tag format)

!B!EXAMPLE:!W! Install the latest Python 3 version
> py install 3

!B!EXAMPLE:!W! Extract Python 3.13 ARM64 to a directory
> py install --target=.\runtime 3.13-arm64

!B!EXAMPLE:!W! Clean reinstall of 3.13
> py install --force 3.13

!B!EXAMPLE:!W! Refresh and replace all shortcuts
> py install --refresh

!B!EXAMPLE:!W! Prepare an offline index with multiple versions
> py install --download=.\pkgs 3.12 3.12-arm64 3.13 3.13-arm64
"""

    source = None
    fallback_source = None
    target = None
    download = None
    force = False
    update = False
    repair = False
    dry_run = False
    refresh = False
    by_id = False
    automatic = False
    from_script = None
    enable_shortcut_kinds = None
    disable_shortcut_kinds = None

    def __init__(self, args, root=None):
        super().__init__(args, root)

        if not self.source:
            # HACK: For testing until we get a reasonable default feed
            self.source = str(Path(root) / "./bundled/index.json")
            if not Path(self.source).is_file():
                raise ArgumentError("No source feed specified.")
        if "://" not in str(self.source):
            try:
                self.source = Path(self.source).absolute().as_uri()
            except Exception as ex:
                raise ArgumentError("Source feed is not a valid path or URL") from ex
        if self.fallback_source and "://" not in self.fallback_source:
            try:
                self.fallback_source = Path(self.fallback_source).absolute().as_uri()
            except Exception as ex:
                raise ArgumentError("Fallback source feed is not a valid path or URL") from ex
        if self.target:
            self.target = Path(self.target).absolute()
        if self.download:
            self.download = Path(self.download).absolute()

    def execute(self):
        from .install_command import execute
        LOGGER.verbose("!W!%s", COPYRIGHT)
        execute(self)


class UninstallCommand(BaseCommand):
    CMD = "uninstall"
    HELP_LINE = "Remove runtimes from your machine"
    HELP_TEXT = r"""!G!Uninstall command!W!
> py uninstall !B![options] <TAG> [<TAG>] ...!W!

!G!Options:!W!
    --purge          Remove all runtimes, shortcuts, and cached files. Ignores tags.
    --by-id          Require TAG to exactly match the install ID. (For advanced use.)
    !B!<TAG> <TAG>!W! ...  One or more runtimes to uninstall (Company\Tag format)

!B!EXAMPLE:!W! Uninstall Python 3.12 32-bit
> py uninstall 3.12-32

!B!EXAMPLE:!W! Uninstall all runtimes without confirmation
> py uninstall --yes --purge

!B!EXAMPLE:!W! Uninstall all runtimes using their install ID.
> py uninstall --by-id (py list --only-managed -f=id)
"""

    confirm = True
    purge = False
    by_id = False

    # Not settable, but are checked by update_all_shortcuts() so we need them.
    enable_shortcut_kinds = None
    disable_shortcut_kinds = None

    def execute(self):
        from .uninstall_command import execute
        LOGGER.verbose("!W!%s", COPYRIGHT)
        execute(self)


#class RunCommand(BaseCommand):
#    CMD = "run"
#    HELP_LINE = "Launch a script in a dedicated environment"


class HelpCommand(BaseCommand):
    CMD = "help"
    HELP_LINE = "Show help for Python installation manager commands"
    HELP_TEXT = r"""!G!Help command!W!
> py help !B![<CMD>] ...!W!

!G!Options:!W!
    !B!<CMD>!W! ...       One or more commands to show help for. If omitted, lists
                    commands and global options only.
"""

    _create_log_file = False

    def execute(self):
        LOGGER.print(COPYRIGHT)
        if not self.args:
            LOGGER.print(BaseCommand.subcommands_list())
        LOGGER.print(BaseCommand.help_text())
        for a in self.args:
            try:
                cls = COMMANDS[a.lower()]
            except LookupError:
                LOGGER.warn("Command %s is not known.", a)
                continue
            try:
                LOGGER.print(cls.HELP_TEXT.lstrip())
            except AttributeError:
                pass


class DefaultConfig(BaseCommand):
    CMD = "__no_command"
    _create_log_file = False

    def __init__(self, root):
        super().__init__([], root)


def load_default_config(root):
    return DefaultConfig(root)


def find_command(args, root):
    for a in args:
        try:
            cls = COMMANDS[a.lower()]
        except LookupError:
            continue

        return cls(args, root)
    raise LookupError("Failed to find command")


def show_help(args):
    HelpCommand(["help", *args]).execute()
