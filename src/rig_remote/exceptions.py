"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation


Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
"""


class NonRetriableError(Exception):
    pass


class InvalidPathError(NonRetriableError):
    pass


class UnsupportedScanningConfigError(NonRetriableError):
    pass


class UnsupportedSyncConfigError(NonRetriableError):
    pass


class RetriableError(Exception):
    pass


class BookmarkFormatError(RetriableError):
    pass
