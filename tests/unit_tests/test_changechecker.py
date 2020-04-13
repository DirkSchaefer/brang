import unittest
import logging
import requests
import hashlib
import time

import mailtest

import tests.test_server as test_server
import brang.database as database
from brang.change_checker import ChangeChecker
from brang.exceptions import FingerprintGenerationError
from brang.database import Site, SiteChange

logging.basicConfig(level=logging.INFO)


class ChangeCheckerTests(unittest.TestCase):
    def setUp(self):
        logging.info("setUp")
        self.url_fix = 'http://localhost:5000/fix'
        self.url_changing = 'http://localhost:5000/changing'
        self.db = database.SQLiteDatabase(db_filename=':memory:')
        test_server.start_server()
        self.checker = ChangeChecker(db=self.db)

    def test_change_checker_fingerprint(self):
        r_t1 = requests.get(self.url_fix)
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        site = Site(url=self.url_fix)
        d = self.checker.get_fingerprint(site=site)
        self.assertEqual(['fingerprint', 'timestamp'], list(d.keys()))
        self.assertEqual(s1, d['fingerprint'])

    def test_change_checker_fingerprint_broken_url(self):
        with self.assertRaises(FingerprintGenerationError) as cm:
            url = 'http://localhost:5001/doesnotexists'
            site = Site(url=url)
            d = self.checker.get_fingerprint(site=site)
        ex = cm.exception
        print(ex)

    def test_change_checker_fingerprint_non_200_status_code(self):
        test_url = 'http://localhost:5000/unknown'
        with self.assertRaises(FingerprintGenerationError) as cm:
            site = Site(url=test_url)
            d = self.checker.get_fingerprint(site=site)
        ex = cm.exception
        print(ex)

    def test_prelim_detect_site_change(self):
        r_t1 = requests.get(self.url_changing)
        r_t1.content
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        logging.info(f"Fingerprint t1: {s1}")
        r_t2 = requests.get(self.url_changing)
        r_t2.content
        s2 = hashlib.sha224(r_t2.content).hexdigest()
        logging.info(f"Fingerprint t2: {s2}")
        self.assertIsNot(s1, s2)

    def test_prelim_detect_no_site_change(self):
        r_t1 = requests.get(self.url_fix)
        r_t1.content
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        logging.info(f"Fingerprint t1: {s1}")
        r_t2 = requests.get(self.url_fix)
        r_t2.content
        s2 = hashlib.sha224(r_t2.content).hexdigest()
        logging.info(f"Fingerprint t2: {s2}")
        self.assertEqual(s1, s2)

    def test_check_site_changing_empty(self):
        self.db.insert_site(url=self.url_changing)
        site = self.db.get_site(url=self.url_changing)
        self.checker.check_site(site=site)
        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(site.id, qr[0].site_id)

    def test_check_site_changing_nonempty(self):
        self.db.insert_site(url=self.url_changing)
        site = self.db.get_site(url=self.url_changing)
        self.checker.check_site(site=site)
        time.sleep(1)
        self.checker.check_site(site=site)

        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(2, len(qr))

    def test_check_site_nonchanging_nonempty(self):
        self.db.insert_site(url=self.url_fix)
        site = self.db.get_site(url=self.url_fix)
        self.checker.check_site(site=site)
        time.sleep(1)
        self.checker.check_site(site=site)
        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(1, len(qr))

    def test_check_all_sites_first_run(self):
        self.db.insert_site(url=self.url_fix)
        self.db.insert_site(url=self.url_changing)
        self.checker.check_all_sites()
        qr = self.db.session.query(SiteChange).all()
        for res in qr:
            logging.info(res)
        self.assertEqual(2, len(qr))

    def test_check_all_sites_late_run(self):
        self.db.insert_site(url=self.url_fix)
        self.db.insert_site(url=self.url_changing)
        self.checker.check_all_sites()
        self.checker.check_all_sites()
        qr = self.db.session.query(SiteChange).all()
        for res in qr:
            logging.info(res)
        self.assertEqual(3, len(qr))

    def test_send_email(self):
        recipient = "root@localhost"
        self.db.add_setting(key="email_to", value=recipient)
        self.db.add_setting(key="smtp_port", value="1025")
        self.db.add_setting(key="smtp_server", value="localhost")

        with mailtest.Server(smtp_port=1025) as s:
            self.checker.send_email(msg_body="test")
            self.assertEqual(len(s.emails), 1)
            self.assertEqual(s.emails[0].frm, 'notify@brang.io')
            self.assertEqual(s.emails[0].to, [recipient])
            self.assertEqual(s.emails[0].msg, 'test')

    def tearDown(self) -> None:
        logging.info("tear down")
        self.db.destroy_sqlite_db_file()
        test_server.stop_server()


if __name__ == '__main__':
    unittest.main()
