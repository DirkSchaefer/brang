import datetime
import hashlib
import logging
import requests
import smtplib
from email.message import EmailMessage

from brang.exceptions import FingerprintGenerationError
from brang.database import Database, Site, SiteChange
from brang.exceptions import SiteChangeNotFoundException, SettingNotFoundException

log = logging.getLogger(__name__)


class ChangeChecker(object):
    """
    ChangeChecker is responsible for checking all sites (in DB) for changes.

    It does it by requesting an URL from DB "Site" table and taking a fingerprint.
    If the fingerprint does not exist yet for that URL in table "SiteChange",
    it will be added.
    """

    def __init__(self, db: Database):
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
            ts = datetime.datetime.now()
            r = requests.get(url)
            if r.status_code != 200:
                raise FingerprintGenerationError(f"Invalid http code: {r.status_code}.")
            finger_print = hashlib.sha224(r.content).hexdigest()
            ret = {'fingerprint': finger_print, 'timestamp': ts}
            return ret
        except Exception as e:
            raise FingerprintGenerationError(f"Fingerprint for url={url} could not be generated at ts={ts}. "
                                             f"Original exception: {e.__class__}:{str(e)}")

    def check_site(self, site: Site):
        """
        Check content change for one particular site.

        :param site:
        :return:
        """
        d = ChangeChecker.get_fingerprint(site=site)
        update_detected = False
        try:
            latest_site_change = self.db.get_latest_sitechange(site=site)
            if d['fingerprint'] == latest_site_change.fingerprint:
                return
            else:
                update_detected = True
        except SiteChangeNotFoundException:
            pass

        # Create new SiteChange entry
        self.db.insert_site_change_entry(site=site,
                                         fingerprint=d['fingerprint'],
                                         timestamp=d['timestamp'])
        return update_detected

    def check_all_sites(self):
        """
        Check all site for content changes.

        The method also triggers the notification if changes have been found.

        :return:
        """
        sites = self.db.get_all_sites()

        msg_lines = []
        for site in sites:
            log.info(f"Processing site: Id={site.id}, URL={site.url}")
            update_detected = self.check_site(site=site)
            if update_detected:
                msg_lines.append(f"* {site.url}")

        if len(msg_lines) > 0:
            self.send_email(msg_body="\n".join(msg_lines))

    def send_email(self, msg_body):
        """
        Helper function for sending e-mail.

        The method requires an existing Setting entries with the keys
         - email_to
         - smtp_port
         - smtp_server

        :param msg_body:
        :return:
        """
        try:
            email_to = self.db.get_setting("email_to").value
            smtp_server = self.db.get_setting("smtp_server").value
            smtp_port = int(self.db.get_setting("smtp_port").value)
            msg = EmailMessage()
            msg.set_content(msg_body)
            msg['Subject'] = f"Brang.io: Site changes detected"
            msg['From'] = "notify@brang.io"
            msg['To'] = email_to

            s = smtplib.SMTP(host=smtp_server, port=smtp_port)
            s.send_message(msg)
            s.close()
        except SettingNotFoundException as e:
            log.error(f"Could not send e-email. {e}")
