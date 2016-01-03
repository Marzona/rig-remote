#!/usr/bin/env python

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
