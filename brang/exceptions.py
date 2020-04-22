"""Custom Exceptions and Errors"""


class RequestError(Exception):
    """Raised when a URL could not be requested"""
    pass


class SiteNotFoundException(Exception):
    """Raised when a Site could not be found"""
    pass


class SiteChangeNotFoundException(Exception):
    """Raised when a SiteChange entry could not be found"""


class SettingNotFoundException(Exception):
    """Raised when a Setting entry could not be found"""

