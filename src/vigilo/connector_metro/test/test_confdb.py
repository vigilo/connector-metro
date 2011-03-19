# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212

from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree, copy
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from twisted.internet import defer

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.connector_metro.vigiconf_settings import ConfDB, NoConfDBError


class ConfDBTest(unittest.TestCase):
    """
    Gestion du protocole SNMP entre avec le démon
    """

    def setUp(self):
        dbpath = os.path.join(os.path.dirname(__file__), "connector-metro.db")
        self.confdb = ConfDB(dbpath)
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")

    def tearDown(self):
        self.confdb.stop()
        rmtree(self.tmpdir)

    @deferred(timeout=30)
    @defer.inlineCallbacks
    def test_reload(self):
        """Reconnexion à la base"""
        self.confdb.start_db()
        yield self.confdb.get_hosts()
        old_connection_threads = set(self.confdb._db.connections.keys())
        print self.confdb._db.connections
        newdb = os.path.join(self.tmpdir, "conf.db")
        copy(self.confdb.path, newdb)
        self.confdb.path = newdb
        self.confdb.reload()
        yield self.confdb.get_hosts()
        new_connection_threads = set(self.confdb._db.connections.keys())
        self.assertNotEqual(old_connection_threads, new_connection_threads)

    @deferred(timeout=30)
    @defer.inlineCallbacks
    def test_reload_nochange(self):
        """Pas de reconnexion à la base si elle n'a pas changé"""
        self.confdb.start_db()
        yield self.confdb.get_hosts()
        old_connection_threads = set(self.confdb._db.connections.keys())
        self.confdb.reload()
        yield self.confdb.get_hosts()
        new_connection_threads = set(self.confdb._db.connections.keys())
        self.assertTrue(old_connection_threads <= new_connection_threads)

    def test_nodb(self):
        """La base n'existe pas"""
        confdb = ConfDB(os.path.join(self.tmpdir, "conf.db"))
        self.assertRaises(NoConfDBError, confdb.start_db)

    def test_reload_nodb(self):
        """Rechargement alors que la base n'existe pas"""
        confdb = ConfDB(os.path.join(self.tmpdir, "conf.db"))
        self.assertEqual(confdb.reload(), None)


