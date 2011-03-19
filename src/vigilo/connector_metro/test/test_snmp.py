# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613

from __future__ import absolute_import

import tempfile
import os
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from twisted.internet import defer

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.connector_metro.snmp import SNMPProtocol, SNMP_ENTERPRISE_OID
from vigilo.connector_metro.snmp import RRDNoDataError, NoSuchRRDFile
from vigilo.connector_metro.snmp import SNMPtoRRDTool

from .helpers import RRDToolManagerStub, TransportStub


class FakeParent(object):
    def __init__(self):
        self.calls = []
        self.fail = False
    def start(self):
        self.calls.append("start")
        return defer.succeed(None)
    def quit(self):
        self.calls.append("quit")
    def get(self, oid):
        self.calls.append(("get", oid))
        if self.fail:
            return defer.fail(self.fail("dummy result"))
        else:
            return defer.succeed("dummy result")

class SNMPProtocolTest(unittest.TestCase):
    """
    Gestion du protocole SNMP entre avec le démon
    """

    def setUp(self):
        self.transport = TransportStub()
        self.parent = FakeParent()
        self.snmp = SNMPProtocol(self.parent)
        self.snmp.transport = self.transport
        self.snmp.connectionMade()


    def test_received_nothing(self):
        """Rien reçu"""
        self.snmp.lineReceived("")
        self.assertEqual(self.transport.getvalue(), "Goodbye.\n")

    def test_received_quit(self):
        """Reçu: quit"""
        self.snmp.lineReceived("quit\n")
        self.assertEqual(self.transport.getvalue(), "Goodbye.\n")

    def test_received_PING(self):
        """Reçu: PING"""
        self.snmp.lineReceived("PING\n")
        self.assertEqual(self.parent.calls, ["start", ])
        self.assertEqual(self.transport.getvalue(), "PONG\n")

    def test_received_set(self):
        """Reçu: set"""
        self.snmp.lineReceived("set\n")
        self.snmp.lineReceived("fake_oid\n")
        self.snmp.lineReceived("fake_value\n")
        self.assertEqual(self.transport.getvalue(), "not-writable\n")

    def test_received_getnext(self):
        """Reçu: getnext"""
        self.snmp.lineReceived("getnext\n")
        self.snmp.lineReceived("fake_oid\n")
        self.assertEqual(self.transport.getvalue(), "NONE\n")

    def test_received_get_outside(self):
        """Reçu: get avec un OID hors de notre contrôle"""
        oid = "1.2.3.4.5.6.7.8.9.10.11.12.13.14.42"
        self.snmp.lineReceived("get\n")
        self.snmp.lineReceived(oid+"\n")
        self.assertEqual(self.transport.getvalue(), "NONE\n")

    def test_received_get(self):
        """Reçu: get avec un bon OID"""
        oid = ".1.3.6.1.4.1.%s.24.42" % SNMP_ENTERPRISE_OID
        self.snmp.lineReceived("get\n")
        self.snmp.lineReceived(oid+"\n")
        self.assertEqual(self.parent.calls, [("get", oid), ])
        self.assertEqual(self.transport.getvalue(),
                "%s\ngauge\ndummy result\n" % oid)

    def test_received_get_nodata(self):
        """Gestion de RRDNoDataError"""
        self.parent.fail = RRDNoDataError
        oid = ".1.3.6.1.4.1.%s.24.42" % SNMP_ENTERPRISE_OID
        self.snmp.lineReceived("get\n")
        self.snmp.lineReceived(oid+"\n")
        self.assertEqual(self.parent.calls, [("get", oid), ])
        self.assertEqual(self.transport.getvalue(),
                "%s\nstring\ndummy result\n" % oid)

    def test_received_get_norrd(self):
        """Gestion de NoSuchRRDFile"""
        self.parent.fail = NoSuchRRDFile
        oid = ".1.3.6.1.4.1.%s.24.42" % SNMP_ENTERPRISE_OID
        self.snmp.lineReceived("get\n")
        self.snmp.lineReceived(oid+"\n")
        self.assertEqual(self.parent.calls, [("get", oid), ])
        self.assertEqual(self.transport.getvalue(),
                "%s\nstring\ndummy result\n" % oid)

    def test_received_get_other_error(self):
        """Gestion d'une exception quelconque"""
        self.parent.fail = Exception
        oid = ".1.3.6.1.4.1.%s.24.42" % SNMP_ENTERPRISE_OID
        self.snmp.lineReceived("get\n")
        self.snmp.lineReceived(oid+"\n")
        self.assertEqual(self.parent.calls, [("get", oid), ])
        self.assertEqual(self.transport.getvalue(), "NONE\n")

    def test_received_unknown_command(self):
        """Reçu une commande inconnue"""
        self.snmp.lineReceived("does_not_exist\n")
        self.assertEqual(self.transport.getvalue(),
                         "ERROR: no such command: does_not_exist\n")

    def test_connection_lost(self):
        """Perte de connexion avec le démon SNMP"""
        self.snmp.connectionLost(None)
        self.assertEqual(self.parent.calls, ["quit", ])


class SNMPtoRRDToolTest(unittest.TestCase):
    """
    Gestion de la communication entre le protocole SNMP est le pool de
    processus RRDTool
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        settings['connector-metro']['rrd_base_dir'] = \
                os.path.join(self.tmpdir, "rrds")
        os.mkdir(settings['connector-metro']['rrd_base_dir'])
        settings['connector-metro']['config'] = os.path.join(
                        os.path.dirname(__file__), "connector-metro.db")
        self.snmp = SNMPtoRRDTool()
        self.snmp.quit = lambda: None # pour éviter de faire un reactor.stop
        self.rrdtool = RRDToolManagerStub()
        self.snmp.rrdtool = self.rrdtool

    def tearDown(self):
        """Destruction des objets de test."""
        self.snmp.confdb.stop()
        rmtree(self.tmpdir)

    def test_oid_to_rrdfile(self):
        """Traduction d'un OID en nom de fichier"""
        filename = "dummy/file/name"
        oid = ".1.3.6.1.4.1.%s." % SNMP_ENTERPRISE_OID
        oid += ".".join([str(ord(c)) for c in filename])
        self.assertEqual(self.snmp.oid_to_rrdfile(oid), filename)

    def test_oid_to_rrdfile_fail(self):
        """Problème dans la traduction d'un OID en nom de fichier"""
        filename = "dummy"
        oid = ".1.3.6.1.4.1.%s." % SNMP_ENTERPRISE_OID
        oid += ".".join([str(ord(c)) for c in filename])
        self.assertRaises(ValueError, self.snmp.oid_to_rrdfile, oid)

    def test_rrdtool_result_empty(self):
        """Sortie de RRDTool: vide"""
        self.assertRaises(RRDNoDataError, self.snmp.rrdtool_result, "", None)

    def test_rrdtool_result_only_nan(self):
        """Sortie de RRDTool: uniquement des NaN"""
        output = "123456789: nan\n"
        self.assertRaises(RRDNoDataError,
                          self.snmp.rrdtool_result, output, None)

    def test_rrdtool_result_simple(self):
        """Sortie de RRDTool: cas simple"""
        output = "123456789: 42\n"
        self.assertEqual(self.snmp.rrdtool_result(output, None), "42")

    def test_rrdtool_result_useless_data(self):
        """Les données inutiles doivent être ignorées"""
        output = "  useless data   \n123456789: 42\n"
        self.assertEqual(self.snmp.rrdtool_result(output, None), "42")

    def test_rrdtool_result_exponent(self):
        """Gestion des valeurs avec exposants"""
        output = "123456789: 4.2e2\n"
        self.assertEqual(self.snmp.rrdtool_result(output, None), "420.0")

    def test_rrdtool_result_choose_last(self):
        """Il faut choisir la dernière valeur"""
        output = "123456789: 41\n123456789: 42\n"
        self.assertEqual(self.snmp.rrdtool_result(output, None), "42")

    def test_rrdtool_result_ignore_nan(self):
        """Les lignes avec NaN doivent être ignorées"""
        output = "123456789: 42\n123456789: nan\n"
        self.assertEqual(self.snmp.rrdtool_result(output, None), "42")

    @deferred(timeout=30)
    def test_get_inexistant_filename(self):
        """Fichier RRD inexistant"""
        filename = "dummy/file/name"
        oid = ".1.3.6.1.4.1.%s." % SNMP_ENTERPRISE_OID
        oid += ".".join([str(ord(c)) for c in filename])
        d = self.snmp.get(oid)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, NoSuchRRDFile)
        d.addCallbacks(cb, eb)
        return d

    @deferred(timeout=30)
    def test_get_inexistant_datasource(self):
        """Indicateur inexistant en base de config"""
        filename = "dummy/filename"
        oid = ".1.3.6.1.4.1.%s." % SNMP_ENTERPRISE_OID
        oid += ".".join([str(ord(c)) for c in filename])
        # on crée le fichier
        filepath = os.path.join(settings['connector-metro']['rrd_base_dir'],
                                filename + ".rrd")
        os.makedirs(os.path.dirname(filepath))
        open(filepath, "w").close()
        # go
        d = self.snmp.get(oid)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, NoSuchRRDFile)
        d.addCallbacks(cb, eb)
        return d

    @deferred(timeout=30)
    def test_get(self):
        """Récupération d'une valeur par RRDtool"""
        # oid
        filename = "server1.example.com/Load"
        oid = ".1.3.6.1.4.1.%s." % SNMP_ENTERPRISE_OID
        oid += ".".join([str(ord(c)) for c in filename])
        # on crée le fichier
        filepath = os.path.join(settings['connector-metro']['rrd_base_dir'],
                                filename + ".rrd")
        os.makedirs(os.path.dirname(filepath))
        open(filepath, "w").close()
        # on inhibe la fonction de sortie pour ne pas avoir à retourner une
        # valeur correcte
        def pass_result(r, oid):
            return r
        self.snmp.rrdtool_result = pass_result
        # go
        d = self.snmp.get(oid)
        def cb(r):
            self.assertEqual(len(self.rrdtool.commands), 1)
            self.assertEqual(self.rrdtool.commands[0],
                    ("fetch", filepath, ['AVERAGE', '--start', '-900']))
        d.addCallback(cb)
        return d


