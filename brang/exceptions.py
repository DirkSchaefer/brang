"""Custom Exceptions and Errors"""


class FingerprintGenerationError(Exception):
    """Raised when a fingerprint could not be generated"""
    pass


class SiteNotFoundException(Exception):
    """Raised when a Site could not be found"""
    pass


class SiteChangeNotFoundException(Exception):
    """Raised when a SiteChange entry could not be found"""


class SettingNotFoundException(Exception):
    """Raised when a Setting entry could not be found"""

