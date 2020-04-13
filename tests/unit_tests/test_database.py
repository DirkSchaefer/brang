import unittest
import logging
import datetime

import sqlalchemy

import brang.database as database
from brang.database import Site, SiteChange
from brang.exceptions import SiteChangeNotFoundException, SettingNotFoundException

logging.basicConfig(level=logging.INFO)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        logging.info("setUp")
        self.db = database.SQLiteDatabase(db_filename=':memory:')
        self.url_fix = 'http://localhost:5000/fix'
        self.url_changing = 'http://localhost:5000/changing'

        self.db.session.add(Site(url=self.url_changing))
        self.db.session.add(Site(url=self.url_fix))
        self.db.session.add(SiteChange(site_id=1,
                                       fingerprint="xyz",
                                       check_timestamp=datetime.datetime.now()))
        self.db.session.add(SiteChange(site_id=1,
                                       fingerprint="abc",
                                       check_timestamp=datetime.datetime(1988, 10, 15)))
        self.db.session.commit()

    def test_insert_site(self):
        self.db.insert_site(url="https://www.brang.io")
        site = self.db.get_site(url="https://www.brang.io")
        logging.info(site)
        self.assertIsNot(None, site.id)

    def test_get_all_sites(self):
        all_sites = self.db.get_all_sites()
        for entry in all_sites:
            logging.info(type(entry))
            logging.info(f"Content: {entry}")
        self.assertEqual(list, type(all_sites))
        self.assertEqual(2, len(all_sites))

    def test_insert_sitechange_entry_primitive(self):
        timestamp = datetime.datetime.now()
        self.db.session.add(SiteChange(site_id=1,
                                       fingerprint='Test',
                                       check_timestamp=timestamp))
        self.db.session.commit()
        try:
            self.db.session.add(SiteChange(site_id=1,
                                           fingerprint='Test',
                                           check_timestamp=timestamp))
            self.db.session.commit()
        except sqlalchemy.exc.IntegrityError as e:
            print("exception caught")
            print(e)

    def test_remove_sitechange_entry_by_deleting_site(self):
        site_entry = Site(url='http://brang.io')
        self.db.session.add(site_entry)
        self.db.session.commit()
        print(site_entry.id)

        # Add sitechange entry
        self.db.session.add(SiteChange(site_id=site_entry.id,
                                       fingerprint='Test',
                                       check_timestamp=datetime.datetime.now()))
        self.db.session.add(SiteChange(site_id=site_entry.id,
                                       fingerprint='Test2',
                                       check_timestamp=datetime.datetime.now()))
        self.db.session.commit()

        # Show all sitechange entries
        qr = self.db.session.query(SiteChange).all()
        for entry in qr:
            logging.info(entry)

        # Removing site (should also remove sitechange entries
        self.db.session.delete(site_entry)
        self.db.session.commit()

        # Show all sites
        logging.info("All Site entries:")
        for entry in self.db.session.query(Site).all():
            logging.info(entry)

        # Show all sitechange entries (should be gone)
        logging.info("All SiteChange entries (should be gone):")
        for entry in self.db.session.query(SiteChange).all():
            logging.info(entry)

    def test_get_latest_sitechange(self):
        site = self.db.get_site(self.url_changing)
        logging.info(f"Site: {site}")
        site_change = self.db.get_latest_sitechange(site=site)
        logging.info(site_change)
        self.assertEqual("xyz", site_change.fingerprint)

    def test_get_latest_sitechange_none(self):
        """
        Test if exception is raised if no sitechange entry could be found.
        :return:
        """
        with self.assertRaises(SiteChangeNotFoundException) as cm:
            site = self.db.get_site(self.url_fix)
            logging.info(f"Site: {site}")
            site_change = self.db.get_latest_sitechange(site=site)
            logging.info(site_change)
        ex = cm.exception
        print(ex)

    def test_insert_sitechange_entry(self):
        url = "http://insert_sitechange_test.com"
        self.db.insert_site(url=url)
        site = self.db.get_site(url=url)
        self.db.insert_site_change_entry(site=site,
                                         fingerprint="123",
                                         timestamp=datetime.datetime.now())
        qr = self.db.session.query(SiteChange).filter(SiteChange.fingerprint == "123").one()
        logging.info(qr)
        self.assertEqual(site.id, qr.site_id)

    def test_setting_insert(self):
        test_value = "bar"
        self.db.add_setting("foo", test_value)
        setting = self.db.get_setting("foo")
        self.assertEqual(test_value, setting.value)

    def test_setting_get_miss(self):
        with self.assertRaises(SettingNotFoundException):
            self.db.get_setting("foo")

    def test_setting_remove(self):
        self.db.add_setting("foo", "bar")
        self.db.remove_setting("foo")
        with self.assertRaises(SettingNotFoundException):
            self.db.get_setting("foo")

    def tearDown(self) -> None:
        logging.info("tear down")
        self.db.destroy_sqlite_db_file()


if __name__ == '__main__':
    unittest.main()
