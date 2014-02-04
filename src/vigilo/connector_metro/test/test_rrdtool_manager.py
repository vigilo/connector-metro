# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613
# Copyright (C) 2006-2014 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Test des classes RRDToolManager et RRDToolProcessProtocol
"""

# Teste la creation d'un fichier RRD
from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from mock import Mock

from twisted.internet import defer

from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.confdb import MetroConfDB
from vigilo.connector_metro.exceptions import NotInConfiguration
from vigilo.connector_metro.exceptions import MissingConfigurationData



class RRDToolManagerTestCase(unittest.TestCase):


    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        self.rrd_base_dir = os.path.join(self.tmpdir, "rrds")
        os.mkdir(self.rrd_base_dir)

        confdb = MetroConfDB(os.path.join(os.path.dirname(__file__),
                                     "connector-metro.db"))
        confdb.reload()
        rrdtool = Mock()
        rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(None)
        rrdtool.rrd_base_dir = self.rrd_base_dir
        rrdtool.rrd_path_mode = "flat"
        self.mgr = RRDToolManager(rrdtool, confdb)
        self.mgr._fixperms = Mock()

    def tearDown(self):
        self.mgr.confdb._db.close()
        rmtree(self.tmpdir)


    @deferred(timeout=30)
    def test_create_needed(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                }
        d = self.mgr.createIfNeeded(msg)
        def check(_ignored):
            print self.mgr.rrdtool.run.call_args_list
            self.assertEqual(len(self.mgr.rrdtool.run.call_args_list), 1)
            self.assertEqual(self.mgr.rrdtool.run.call_args_list[0][0],
                    ('create', self.rrd_base_dir+"/server1.example.com/Load.rrd",
                    ['--step', '300', '--start', '1165939729',
                     'RRA:AVERAGE:0.5:1:600', 'RRA:AVERAGE:0.5:6:700',
                     'RRA:AVERAGE:0.5:24:775', 'RRA:AVERAGE:0.5:288:732',
                     'DS:DS:GAUGE:600:U:U']))
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_already_created(self):
        """Pas de création si le fichier existe déjà"""
        rrdfile = os.path.join(self.rrd_base_dir,
                               "server1.example.com", "Load.rrd")
        os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close()
        msg = { "type": "perf",
                "timestamp": "123456789",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "42",
                }
        d = self.mgr.createIfNeeded(msg)
        def check(r):
            self.assertFalse(self.mgr.rrdtool.run.called)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_update(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "Load",
                "value": "12",
                "has_thresholds": False,
                }
        #self.mgr.getFilename = Mock(return_value=self.rrd_base_dir+"")
        #self.mgr.getOldFilename = Mock(return_value=self.rrd_base_dir+"")
        d = self.mgr.processMessage(msg)
        def check(_ignored):
            print self.mgr.rrdtool.run.call_args_list
            self.assertEqual(len(self.mgr.rrdtool.run.call_args_list), 1)
            self.assertEqual(self.mgr.rrdtool.run.call_args_list[0][0],
                     ('update', self.rrd_base_dir+"/server1.example.com/Load.rrd",
                      '1165939739:12'))
        d.addCallback(check)
        return d


    def test_special_chars_in_pds_name(self):
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "server1.example.com",
                "datasource": "A B/C\\D.E%F",
                "value": "42",
                }
        print self.mgr.getFilename(msg)
        expected = (self.rrd_base_dir+"/server1.example.com/"
                    "A+B%2FC%5CD.E%25F.rrd")
        self.assertEqual(expected, self.mgr.getFilename(msg))


    def test_special_chars_in_host_name(self):
        """Caractères spéciaux dans le nom de l'hôte (#454)."""
        msg = { "type": "perf",
                "timestamp": "1165939739",
                "host": "A b/c.example.com",
                "datasource": "Load",
                "value": "42",
                }
        print self.mgr.getFilename(msg)
        expected = self.rrd_base_dir+"/A+b%2Fc.example.com/Load.rrd"
        self.assertEqual(expected, self.mgr.getFilename(msg))


    @deferred(timeout=30)
    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"type": "perf",
               "timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",
               }
        d = self.mgr._create(self.rrd_base_dir+"/nonexistant", msg)
        def check_failure(f):
            if not isinstance(f.value, NotInConfiguration):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        d.addCallbacks(lambda x: self.fail("No exception raised"),
                       check_failure)
        return d


    @deferred(timeout=30)
    def test_missing_ds_data(self):
        msg = {"host": "dummy_host",
               "datasource": "dummy_datasource"}
        full_ds = {"host": "dummy_host",
                   "datasource": "dummy_datasource",
                   "step": 300,
                   "warning_threshold": "42",
                   "critical_threshold": "43",
                   "nagiosname": "Dummy Service",
                   "ventilation": "ventilation_group",
                   }
        required_attrs = [
            'warning_threshold',
            'critical_threshold',
            'nagiosname',
            'ventilation',
        ]
        def check_failure(f):
            if not isinstance(f.value, MissingConfigurationData):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        dl = []
        for attr in required_attrs:
            ds = full_ds.copy()
            ds[attr] = None
            d = self.mgr.getLastValue(ds, msg)
            d.addCallbacks(lambda x: self.fail(
                           "l'attribut %s devrait être obligatoire" % attr),
                           check_failure)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)


    @deferred(timeout=30)
    def test_last_value(self):
        msg = {"host": "dummy_host éçà",
               "datasource": "dummy_datasource éçà"}
        ds = {"host": "dummy_host éçà",
              "datasource": "dummy_datasource éçà",
              "step": 300,
              "warning_threshold": "42",
              "critical_threshold": "43",
              "nagiosname": "Dummy Service",
              "ventilation": "ventilation_group",
              }
        self.mgr.rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(
                "DS\n\ntimestamp: 42\n")
        d = self.mgr.getLastValue(ds, msg)
        def check(r):
            print r
            self.assertEqual(r, 42)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_last_value_no_rrdcached(self):
        """Ne pas utiliser RRDCached s'il y a des seuils"""
        msg = {"host": "dummy_host éçà",
               "datasource": "dummy_datasource éçà"}
        ds = {"host": "dummy_host éçà",
              "datasource": "dummy_datasource éçà",
              "step": 300,
              "warning_threshold": "42",
              "critical_threshold": "43",
              "nagiosname": "Dummy Service",
              "ventilation": "ventilation_group",
              }
        self.mgr.rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(
                "DS\n\ntimestamp: 42\n")
        d = self.mgr.getLastValue(ds, msg)
        def check_no_rrdcached(r):
            print self.mgr.rrdtool.run.call_args_list
            for cmd in self.mgr.rrdtool.run.call_args_list:
                print cmd
                self.assertTrue("no_rrdcached" in cmd[1])
                self.assertTrue(cmd[1]["no_rrdcached"])
        d.addCallback(check_no_rrdcached)
        return d
