# -*- coding: utf-8 -*-
'''
Created on 14 oct. 2009

@author: tburguie
'''
# Teste la creation d'un fichier RRD 
from __future__ import absolute_import
import unittest
from vigilo.common.conf import settings
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
        """
        Vérification que le message qui correpond à un hôte déclaré 
        créer bien un fichier RRD correspondant.
        """

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
# Load for serveur1.example.com
HOSTS[quote("serveur1.example.com/Load")] = {
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
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}"""
        # on créer le fichier de conf

        file = open(settings['VIGILO_METRO_CONF'], 'w')
        file.write(conf)
        file.close()
        conf_ = settings.get('VIGILO_METRO_CONF', None)
        xmpp_client = client.XMPPClient(
            JID(settings['VIGILO_CONNECTOR_JID']),
            settings['VIGILO_CONNECTOR_PASS'],
            settings['VIGILO_CONNECTOR_XMPP_SERVER_HOST'])

        message_publisher = NodeToRRDtoolForwarder(conf_)
        message_publisher.setHandlerParent(xmpp_client)
        
        from urllib import quote
        settings.load_file(conf_)
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on test le fichier).
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['RRD_BASE_DIR'], 
                             quote("serveur1.example.com/Load"))
                )
        xml = text2xml(
                "perf|1165939739|serveur1.example." +
                "com|Load|12")
        message_publisher.messageForward(xml)
        # on vérifie que le fichier correspondant a bien été créé
        self.assertTrue(
            stat.S_ISREG(
                os.stat(
                    os.path.join(settings['RRD_BASE_DIR'],
                                 quote("serveur1.example.com/Load"))).st_mode
            ))
        # un peu de nettoyage
        # shutil.rmtree permet de faire l'equivalent d'un "rm -rf" du 
        #  répertoire/fichier visé
        from shutil import rmtree
        rmtree(settings['RRD_BASE_DIR'])
        os.unlink(conf_)

        
        
    def test_nodeToRRDtool2(self):
        """ 
        Vérification que le message qui ne correpond pas à un hôte déclaré
        ne créer pas le fichier correspondant au message (si l'hôte 
        n'existe pas dans le fichier de configuration impossible de créer
        le fichier RRD correspondant).
        """
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
# Load for serveur1.example.com
HOSTS[quote("serveur1.example.com/Load")] = {
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
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}"""
        # on créer le fichier de conf

        file = open(settings['VIGILO_METRO_CONF'], 'w')
        file.write(conf)
        file.close()
        conf_ = settings.get('VIGILO_METRO_CONF', None)
        xmpp_client = client.XMPPClient(
            JID(settings['VIGILO_CONNECTOR_JID']),
            settings['VIGILO_CONNECTOR_PASS'],
            settings['VIGILO_CONNECTOR_XMPP_SERVER_HOST'])

        message_publisher = NodeToRRDtoolForwarder(conf_)
        message_publisher.setHandlerParent(xmpp_client)
        
        from urllib import quote
        settings.load_file(conf_)
        # on vérifie que le fichier n'existe pas encore
        # (ce qui lève une exception quand on test le fichier).
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['RRD_BASE_DIR'], 
                             quote("unknown.example.com/Load"))
                )
        xml = text2xml(
                "perf|1165939739|unknown.example." +
                "com|Load|12")
        message_publisher.messageForward(xml)
        # on vérifie que le fichier correspondant n'a pas été créé
        self.assertRaises(OSError, 
                os.stat, 
                os.path.join(settings['RRD_BASE_DIR'], 
                             quote("unknown.example.com/Load"))
                )
        # un peu de nettoyage
        # shutil.rmtree permet de faire l'equivalent d'un "rm -rf" du 
        #  répertoire/fichier visé
        from shutil import rmtree
        rmtree(settings['RRD_BASE_DIR'])
        os.unlink(conf_)



    
if __name__ == "__main__": 
    unittest.main()
