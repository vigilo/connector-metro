# -*- coding: utf-8 -*-
'''
Created on 14 oct. 2009

@author: tburguie
'''
# Teste la creation d'un fichier RRD
from __future__ import absolute_import

#import unittest
from twisted.trial import unittest
import tempfile
import os
import stat
from shutil import rmtree

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
        conf = """# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# the directory to store RRD file
RRD_BASE_DIR = '/tmp/rrd.test'

# the path to rrdtool binary
RRD_BIN = '/usr/bin/rrdtool'

# Init the hashmap (mandatory)
HOSTS = {}

# In this setup, we create one RRD per DS,
# each in a folder named after the host.
# All the RRDs have the same RRAs.
HOSTS["server1.example.com"] = {}

HOSTS["server1.example.com"]["Load"] = {
    "step": 300,
    "RRA": [
        # on garde ~ deux jours de donnée complète (5 minutes de précision)
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 },
        # on garde ~ deux semaines précision 30 minutes
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 },
        # on garde ~ deux mois précision 2 h
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 },
        # on garde ~ deux ans précision 1 jour
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797}
    ],
    "DS": {"name": "DS", "type": "GAUGE",
            "heartbeat": 600, "min": "U", "max": "U"},
}

# A B/C\\D.E%F => A+B%2FC%5CD.E%25F
HOSTS["server1.example.com"]["A B/C\\D.E%F"] = {
    "step": 300,
    "RRA": [
        # on garde ~ deux jours de donnée complète (5 minutes de précision)
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 },
        # on garde ~ deux semaines précision 30 minutes
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 },
        # on garde ~ deux mois précision 2 h
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 },
        # on garde ~ deux ans précision 1 jour
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797}
    ],
    "DS": {"name": "DS", "type": "GAUGE",
            "heartbeat": 600, "min": "U", "max": "U"},
}
"""
        conf_h, self.confpath = tempfile.mkstemp()
        os.write(conf_h, conf)
        os.close(conf_h)
        self.ntrf = NodeToRRDtoolForwarder(self.confpath)

    def tearDown(self):
        """Destruction des objets de test."""
        rmtree(settings['connector-metro']['rrd_base_dir'])
        self.ntrf.stop()
        os.remove(self.confpath)


    def test_handled_host(self):
        """Prise en compte de messages sur des hôtes déclarés."""

        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|server1.example.com|Load|12")
        d = self.ntrf.forwardMessage(xml)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        return d.addCallback(cb)

    def test_unhandled_host(self):
        """Le connecteur doit ignorer les hôtes non-déclarés."""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "unknown.example.com", "Load.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|unknown.example.com|Load|12")
        d = self.ntrf.forwardMessage(xml)
        # on vérifie que le fichier correspondant n'a pas été créé
        def cb(_):
            self.assertRaises(OSError, os.stat, rrdfile)
        return d.addCallback(cb)

    def test_non_existing_host(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",}
        self.assertRaises(NotInConfiguration, self.ntrf.createRRD,
                          "/tmp/nonexistant", msg)

    def test_special_chars_in_pds_name(self):
        """Caractères spéciaux dans le nom de la source de données."""
        rrdfile = os.path.join(settings['connector-metro']['rrd_base_dir'],
                               "server1.example.com", "A+B%2FC%5CD.E%25F.rrd")
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on teste le fichier).
        self.assertRaises(OSError, os.stat, rrdfile)
        xml = text2xml("perf|1165939739|server1.example.com|A B/C\\D.E%F|42")
        d = self.ntrf.forwardMessage(xml)
        # on vérifie que le fichier correspondant a bien été créé
        def cb(_):
            self.assertTrue(stat.S_ISREG(os.stat(rrdfile).st_mode))
        d.addCallback(cb)
        return d



if __name__ == "__main__":
    unittest.main()
