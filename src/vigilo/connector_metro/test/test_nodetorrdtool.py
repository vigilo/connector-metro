# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

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

from mock import Mock

from twisted.words.protocols.jabber.jid import JID
from twisted.internet import defer
from twisted.python.failure import Failure
from vigilo.connector.test.helpers import XmlStreamStub

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder
from vigilo.connector_metro.nodetorrdtool import NotInConfiguration
from vigilo.connector_metro.nodetorrdtool import WrongMessageType
from vigilo.connector_metro.nodetorrdtool import InvalidMessage
from vigilo.connector.converttoxml import text2xml
from vigilo.pubsub.xml import NS_COMMAND

from .helpers import RRDToolManagerStub


class NodeToRRDtoolForwarderTest(unittest.TestCase):
    """
    Message from BUS forward(XMPP BUS)
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """

    def setUp(self):
        self.stub = XmlStreamStub()
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        settings['connector-metro']['rrd_base_dir'] = \
                os.path.join(self.tmpdir, "rrds")
        os.mkdir(settings['connector-metro']['rrd_base_dir'])
        self.ntrf = NodeToRRDtoolForwarder(os.path.join(
                        os.path.dirname(__file__), "connector-metro.db"))
        self.ntrf.xmlstream = self.stub.xmlstream
        self.ntrf.parent = self
        self.jid = JID('foo@bar')
        self.rrdtool = RRDToolManagerStub()
        self.ntrf.rrdtool = self.rrdtool
        self.ntrf.connectionInitialized()

    def tearDown(self):
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
            self.assertTrue(len(self.rrdtool.commands) > 0)
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
    def test_valid_values(self):
        """Réception d'un message avec une valeur valide"""
        valid_values = ["1", "1.2", "U"]
        dl = []
        for value in valid_values:
            xml = text2xml("perf|1165939739|server1.example.com|Load|%s" % value)
            d = self.ntrf._parse_message(xml)
            dl.append(d)
        return defer.DeferredList(dl, fireOnOneErrback=True)

    @deferred(timeout=30)
    def test_invalid_value_1(self):
        """Réception d'un message avec une valeur invalide (#802)"""
        xml = text2xml("perf|1165939739|server1.example.com|Load|Invalid value")
        d = self.ntrf._parse_message(xml)
        def cb(r):
            self.fail("Il y aurait du y avoir un errback")
        def eb(f):
            self.assertEqual(f.type, InvalidMessage)
        d.addCallbacks(cb, eb)
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
            self.assertEqual(r, {
                'queue': 0,
                'forwarded': 0,
                'pds_count': 4,
                'sent': 0,
                'illegal_updates': 0,
            })
        d.addCallback(cb)
        return d

    #@deferred(timeout=30)
    def test_alerts_required_attrs(self):
        """Fonction _get_last_value"""
        full_ds = {"host": "dummy_host",
                   "datasource": "dummy_datasource",
                   "step": 300,
                   "warning_threshold": "42",
                   "critical_threshold": "43",
                   "nagiosname": "Dummy Service",
                   "jid": "foo@bar",
                   }
        required_attrs = [
            'warning_threshold',
            'critical_threshold',
            'nagiosname',
            'jid',
        ]
        self.ntrf._get_msg_filename = lambda x: "dummy_filename"
        self.ntrf.rrdtool.run = lambda *a: defer.succeed(None)
        self.ntrf._compare_thresholds = lambda ds, host: True
        for attr in required_attrs:
            ds = full_ds.copy()
            ds[attr] = None
            result = self.ntrf._get_last_value(
                ("AVERAGE", ds),
                {"host": "dummy_host"}
            )
            self.assertTrue(result is None,
                    "l'attribut %s devrait être obligatoire" % attr)

    @deferred(timeout=30)
    def test_alerts(self):
        """Fonction _compare_thresholds"""
        # Positionne l'heure courante à "42" (timestamp UNIX) systématiquement.
        self.ntrf.get_current_time = lambda: 42

        res_tpl = \
            "<message to='foo@bar' from='foo@bar' type='chat'><body>" \
            "<command xmlns='%s'>" \
                "<timestamp>42.000000</timestamp>" \
                "<cmdname>PROCESS_SERVICE_CHECK_RESULT</cmdname>" \
                "<value>server1.example.com;MetroLoad" \
                    ";%%(state)d;%%(msg)s</value>" \
            "</command>" \
            "</body></message>" % NS_COMMAND
        testdata = {
            # 0 est là pour détecter les erreurs de comparaison
            # (if x: ... au lieu de if x is None: ...)
            '0': res_tpl % {'state': 0, 'msg': 'OK: 0'},
            '0.80': res_tpl % {'state': 0, 'msg': 'OK: 0.8'},
            '0.81': res_tpl % {'state': 1, 'msg': 'WARNING: 0.81'},
            '0.91': res_tpl % {'state': 2, 'msg': 'CRITICAL: 0.91'},
            'nan': res_tpl % {'state': 3, 'msg': 'UNKNOWN'},
        }
        ds = {"hostname": "server1.example.com",
              "datasource": "Load",
              "step": 300,
              "factor": 1,
              "warning_threshold": "0.8",
              "critical_threshold": "0.9",
              "nagiosname": "MetroLoad",
              "jid": "foo@bar",
              }

        def check_result(dummy, value, expected):
            print "Checking results for value %r" % value
            print [el.toXml() for el in self.stub.output]
            if value == "nan":
                # Une valeur UNKNOWN ne doit pas générer d'alerte
                # (on utilise la direction freshness_threshold de Nagios).
                self.assertEquals(0, len(self.stub.output),
                    "Pas d'alerte pour un état UNKNOWN")
            else:
                self.assertTrue(len(self.stub.output) > 0)
                self.assertEquals(expected, self.stub.output[-1].toXml())
            # On vide la file de message pour permettre
            # la vérification suivante dans ce test.
            self.stub.output = []

        # Ne pas utiliser une DeferredList, ou alors avec les paramètres
        # fireOnOneErrback=True et consumeErrors=True
        # (mais ça fait de moins belles erreurs)
        d = defer.succeed(None)
        tpl = "DS\n\ntimestamp: %s\n"
        for value, expected in testdata.iteritems():
            d.addCallback(lambda x: self.ntrf._compare_thresholds(tpl % value, ds))
            d.addCallback(check_result, value, expected)
        return d

    @deferred(timeout=30)
    def test_alerts_unicode(self):
        """Fonction _compare_thresholds (unicode, #884)"""
        # Positionne l'heure courante à "42" (timestamp UNIX) systématiquement.
        self.ntrf.get_current_time = lambda: 42

        res_tpl = \
            u"<message to='foo@bar' from='foo@bar' type='chat'><body>" \
            u"<command xmlns='%s'>" \
                u"<timestamp>42.000000</timestamp>" \
                u"<cmdname>PROCESS_SERVICE_CHECK_RESULT</cmdname>" \
                u"<value>Host éçà;Nagios' éçà" \
                    u";%%(state)d;%%(msg)s</value>" \
            u"</command>" \
            u"</body></message>" % NS_COMMAND
        testdata = {
            # 0 est là pour détecter les erreurs de comparaison
            # (if x: ... au lieu de if x is None: ...)
            '0': res_tpl % {'state': 0, 'msg': 'OK: 0'},
            '0.80': res_tpl % {'state': 0, 'msg': 'OK: 0.8'},
            '0.81': res_tpl % {'state': 1, 'msg': 'WARNING: 0.81'},
            '0.91': res_tpl % {'state': 2, 'msg': 'CRITICAL: 0.91'},
            'nan': res_tpl % {'state': 3, 'msg': 'UNKNOWN'},
        }
        ds = {"hostname": u"Host éçà",
              "datasource": u"PDS éçà",
              "step": 300,
              "factor": 1,
              "warning_threshold": u"0.8",
              "critical_threshold": u"0.9",
              "nagiosname": u"Nagios' éçà",
              "jid": u"foo@bar",
              }

        def check_result(dummy, value, expected):
            print "Checking results for value %r" % value
            print [el.toXml() for el in self.stub.output]
            if value == "nan":
                # Une valeur UNKNOWN ne doit pas générer d'alerte
                # (on utilise la direction freshness_threshold de Nagios).
                self.assertEquals(0, len(self.stub.output),
                    "Pas d'alerte pour un état UNKNOWN")
            else:
                self.assertTrue(len(self.stub.output) > 0)
                self.assertEquals(expected, self.stub.output[-1].toXml())
            # On vide la file de message pour permettre
            # la vérification suivante dans ce test.
            self.stub.output = []

        # Ne pas utiliser une DeferredList, ou alors avec les paramètres
        # fireOnOneErrback=True et consumeErrors=True
        # (mais ça fait de moins belles erreurs)
        d = defer.succeed(None)
        tpl = "DS\n\ntimestamp: %s\n"
        for value, expected in testdata.iteritems():
            d.addCallback(lambda x: self.ntrf._compare_thresholds(tpl % value, ds))
            d.addCallback(check_result, value, expected)
        return d

    @deferred(timeout=30)
    def test_no_check_thresholds(self):
        """Désactivation de la vérification des seuils"""
        xml = text2xml("perf|1165939739|server1.example.com|Load|12")
        self.ntrf.must_check_thresholds = False
        self.ntrf._get_last_value = Mock()
        d = self.ntrf.processMessage(xml)
        def check_not_called(_r):
            self.assertFalse(self.ntrf._get_last_value.called)
        d.addCallback(check_not_called)
        return d

    @deferred(timeout=30)
    def test_no_check_thresholds_unicode(self):
        """Désactivation de la vérification des seuils (unicode, #884)"""
        xml = text2xml("perf|1165939739|Host éçà|PDS éçà|12")
        self.ntrf.must_check_thresholds = False
        self.ntrf._get_last_value = Mock()
        d = self.ntrf.processMessage(xml)
        def check_not_called(_r):
            self.assertFalse(self.ntrf._get_last_value.called)
        d.addCallback(check_not_called)
        return d

    @deferred(timeout=30)
    def test_no_rrdcached(self):
        """Ne pas utiliser RRDCached s'il y a des seuils"""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "Load.rrd")
        xml = text2xml("perf|1165939739|server1.example.com|Load|12")
        self.ntrf.createRRD = Mock(name="createRRD")
        self.ntrf.createRRD.side_effect = lambda x, y: defer.succeed(None)
        if not os.path.exists(os.path.dirname(rrdfile)):
            os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close() # touch
        self.ntrf.rrdtool.run = Mock(name="run")
        self.ntrf.rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(None)
        d = self.ntrf.processMessage(xml)
        def check_no_rrdcached(r):
            print self.ntrf.rrdtool.run.call_args_list
            for cmd in self.ntrf.rrdtool.run.call_args_list:
                print cmd
                self.assertTrue("no_rrdcached" in cmd[1])
                self.assertTrue(cmd[1]["no_rrdcached"])
        d.addCallback(check_no_rrdcached)
        return d

    @deferred(timeout=30)
    def test_no_rrdcached_unicode(self):
        """Ne pas utiliser RRDCached s'il y a des seuils (unicode, #884)"""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "Host%20%C3%A9%C3%A7%C3%A0",
                               "PDS%20%C3%A9%C3%A7%C3%A0.rrd")
        xml = text2xml("perf|1165939739|Host éçà|PDS éçà|12")
        self.ntrf.createRRD = Mock(name="createRRD")
        self.ntrf.createRRD.side_effect = lambda x, y: defer.succeed(None)
        if not os.path.exists(os.path.dirname(rrdfile)):
            os.makedirs(os.path.dirname(rrdfile))
        open(rrdfile, "w").close() # touch
        self.ntrf.rrdtool.run = Mock(name="run")
        self.ntrf.rrdtool.run.side_effect = lambda *a, **kw: defer.succeed(None)
        d = self.ntrf.processMessage(xml)
        def check_no_rrdcached(r):
            print self.ntrf.rrdtool.run.call_args_list
            for cmd in self.ntrf.rrdtool.run.call_args_list:
                print cmd
                self.assertTrue("no_rrdcached" in cmd[1])
                self.assertTrue(cmd[1]["no_rrdcached"])
        d.addCallback(check_no_rrdcached)
        return d
