import datetime
import hashlib
import logging
import requests

from brang.exceptions import FingerprintGenerationError
from brang.database import Site, SiteChange

log = logging.getLogger(__name__)


class ChangeChecker(object):
    """
    ChangeChecker is responsible for checking all sites (in DB) for changes.

    It does it by requesting an URL from DB "Site" table and taking a fingerprint.
    If the fingerprint does not exist yet for that URL in table "SiteChange",
    it will be added.
    """

    def __init__(self, db):
        self.db = db

    @staticmethod
    def get_fingerprint(site: Site):
        """
        Determines the fingerprint of a website specified by its URL.

        :param site:
        :return: dictionary with keys: timestamp and fingerprint
        """
        url = site.url
        try:
            ts = datetime.datetime.now().timestamp()
            r = requests.get(url)
            if r.status_code != 200:
                raise FingerprintGenerationError(f"Invalid http code: {r.status_code}.")
            finger_print = hashlib.sha224(r.content).hexdigest()
            ret = {'fingerprint': finger_print, 'timestamp': ts}
            return ret
        except Exception as e:
            raise FingerprintGenerationError(f"Fingerprint for url={url} could not be generated at ts={ts}. "
                                             f"Original exception: {e.__class__}:{str(e)}")

