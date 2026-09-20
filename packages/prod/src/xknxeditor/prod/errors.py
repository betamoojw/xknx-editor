class ArchiveError(Exception):
    """Invalid or unreadable knxprod archive."""


class VersionError(Exception):
    """KNX version undetectable or unsupported."""


class ParseError(Exception):
    """XML parsing failed."""


class EncodingError(Exception):
    """A parameter value could not be encoded into its memory/property image.

    Raised instead of silently skipping the write: a value that fails to encode against
    its own declared type is a clear sign of corrupt data (a hand-edited project, a UI
    bug bypassing widget validation, or a calculation producing a bad value), and a
    partial image must never be programmed onto a device.
    """
