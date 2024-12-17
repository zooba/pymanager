import logging
import sys

FILE = sys.stderr

LOGGER = logging.getLogger("pymanager")
LOGGER.addHandler(logging.StreamHandler(FILE))

class ProgressPrinter:
    def __init__(self, operation):
        self.operation = operation or "Progress"
        self.width = 80
        self._dots_shown = 0
        self._complete = False
        self._need_newline = False
        self.file = FILE if LOGGER.isEnabledFor(logging.INFO) else None

    def __enter__(self):
        if self.file:
            print(self.operation, ": ", sep="", end="", flush=True, file=self.file)
        return self

    def __exit__(self, *exc_info):
        if self.file and self._need_newline:
            if self._complete:
                print(file=self.file)
            else:
                print("❌", file=self.file)

    def __call__(self, progress):
        if self._complete:
            return

        if progress is None:
            if self.file and self._need_newline:
                if not self._complete:
                    print(file=self.file)
                    self._need_newline = False
            return

        dot_count = min(self.width, progress * self.width // 100) - self._dots_shown
        if dot_count <= 0:
            return

        self._dots_shown += dot_count
        if self.file:
            print("." * dot_count, end="", flush=True, file=self.file)
            self._need_newline = True
            if progress >= 100:
                print("✅", flush=True, file=self.file)
                self._complete = True
                self._need_newline = False
