#!/usr/bin/env python

# custom exception definition

# non retriable custom exceptions

class NonRetriableError (object):
    pass

class InvalidPathError (NonRetriableError):
    pass

class UnsupportedScanningConfigError(NonRetriableError):
    pass

# retriable custom exceptions

class RetriableError (object):
    pass
