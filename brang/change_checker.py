import datetime
import hashlib
import logging
import os
import smtplib
import time
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
        This method checks if a site has been changed in comparison to an earlier entry.
        If there are no entries, a new SiteChange entry will be created.

        :param site:
        :return: True if a Site change could be detected, False otherwise
        """
        text = request_site(site=site)
        current_fingerprint = create_fingerprint(text=text)
        current_ts = datetime.datetime.now()
        update_detected = False
        try:
            latest_site_change = self.db.get_latest_sitechange(site=site)
            if current_fingerprint == latest_site_change.fingerprint:
                return False
            else:
                update_detected = True
        except SiteChangeNotFoundException:
            pass

        # Create new SiteChange entry
        self.db.insert_site_change_entry(site=site,
                                         fingerprint=current_fingerprint,
                                         timestamp=current_ts)
        return update_detected


class HfcInvarianceCheckStrategy(ChangeCheckStrategy):
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def transform(text: str):
        """
        Basic transform used by HFC Invariance Check
        :param text:
        :return: list
        """
        return text.replace('<', '\n<').split('\n')

    @staticmethod
    def apply_pattern(pattern: str, text: str):
        """
        Applies the hfc-pattern on the text and returns the fingerprint.

        :param pattern:
        :param text:
        :return:
        """
        p = pattern.split(',')
        p.reverse()
        t_list = HfcInvarianceCheckStrategy.transform(text=text)
        for entry in p:
            if entry != '':
                del t_list[int(entry)]

        site_str = ''.join(t_list)
        return create_fingerprint(text=site_str)

    @staticmethod
    def create_pattern(site_t1_text, site_t2_text):
        """
        Creates the hfc-pattern on two html documents.

        :param site_t1_text: html content (text) of a site at timestamp 1
        :param site_t2_text: html content (text) of a site at timestamp 2
        :return: pattern as comma separated string of line numbers
        """
        t_list_1 = HfcInvarianceCheckStrategy.transform(text=site_t1_text)
        t_list_2 = HfcInvarianceCheckStrategy.transform(text=site_t2_text)
        pattern = []
        for i in range(len(t_list_1)):
            if t_list_1[i] != t_list_2[i]:
                pattern.append(i)
        pattern_str = ','.join([str(x) for x in pattern])
        return pattern_str

    def change_check(self, site: Site):
        """
        This method checks if a site has been changed in comparison to an earlier entry.

        If there are no previous SiteChange entries, a new SiteChange entry will be created.

        :param site:
        :return: True if a Site change could be detected, False otherwise
        """
        update_detected = False
        try:
            latest_site_change = self.db.get_latest_sitechange(site=site)
            latest_fingerprint = latest_site_change.fingerprint
            log.info(f"Latest fingerprint: {latest_fingerprint}")
            latest_pattern = ""
            if latest_site_change.pattern:
                latest_pattern = latest_site_change.pattern
            log.info(f"Pattern of latest_sitechange: {latest_pattern}")

            current_text = request_site(site=site)
            current_fingerprint = HfcInvarianceCheckStrategy.apply_pattern(latest_pattern, current_text)
            log.info(f"Current fingerprint: {current_fingerprint}")

            if current_fingerprint == latest_fingerprint:
                log.info(f'Nothing has changed.')
                return False  # Nothing changed (update_detected = False)
            else:
                log.info(f'Update detected.')
                update_detected = True

                # Check validity of pattern by comparing ct_text vs (counter)check_text
                log.info(f'Check validity of pattern.')
                time.sleep(0.5)
                check_text = request_site(site=site)
                check_fingerprint = HfcInvarianceCheckStrategy.apply_pattern(latest_pattern, check_text)
                if check_fingerprint != current_fingerprint:
                    log.info(f'Pattern not valid. Recreating it.')
                    current_pattern = HfcInvarianceCheckStrategy.create_pattern(current_text, check_text)

                    # Recreate current_fingerprint
                    current_fingerprint = HfcInvarianceCheckStrategy.apply_pattern(current_pattern, current_text)
                else:
                    log.info(f'Pattern is still valid.')
                    current_pattern = latest_pattern

        except SiteChangeNotFoundException:
            log.info(f'SiteChange entry for url={site.url} not found. Create new HFC fingerprint.')
            text_t1 = request_site(site=site)
            time.sleep(1)
            text_t2 = request_site(site=site)
            current_pattern = HfcInvarianceCheckStrategy.create_pattern(text_t1, text_t2)
            current_fingerprint = HfcInvarianceCheckStrategy.apply_pattern(current_pattern, text_t1)

        # Create new SiteChange entry
        log.info(f"Creating new SiteChange entry with fingerprint: {current_fingerprint} and pattern: {current_pattern}")
        self.db.insert_site_change_entry(site=site,
                                         fingerprint=current_fingerprint,
                                         pattern=current_pattern)

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
        if change_check_strategy is None:
            self.change_check_strategy = HfcInvarianceCheckStrategy(db=self.db)
        else:
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