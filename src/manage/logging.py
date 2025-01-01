import os
import sys


DEBUG = 10
VERBOSE = 15
INFO = 20
WARN = 30
ERROR = 40


class Logger:
    CONSOLE_PREFIX = {
        DEBUG: "# ",
        WARN: "[WARNING] ",
        ERROR: "[ERROR] ",
    }

    FILE_PREFIX = {
        VERBOSE: ">> ",
        INFO: ">  ",
        WARN: "!  ",
        ERROR: "!! ",
    }

    def __init__(self):
        if os.getenv("PYMANAGER_DEBUG"):
            self.level = DEBUG
        elif os.getenv("PYMANAGER_VERBOSE"):
            self.level = VERBOSE
        else:
            self.level = INFO
        self.console = sys.stderr
        self.file = None
        self._list = None

    def set_level(self, level):
        self.level = level

    def reduce_level(self, new_level):
        if new_level is not None and new_level < self.level:
            self.level = new_level
        return self.level

    def debug(self, msg, *args, **kwargs):
        self.log(DEBUG, msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        self.log(VERBOSE, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.log(INFO, msg, *args, **kwargs)

    def warn(self, msg, *args, **kwargs):
        self.log(WARN, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.log(ERROR, msg, *args, **kwargs)

    def would_log_to_console(self, level):
        return level >= self.level

    def would_log(self, level):
        return (level >= self.level) or self.file

    def log(self, level, msg, *args, exc_info=False):
        if self._list is not None:
            self._list.append((msg, args))
        if not ((level >= self.level) or self.file is not None):
            return
        msg = msg % args
        if level >= self.level:
            print(self.CONSOLE_PREFIX.get(level, ""), msg, sep="", file=self.console)
        if self.file is not None:
            print(self.FILE_PREFIX.get(level, ""), msg, sep="", file=self.file)
        if exc_info:
            import traceback
            exc = traceback.format_exc()
            if level >= self.level:
                print(exc, file=self.console)
            if self.file is not None:
                print(exc, file=self.file)

    def print(self, *args, **kwargs):
        if kwargs.pop("level", INFO) < self.level:
            return
        print(*args, **kwargs, file=self.console)


LOGGER = Logger()


class ProgressPrinter:
    def __init__(self, operation, maxwidth=80):
        self.operation = operation or "Progress"
        self.width = maxwidth - 2 - len(self.operation)
        self._dots_shown = 0
        self._started = False
        self._complete = False
        self._need_newline = False

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if self._need_newline:
            if self._complete:
                LOGGER.print()
            else:
                LOGGER.print("❌")

    def __call__(self, progress):
        if self._complete:
            return

        if progress is None:
            if self._need_newline:
                if not self._complete:
                    LOGGER.print("⏸️")
                    self._dots_shown = 0
                    self._started = False
                    self._need_newline = False
            return

        if not self._started:
            LOGGER.print(self.operation, ": ", sep="", end="", flush=True)
            self._started = True
            self._need_newline = True

        dot_count = min(self.width, progress * self.width // 100) - self._dots_shown
        if dot_count <= 0:
            return

        self._dots_shown += dot_count
        LOGGER.print("." * dot_count, end="", flush=True)
        self._need_newline = True
        if progress >= 100:
            LOGGER.print("✅", flush=True)
            self._complete = True
            self._need_newline = False
