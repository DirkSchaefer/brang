import datetime
import os
from abc import ABC, abstractmethod

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import backref, relationship
from sqlalchemy import UniqueConstraint

from brang.exceptions import SiteNotFoundException, SiteChangeNotFoundException


class BaseExt(object):
    """Does much nicer repr/print of class instances
    https://gist.github.com/major/2173517
    """

    def __repr__(self):
        return "%s(%s)" % (
            self.__class__.__name__,
            ', '.join(["%s=%r" % (key, getattr(self, key))
                       for key in sorted(self.__dict__.keys())
                       if not key.startswith('_')]))


Base = declarative_base(cls=BaseExt)


class Setting(Base):
    __tablename__ = 'setting'
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String)


class Site(Base):
    __tablename__ = 'site'
    id = Column(Integer, primary_key=True)
    url = Column(String)
    title = Column(String)
    site_changes = relationship("SiteChange",
                                backref="site",
                                cascade="all, delete, delete-orphan")


class SiteChange(Base):
    __tablename__ = 'site_change'
    __table_args__ = (UniqueConstraint('site_id', 'fingerprint', 'check_timestamp',
                                       name='unique_site_fingerprint_timestamp'), )
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey('site.id'))
    fingerprint = Column(String)
    check_timestamp = Column(DateTime)


class Database(ABC):
    """
    Abstract Base Class for the Database.
    """

    @abstractmethod
    def get_all_sites(self) -> list:
        """
        Returns a list of site objects
        :return:
        """
        pass

    def insert_site_change_entry(self, site: Site,
                                 fingerprint: str,
                                 timestamp: datetime.datetime):
        """
        Inserts a site_change entry.

        :param site:
        :param fingerprint:
        :param timestamp:
        :return:
        """
        pass

    def get_latest_sitechange(self, site: Site) -> SiteChange:
        """
        Returns
        :param site:
        :return:
        :raises: SiteChangeNotFoundException: if entry does not exist
        """
        pass


class SQLiteDatabase(Database):

    def __init__(self, db_filename):
        self.db_filename = db_filename
        self.engine = create_engine('sqlite:///' + self.db_filename, echo=False)
        cls_session = sessionmaker(bind=self.engine)
        self.session = cls_session()

        Base.metadata.create_all(bind=self.engine)
        self.setup_tables()

    def setup_tables(self):
        """
        Creates database tables if they do not exist yet.

        :return:
        """
        Setting.__table__.create(bind=self.engine, checkfirst=True)
        Site.__table__.create(bind=self.engine, checkfirst=True)
        SiteChange.__table__.create(bind=self.engine, checkfirst=True)

    def get_all_sites(self) -> list:
        """
        Returns a list of site objects
        :return:
        """
        qr = self.session.query(Site).all()
        all_sites = []
        for res in qr:
            all_sites.append(res)
        return all_sites

    def get_site(self, url) -> Site:
        """
        Returns a Site object given a url.

        :param url:
        :return:
        """
        try:
            qr = self.session.query(Site).filter(Site.url == url).one()
        except (sqlalchemy.orm.exc.NoResultFound, sqlalchemy.orm.exc.MultipleResultsFound):
            raise SiteNotFoundException(f"Site with url={url} could not be found.")
        return qr

    def get_site_by_id(self, site_id) -> Site:
        """
        Returns a Site object given its id.
        :param site_id:
        :return:
        """
        try:
            qr = self.session.query(Site).filter(Site.id == site_id).one()
        except (sqlalchemy.orm.exc.NoResultFound, sqlalchemy.orm.exc.MultipleResultsFound):
            raise SiteNotFoundException(f"Site with id={site_id} could not be found.")
        return qr

    def insert_site_change_entry(self, site: Site,
                                 fingerprint: str,
                                 timestamp: datetime.datetime):
        """
        Inserts a site_change entry.

        :param site:
        :param fingerprint:
        :param timestamp:
        :return:
        """
        self.session.add(SiteChange(site_id=site.id,
                                    fingerprint=fingerprint,
                                    check_timestamp=timestamp))
        self.session.commit()

    def get_latest_sitechange(self, site: Site) -> SiteChange:
        """
        Returns
        :param site:
        :return:
        :raises: SiteChangeNotFoundException: if entry does not exist
        """
        ex_msg = f"No SiteChange entry with id={site.id} could not be found."
        try:
            qr = self.session.query(SiteChange).\
                filter(site.id == SiteChange.site_id).\
                order_by(SiteChange.check_timestamp.desc()).first()
        except (sqlalchemy.orm.exc.NoResultFound, sqlalchemy.orm.exc.MultipleResultsFound):
            raise SiteChangeNotFoundException(ex_msg)
        if not qr:
            raise SiteChangeNotFoundException(ex_msg)
        return qr

    def destroy_sqlite_db_file(self):
        if os.path.exists(self.db_filename):
            os.remove(self.db_filename)


