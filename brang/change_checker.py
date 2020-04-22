import datetime
import hashlib
import logging
import os
import smtplib
from email.message import EmailMessage
from abc import ABC, abstractmethod

import requests

import brang.config as config
from brang.database import SQLiteDatabase, Database, Site
from brang.exceptions import RequestError
from brang.exceptions import SiteChangeNotFoundException, SettingNotFoundException

log = logging.getLogger(__name__)


def create_fingerprint(text: str):
    """
    Creates a fingerprint for a given string.

    :param text:
    :return:
    """
    fingerprint = hashlib.sha224(text.encode('utf-8')).hexdigest()
    return fingerprint


def request_site(site: Site):
    """
    Requests the content of a site from the world wide web.

    :param site:
    :return:
    """
    url = site.url
    try:
        r = requests.get(url)
        if r.status_code != 200:
            raise RequestError(f"Invalid http code: {r.status_code}.")
        return r.text
    except Exception as e:
        raise RequestError(f"Request for url={url} failed. "
                           f"Original exception: {e.__class__}:{str(e)}")


class ChangeCheckStrategy(ABC):
    """
    Interface for ChangeCheckStrategies
    """

    @abstractmethod
    def change_check(self, site: Site):
        """
        This method checks if a site has been changed in comparison to an earlier entry.
        If there are no entries, a new SiteChange entry will be created.

        :param site:
        :return: True if a Site change could be detected, False otherwise
        """
        pass


class NaiveCheckStrategy(ChangeCheckStrategy):
    def __init__(self, db: Database):
        self.db = db

    def change_check(self, site: Site):
        """

        :param site:
        :return:
        """
        text = request_site(site=site)
        current_fingerprint = create_fingerprint(text=text)
        current_ts = datetime.datetime.now()
        update_detected = False
        try:
            latest_site_change = self.db.get_latest_sitechange(site=site)
            if current_fingerprint == latest_site_change.fingerprint:
                return
            else:
                update_detected = True
        except SiteChangeNotFoundException:
            pass

        # Create new SiteChange entry
        self.db.insert_site_change_entry(site=site,
                                         fingerprint=current_fingerprint,
                                         timestamp=current_ts)
        return update_detected


class ChangeChecker(object):
    """
    ChangeChecker is responsible for checking all sites (in DB) for changes.

    It does this by requesting a URL from DB "Site" table and taking a fingerprint.
    If the fingerprint does not exist yet for that URL in table "SiteChange",
    it will be added.
    """

    def __init__(self, db: Database, change_check_strategy: ChangeCheckStrategy = None):
        self.db = db
        self.change_check_strategy = change_check_strategy

    def check_site(self, site: Site):
        """
        Check content change for one particular site.

        :param site:
        :return:
        """
        site_has_changed = self.change_check_strategy.change_check(site=site)
        return site_has_changed

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

        The method requires an existing Setting entry with the key
         - email_to, and
         config.py entries
         - smtp_port
         - smtp_server

        :param msg_body:
        :return:
        """
        try:
            email_to = self.db.get_setting("email_to").value
            if email_to == '':
                raise SettingNotFoundException
            smtp_server = config.smtp_server
            smtp_port = config.smtp_port
            msg = EmailMessage()
            msg.set_content(msg_body)
            msg['Subject'] = f"Brang.io: Site changes detected"
            msg['From'] = "notify@brang.io"
            msg['To'] = email_to

            s = smtplib.SMTP(host=smtp_server, port=smtp_port)
            s.send_message(msg)
            s.close()
        except Exception as e:
            log.error(f"Could not send e-email. {e}")


if __name__ == '__main__':
    t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f'[{t}] Brang::ChangeChecker.check_all_sites()')
    full_sqlite_file = os.path.expanduser(config.sqlite_file)
    brang_dir = os.path.dirname(full_sqlite_file)
    if not os.path.exists(brang_dir):
        os.makedirs(brang_dir)
    db = SQLiteDatabase(db_filename=full_sqlite_file)

    checker = ChangeChecker(db=db)
    checker.check_all_sites()