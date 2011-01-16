# -*- coding: utf-8 -*-
'''
Created on 14 oct. 2009

@author: tburguie
'''
# Teste la creation d'un fichier RRD
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

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder, \
                                                 NotInConfiguration
from vigilo.connector.converttoxml import text2xml


class TestCreateRRDFile(unittest.TestCase):
    """
    Message from BUS forward(XMPP BUS)
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """

    def setUp(self):
        """Initialisation du test."""
        #unittest.TestCase.setUp(self)

        #self.stub = XmlStreamStub()
        #self.protocol.xmlstream = self.stub.xmlstream
        #self.protocol.connectionInitialized()
        self.tmpdir = tempfile.mkdtemp(prefix="test-connector-metro-")
        settings['connector-metro']['rrd_base_dir'] = \
                os.path.join(self.tmpdir, "rrds")
        os.mkdir(settings['connector-metro']['rrd_base_dir'])
        self.ntrf = NodeToRRDtoolForwarder(os.path.join(os.path.dirname(__file__), "connector-metro.db"))

    def tearDown(self):
        """Destruction des objets de test."""
        self.ntrf.stop()
        rmtree(self.tmpdir)


    @deferred(timeout=5)
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
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        return d.addCallback(cb)

    @deferred(timeout=5)
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

    @deferred(timeout=5)
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
        d.addCallbacks(lambda x: self.fail("No exception raised"), check_failure)
        return d

    @deferred(timeout=5)
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



if __name__ == "__main__":
    unittest.main()
