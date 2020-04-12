import unittest
import logging
import requests
import hashlib
import time

import tests.test_server as test_server
import brang.database as database
from brang.change_checker import ChangeChecker
from brang.exceptions import FingerprintGenerationError
from brang.database import Site, SiteChange


logging.basicConfig(level=logging.INFO)


class ChangeCheckerTests(unittest.TestCase):
    def setUp(self):
        logging.info("setUp")
        self.db = database.SQLiteDatabase(db_filename=':memory:')
        test_server.start_server()
        self.checker = ChangeChecker(db=self.db)

    def test_change_checker_fingerprint(self):
        url = 'http://localhost:5000/eternal'
        r_t1 = requests.get(url)
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        site = Site(url=url)
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
        with self.assertRaises(FingerprintGenerationError) as cm:
            url = 'http://localhost:5000/eternals'
            site = Site(url=url)
            d = self.checker.get_fingerprint(site=site)
        ex = cm.exception
        print(ex)

    def test_prelim_detect_site_change(self):
        r_t1 = requests.get('http://localhost:5000/atomic')
        r_t1.content
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        logging.info(f"Fingerprint t1: {s1}")
        r_t2 = requests.get('http://localhost:5000/atomic')
        r_t2.content
        s2 = hashlib.sha224(r_t2.content).hexdigest()
        logging.info(f"Fingerprint t2: {s2}")
        self.assertIsNot(s1, s2)

    def test_prelim_detect_no_site_change(self):
        r_t1 = requests.get('http://localhost:5000/eternal')
        r_t1.content
        s1 = hashlib.sha224(r_t1.content).hexdigest()
        logging.info(f"Fingerprint t1: {s1}")
        r_t2 = requests.get('http://localhost:5000/eternal')
        r_t2.content
        s2 = hashlib.sha224(r_t2.content).hexdigest()
        logging.info(f"Fingerprint t2: {s2}")
        self.assertEqual(s1, s2)

    def test_check_site_changing_empty(self):
        test_url = 'http://localhost:5000/atomic'
        self.db.insert_site(url=test_url)
        site = self.db.get_site(url=test_url)
        self.checker.check_site(site=site)
        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(site.id, qr[0].site_id)

    def test_check_site_changing_nonempty(self):
        test_url = 'http://localhost:5000/atomic'
        self.db.insert_site(url=test_url)
        site = self.db.get_site(url=test_url)
        self.checker.check_site(site=site)
        time.sleep(1)
        self.checker.check_site(site=site)

        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(2, len(qr))

    def test_check_site_nonchanging_nonempty(self):
        test_url = 'http://localhost:5000/eternal'
        self.db.insert_site(url=test_url)
        site = self.db.get_site(url=test_url)
        self.checker.check_site(site=site)
        time.sleep(1)
        self.checker.check_site(site=site)
        qr = self.db.session.query(SiteChange).filter(SiteChange.site_id == site.id).all()
        logging.info(qr)
        self.assertEqual(1, len(qr))

    def tearDown(self) -> None:
        logging.info("tear down")
        self.db.destroy_sqlite_db_file()
        test_server.stop_server()


if __name__ == '__main__':
    unittest.main()
