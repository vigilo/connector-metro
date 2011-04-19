# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree, copy
import sqlite3
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from twisted.internet import defer

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.connector.test.helpers import wait

from vigilo.connector_metro.vigiconf_settings import ConfDB, NoConfDBError


class ConfDBTest(unittest.TestCase):
    """
    Gestion du protocole SNMP entre avec le démon
    """

    @deferred(timeout=5)
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        dbpath_orig = os.path.join(os.path.dirname(__file__),
                                   "connector-metro.db")
        dbpath = os.path.join(self.tmpdir, "conf.db")
        copy(dbpath_orig, dbpath)
        self.confdb = ConfDB(dbpath)
        d = wait(0.1)
        def stop_task(r):
            self.confdb._reload_task.stop()
        d.addCallback(stop_task)
        return d

    def tearDown(self):
        self.confdb.stop()
        rmtree(self.tmpdir)

    @deferred(timeout=30)
    @defer.inlineCallbacks
    def test_reload(self):
        """Reconnexion à la base"""
        self.confdb.start_db()
        old_hosts = yield self.confdb.get_hosts()
        # On change le fichier de la base de données
        dbpath = os.path.join(self.tmpdir, "conf.db")
        os.rename(dbpath, dbpath + ".orig.db")
        copy(dbpath + ".orig.db", dbpath)
        # On modifie la base de données
        conn = sqlite3.connect(dbpath)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM perfdatasource")
        conn.commit()
        cursor.close()
        conn.close()
        # Reload et test
        self.confdb.reload()
        new_hosts = yield self.confdb.get_hosts()
        self.assertNotEqual(len(old_hosts), len(new_hosts))

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
        confdb = ConfDB(os.path.join(self.tmpdir, "nonexistant.db"))
        self.assertRaises(NoConfDBError, confdb.start_db)

    def test_reload_nodb(self):
        """Rechargement alors que la base n'existe pas"""
        confdb = ConfDB(os.path.join(self.tmpdir, "nonexistant.db"))
        self.assertEqual(confdb.reload(), None)


