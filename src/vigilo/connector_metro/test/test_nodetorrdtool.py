# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212

from __future__ import absolute_import

import tempfile
import os
import stat
from shutil import rmtree
import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from vigilo.connector.test.helpers import XmlStreamStub

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder
from vigilo.connector_metro.nodetorrdtool import NotInConfiguration
from vigilo.connector_metro.nodetorrdtool import WrongMessageType
from vigilo.connector_metro.nodetorrdtool import InvalidMessage
from vigilo.connector.converttoxml import text2xml

from .helpers import RRDToolManagerStub


class NodeToRRDtoolForwarderTest(unittest.TestCase):
    """
    Message from BUS forward(XMPP BUS)
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """

    def setUp(self):
        """Initialisation du test."""
        #unittest.TestCase.setUp(self)

        self.stub = XmlStreamStub()
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        settings['connector-metro']['rrd_base_dir'] = \
                os.path.join(self.tmpdir, "rrds")
        os.mkdir(settings['connector-metro']['rrd_base_dir'])
        self.ntrf = NodeToRRDtoolForwarder(os.path.join(
                        os.path.dirname(__file__), "connector-metro.db"))
        self.ntrf.xmlstream = self.stub.xmlstream
        self.rrdtool = RRDToolManagerStub()
        self.ntrf.rrdtool = self.rrdtool
        self.ntrf.connectionInitialized()

    def tearDown(self):
        """Destruction des objets de test."""
        self.ntrf.stop()
        rmtree(self.tmpdir)


    @deferred(timeout=30)
    def test_handled_host(self):
        """Prise en compte de messages sur des hôtes déclarés."""

        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|server1.example.com|Load|12")
        d = self.ntrf.processMessage(xml)
        # on vérifie que le fichier correspondant a bien été créé
        def check_created(r):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        def check_creation_command(r):
            self.assertEqual(self.rrdtool.commands[0], ('create', rrdfile,
                ['--step', '300', '--start', '1165939729',
                 'RRA:AVERAGE:0.5:1:600', 'RRA:AVERAGE:0.5:6:700',
                 'RRA:AVERAGE:0.5:24:775', 'RRA:AVERAGE:0.5:288:732',
                 'DS:DS:GAUGE:600:U:U']))
        def check_update_command(r):
            self.assertEqual(self.rrdtool.commands[1],
                             ('update', rrdfile, '1165939739:12'))
        d.addCallback(check_created)
        d.addCallback(check_creation_command)
        d.addCallback(check_update_command)
        return d

    @deferred(timeout=30)
    def test_unhandled_host(self):
        """Le connecteur doit ignorer les hôtes non-déclarés."""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "unknown.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|unknown.example.com|Load|12")
        d = self.ntrf.processMessage(xml)
        # on vérifie que le fichier correspondant n'a pas été créé
        def cb(_):
            self.assertRaises(OSError, os.stat, rrdfile)
        return d.addCallback(cb)

    @deferred(timeout=30)
    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",}
        d = self.ntrf.createRRD("/tmp/nonexistant", msg)
        def check_failure(f):
            if not isinstance(f.value, NotInConfiguration):
                self.fail("Raised exeception is not of the right type (got %s)"
                          % type(f.value))
        d.addCallbacks(lambda x: self.fail("No exception raised"),
                       check_failure)
        return d

    @deferred(timeout=30)
    def test_special_chars_in_pds_name(self):
        """Caractères spéciaux dans le nom de la source de données."""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "A+B%2FC%5CD.E%25F.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|server1.example.com|A B/C\\D.E%F|42")
        d = self.ntrf.processMessage(xml)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_special_chars_in_host_name(self):
        """Caractères spéciaux dans le nom de l'hôte (#454)."""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "A+b%2Fc.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|A b/c.example.com|Load|42")
        d = self.ntrf.processMessage(xml)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_wrong_message_type_1(self):
        """Réception d'un autre message que perf (_parse_message)"""
        xml = text2xml("event|1165939739|host|service|CRITICAL|message")
        d = self.ntrf._parse_message(xml)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, WrongMessageType)
        d.addCallbacks(cb, eb)
        return d

    @deferred(timeout=30)
    def test_wrong_message_type_2(self):
        """Réception d'un autre message que perf (processMessage)"""
        xml = text2xml("event|1165939739|host|service|CRITICAL|message")
        d = self.ntrf.processMessage(xml)
        def cb(r):
            self.assertEqual(len(self.ntrf.rrdtool.commands), 0)
            self.assertEqual(self.ntrf._messages_forwarded, -1)
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_invalid_message_1(self):
        """Réception d'un message invalide (_parse_message)"""
        xml = text2xml("perf|1165939739|unknown.example.com|Load|12")
        del xml.children[0]
        d = self.ntrf._parse_message(xml)
        def cb(r):
            self.fail("Il y aurait dû y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, InvalidMessage)
        d.addCallbacks(cb, eb)
        return d

    @deferred(timeout=30)
    def test_invalid_message_2(self):
        """Réception d'un message invalide (processMessage)"""
        xml = text2xml("perf|1165939739|unknown.example.com|Load|12")
        del xml.children[0]
        d = self.ntrf.processMessage(xml)
        def cb(r):
            self.assertEqual(len(self.ntrf.rrdtool.commands), 0)
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_already_created(self):
        """Pas de création si le fichier existe déjà"""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "Load.rrd")
        os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close()
        msg = {"timestamp": "123456789",
               "host": "server1.example.com",
               "datasource": "Load",
               "value": "42",}
        d = self.ntrf.create_if_needed(msg)
        def cb(r):
            self.assertEqual(len(self.ntrf.rrdtool.commands), 0)
        d.addCallback(cb)
        return d

    @deferred(timeout=30)
    def test_stats(self):
        """Statistiques"""
        d = self.ntrf.getStats()
        def cb(r):
            self.assertEqual(r, {'queue': 0, 'forwarded': 0, 'pds_count': 3})
        d.addCallback(cb)
        return d

