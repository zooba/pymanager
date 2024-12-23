class ArgumentError(Exception):
    pass


class HashMismatchError(Exception):
    pass


class NoInstallsError(Exception):
    pass


class NoInstallFoundError(Exception):
    def __init__(self, tag=None, script=None):
        self.tag = tag
        self.script = script
        # TODO: Better error message
        super().__init__("No install found for '{}' or '{}'".format(
            self.tag, self.script
        ))


class InvalidFeedError(Exception):
    pass


class InvalidInstallError(Exception):
    def __init__(self, message, prefix=None):
        super().__init__(message, prefix)

    @property
    def prefix(self):
        return self.args[1] if len(self.args) >= 2 else None


class InvalidConfigurationError(ValueError):
    def __init__(self, file=None, argument=None, value=None):
        if value:
            msg = f"Invalid configuration value {value!r} for key {argument} in {file}"
        elif argument:
            msg = f"Invalid configuration key {argument} in {file}"
        elif file:
            msg = f"Invalid configuration file {file}"
        else:
            msg = "Invalid configuration"
        super().__init__(msg, file, argument, value)

    @property
    def file(self):
        return self.args[1] if len(self.args) >= 2 else None

    @property
    def argument(self):
        return self.args[2] if len(self.args) >= 3 else None

    @property
    def value(self):
        return self.args[3] if len(self.args) >= 4 else None
