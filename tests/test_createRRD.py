# -*- coding: utf-8 -*-
'''
Created on 14 oct. 2009

@author: tburguie
'''
# Teste la creation d'un fichier RRD 
from __future__ import absolute_import
import unittest
from vigilo.common.conf import settings, ConfigParseError
from vigilo.connector_metro.vigiconf_settings import vigiconf_settings
from wokkel import client
from twisted.words.protocols.jabber.jid import JID
from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder
from vigilo.connector.converttoxml import text2xml
import os
import stat

class TestCreateRRDFile(unittest.TestCase):
    """ 
    Message from BUS forward(XMPP BUS)
    Vérification que le passage d'un message produit bien un fichier RRD.
    (création du fichier)
    """
        
    def test_nodeToRRDtool(self):
        """Prise en compte de messages sur des hôtes déclarés."""

        conf = """# vim: set fileencoding=utf-8 sw=4 ts=4 et :
from urllib import quote
# the directory to store RRD file
RRD_BASE_DIR = '/tmp/rrd.test'
# the path to rrdtool binary
RRD_BIN = '/usr/bin/rrdtool'
# Init the hashmap (mandatory)
HOSTS = {}
# In this setup, we create one RRD per DS, each in a folder named after the host.
# All the RRDs have the same RRAs.
# Load for server1.example.com
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
    "DS": { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" },
}"""
        # on créer le fichier de conf

        file = open(settings['connector-metro']['config'], 'w')
        file.write(conf)
        file.close()
        conf_ = settings['connector-metro'].get('config', None)
        xmpp_client = client.XMPPClient(
            JID(settings['bus']['jid']),
            settings['bus']['password'],
            settings['bus']['host'])

        message_publisher = NodeToRRDtoolForwarder(conf_)
        message_publisher.setHandlerParent(xmpp_client)
        
        from urllib import quote
        try:
            vigiconf_settings.load_configuration(conf_)
        except (IOError, ConfigParseError):
            pass
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on test le fichier).
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['connector-metro']['rrd_base_dir'], 
                             "server1.example.com", "%s.rrd" % quote("Load"))
                )
        xml = text2xml(
                "perf|1165939739|server1.example." +
                "com|Load|12")
        message_publisher.messageForward(xml)
        # on vérifie que le fichier correspondant a bien été créé
        self.assertTrue(
            stat.S_ISREG(
                os.stat(
                    os.path.join(settings['connector-metro']['rrd_base_dir'],
                                 "server1.example.com", "%s.rrd" %
                                 quote("Load"))).st_mode
            ))
        # un peu de nettoyage
        # shutil.rmtree permet de faire l'equivalent d'un "rm -rf" du 
        #  répertoire/fichier visé
        from shutil import rmtree
        rmtree(settings['connector-metro']['rrd_base_dir'])
        os.unlink(conf_)

        
        
    def test_nodeToRRDtool2(self):
        """Le connecteur doit ignorer les hôtes non-déclarés."""
        conf = """# vim: set fileencoding=utf-8 sw=4 ts=4 et :
from urllib import quote
# the directory to store RRD file
RRD_BASE_DIR = '/tmp/rrd.test'
# the path to rrdtool binary
RRD_BIN = '/usr/bin/rrdtool'
# Init the hashmap (mandatory)
HOSTS = {}
# In this setup, we create one RRD per DS, each in a folder named after the host.
# All the RRDs have the same RRAs.
# Load for server1.example.com
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
    "DS": { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" },
}"""
        # on créer le fichier de conf

        file = open(settings['connector-metro']['config'], 'w')
        file.write(conf)
        file.close()
        conf_ = settings['connector-metro'].get('config', None)
        xmpp_client = client.XMPPClient(
            JID(settings['bus']['jid']),
            settings['bus']['password'],
            settings['bus']['host'])

        message_publisher = NodeToRRDtoolForwarder(conf_)
        message_publisher.setHandlerParent(xmpp_client)
        
        from urllib import quote
        vigiconf_settings.load_configuration(conf_)
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on test le fichier).
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['connector-metro']['rrd_base_dir'], 
                             "unknown.example.com", "%s.rrd" % quote("Load"))
                )
        xml = text2xml(
                "perf|1165939739|unknown.example." +
                "com|Load|12")
        message_publisher.messageForward(xml)
        # on vérifie que le fichier correspondant n'a pas été créé
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['connector-metro']['rrd_base_dir'], 
                             "unknown.example.com", "%s.rrd" % quote("Load"))
                )
        # un peu de nettoyage
        # shutil.rmtree permet de faire l'equivalent d'un "rm -rf" du 
        #  répertoire/fichier visé
        from shutil import rmtree
        rmtree(settings['connector-metro']['rrd_base_dir'])
        os.unlink(conf_)

if __name__ == "__main__": 
    unittest.main()
