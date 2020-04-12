"""Custom Exceptions and Errors"""


class FingerprintGenerationError(Exception):
    """Raised when a fingerprint could not be generated"""
    pass


class SiteNotFoundException(Exception):
    """Raised when a Site could not be found"""
    pass
