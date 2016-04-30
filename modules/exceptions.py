#!/usr/bin/env python
"""
Remote application that interacts with rigs using rigctl protocol.

Please refer to:
http://gqrx.dk/
http://gqrx.dk/doc/remote-control
http://sourceforge.net/apps/mediawiki/hamlib/index.php?title=Documentation

Author: Rafael Marmelo
Author: Simone Marzona

License: MIT License

Copyright (c) 2014 Rafael Marmelo
Copyright (c) 2015 Simone Marzona
"""
# custom exception definition

# non retriable custom exceptions

class NonRetriableError (Exception):
    pass

class InvalidPathError (NonRetriableError):
    pass

class UnsupportedScanningConfigError(NonRetriableError):
    pass

# retriable custom exceptions

class RetriableError (object):
    pass

