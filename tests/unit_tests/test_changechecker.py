import unittest
import logging
import time

import mailtest

import tests.test_server as test_server
import brang.database as database
from brang.change_checker import request_site
from brang.change_checker import ChangeChecker, NaiveCheckStrategy
from brang.exceptions import RequestError
from brang.database import Site, SiteChange
from brang import config

logging.basicConfig(level=logging.DEBUG)


class ChangeCheckerTests(unittest.TestCase):
    def setUp(self):
        logging.info("setUp")
        self.url_fix = 'http://localhost:5000/fix'
        self.url_changing = 'http://localhost:5000/changing'
        self.db = database.SQLiteDatabase(db_filename=':memory:')
        test_server.start_server()
        self.naive_check_strategy = NaiveCheckStrategy(db=self.db)
        self.checker = ChangeChecker(db=self.db)
        self.checker.change_check_strategy = self.naive_check_strategy

    def test_request_site_broken_url(self):
        with self.assertRaises(RequestError) as cm:
            url = 'http://localhost:5001/doesnotexists'
            site = Site(url=url)
            site_content = request_site(site=site)
        ex = cm.exception
        logging.info(ex)

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
        config.smtp_port = 1025
        config.smtp_server = "localhost"

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
