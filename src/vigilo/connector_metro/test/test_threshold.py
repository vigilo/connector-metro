# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2012 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import unittest

# ATTENTION: ne pas utiliser twisted.trial, car nose va ignorer les erreurs
# produites par ce module !!!
#from twisted.trial import unittest
from nose.twistedtools import reactor, deferred

from mock import Mock
from twisted.internet import defer

from vigilo.connector.test.helpers import ConsumerStub
from vigilo.connector_metro import threshold
from vigilo.connector_metro.exceptions import MissingConfigurationData


class ThresholdTestCase(unittest.TestCase):

    def test_inside_range(self):
        """
        Seuils tels que les valeurs sont à l'intérieur de l'intervalle.
        """
        data = {
            '10': [0, 10],
            '10:': [10, float("inf")],
            '~:10': [float("-inf"), 0, 10],
            '10:20': [10, 15, 20],
            '@10:20': [float("-inf"), 0, 9.9, 20.1, float("inf")],
        }
        for thresh, values in data.iteritems():
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                self.assertFalse(
                    threshold.is_out_of_bounds(value, thresh),
                    "Could not assert %r is inside the range defined by %r" % \
                        (value, thresh)
                )

    def test_outside_range(self):
        """
        Seuils tels que les valeurs sont à l'extérieur de l'intervalle.
        """
        data = {
            '10': [-0.1, 10.1],
            '10:': [0, 9.99],
            '~:10': [10.1, float("inf")],
            '10:20': [float("-inf"), 0, 9.99, 20.1, float("inf")],
            '@10:20': [10, 15, 20],
        }
        for thresh, values in data.iteritems():
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                self.assertTrue(
                    threshold.is_out_of_bounds(value, thresh),
                    "Could not assert %r is outside the range defined by %r" % \
                        (value, thresh)
                )

    def test_invalid_range(self):
        """Seuil non valide."""
        self.assertRaises(ValueError, threshold.is_out_of_bounds, 1, '4:2')



class ThresholdCheckerTestCase(unittest.TestCase):


    def setUp(self):
        self.tc = threshold.ThresholdChecker(Mock(), Mock())
        self.tc._check_thresholds_synchronously = True
        self.tc.consumer = ConsumerStub()
        self.tc.resumeProducing()


    @deferred(timeout=30)
    def test_alerts_required_attrs(self):
        self.tc.confdb.get_datasource.return_value = defer.succeed(None)
        self.tc.rrdtool.getLastValue.return_value = defer.fail(
                MissingConfigurationData("dummy"))
        d = self.tc.checkMessage({"host": "dummy", "datasource": "dummy"})
        def check(result):
            self.assertTrue(result is None)
        d.addCallback(check)
        return d


    @deferred(timeout=30)
    def test_alerts(self):
        """Fonction _compare_thresholds"""
        # Positionne l'heure courante à "42" (timestamp UNIX) systématiquement.
        self.tc.get_current_time = lambda: 42

        msg_tpl = {
            'type': "nagios",
            'routing_key': "ventilation_group",
            'timestamp': 42,
            'host': "server1.example.com",
            'cmdname': "PROCESS_SERVICE_CHECK_RESULT",
        }
        msg_value_tpl = "server1.example.com;MetroLoad;%(state)d;%(msg)s"
        testdata = {
            # 0 est là pour détecter les erreurs de comparaison
            # (if x: ... au lieu de if x is None: ...)
            0:    msg_value_tpl % {'state': 0, 'msg': 'OK: 0'},
            0.80: msg_value_tpl % {'state': 0, 'msg': 'OK: 0.8'},
            0.81: msg_value_tpl % {'state': 1, 'msg': 'WARNING: 0.81'},
            0.91: msg_value_tpl % {'state': 2, 'msg': 'CRITICAL: 0.91'},
            None: msg_value_tpl % {'state': 3, 'msg': 'UNKNOWN'},
        }
        ds = {"hostname": "server1.example.com",
              "datasource": "Load",
              "step": 300,
              "factor": 1,
              "warning_threshold": "0.8",
              "critical_threshold": "0.9",
              "nagiosname": "MetroLoad",
              "ventilation": "ventilation_group",
              }

        def check_result(dummy, value, expected):
            print "Checking results for value %r" % value
            expected_msg = msg_tpl.copy()
            expected_msg["value"] = expected
            print self.tc.consumer.written
            if value is None:
                # Une valeur UNKNOWN ne doit pas générer d'alerte
                # (on utilise la direction freshness_threshold de Nagios).
                self.assertEquals(0, len(self.tc.consumer.written),
                    "Pas d'alerte pour un état UNKNOWN")
            else:
                self.assertTrue(len(self.tc.consumer.written) > 0)
                self.assertEquals(expected_msg, self.tc.consumer.written[-1])
            # On vide la file de message pour permettre
            # la vérification suivante dans ce test.
            self.tc.consumer.written = []

        # Ne pas utiliser une DeferredList, ou alors avec les paramètres
        # fireOnOneErrback=True et consumeErrors=True
        # (mais ça fait de moins belles erreurs)
        d = defer.succeed(None)
        for value, expected in testdata.iteritems():
            d.addCallback(lambda x: self.tc._compare_thresholds(value, ds))
            d.addCallback(check_result, value, expected)
        return d


    @deferred(timeout=30)
    def test_alerts_unicode(self):
        """Fonction _compare_thresholds (unicode, #884)"""
        # Positionne l'heure courante à "42" (timestamp UNIX) systématiquement.
        self.tc.get_current_time = lambda: 42

        msg_tpl = {
            'type': "nagios",
            'routing_key': "ventilation_group",
            'timestamp': 42,
            'host': u"Host éçà",
            'cmdname': "PROCESS_SERVICE_CHECK_RESULT",
        }
        msg_value_tpl = u"Host éçà;Nagios' éçà;%(state)d;%(msg)s"
        testdata = {
            # 0 est là pour détecter les erreurs de comparaison
            # (if x: ... au lieu de if x is None: ...)
            0:    msg_value_tpl % {'state': 0, 'msg': 'OK: 0'},
            0.80: msg_value_tpl % {'state': 0, 'msg': 'OK: 0.8'},
            0.81: msg_value_tpl % {'state': 1, 'msg': 'WARNING: 0.81'},
            0.91: msg_value_tpl % {'state': 2, 'msg': 'CRITICAL: 0.91'},
            None: msg_value_tpl % {'state': 3, 'msg': 'UNKNOWN'},
        }
        ds = {"hostname": u"Host éçà",
              "datasource": u"PDS éçà",
              "step": 300,
              "factor": 1,
              "warning_threshold": u"0.8",
              "critical_threshold": u"0.9",
              "nagiosname": u"Nagios' éçà",
              "ventilation": "ventilation_group",
              }

        def check_result(dummy, value, expected):
            print "Checking results for value %r" % value
            expected_msg = msg_tpl.copy()
            expected_msg["value"] = expected
            print self.tc.consumer.written
            if value is None:
                # Une valeur UNKNOWN ne doit pas générer d'alerte
                # (on utilise la direction freshness_threshold de Nagios).
                self.assertEquals(0, len(self.tc.consumer.written),
                    "Pas d'alerte pour un état UNKNOWN")
            else:
                self.assertTrue(len(self.tc.consumer.written) > 0)
                self.assertEquals(expected_msg, self.tc.consumer.written[-1])
            # On vide la file de message pour permettre
            # la vérification suivante dans ce test.
            self.tc.consumer.written = []

        # Ne pas utiliser une DeferredList, ou alors avec les paramètres
        # fireOnOneErrback=True et consumeErrors=True
        # (mais ça fait de moins belles erreurs)
        d = defer.succeed(None)
        for value, expected in testdata.iteritems():
            d.addCallback(lambda x: self.tc._compare_thresholds(value, ds))
            d.addCallback(check_result, value, expected)
        return d


