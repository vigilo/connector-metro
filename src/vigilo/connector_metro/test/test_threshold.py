# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import unittest
from vigilo.connector_metro import threshold


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
            result = self.ntrf._get_last_value(ds, {"host": "dummy_host"})
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
