# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""Tests de la conversion des messages en données RRD"""

import os
import tempfile

from twisted.trial import unittest
from twisted.internet import reactor
from twisted.words.xish import domish

from vigilo.common.conf import settings
settings.load_module(__name__)
from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.connector.converttoxml import perf2xml
from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder, \
                                                 NodeToRRDtoolForwarderError

class TestNodeToRRDtoolForwarder(unittest.TestCase):
    """Teste les échangeurs (forwarders) de messages."""
    timeout = 10

    def setUp(self):
        """Initialisation du test."""

        #self.stub = XmlStreamStub()
        #self.protocol.xmlstream = self.stub.xmlstream
        #self.protocol.connectionInitialized()
        conf_h, self.confpath = tempfile.mkstemp()
        os.write(conf_h, "HOSTS = {}\n")
        os.close(conf_h)
        self.ntrf = NodeToRRDtoolForwarder(self.confpath)

    def tearDown(self):
        """Destruction des objets de test."""
        os.remove(self.confpath)

    def test_unhandled_host(self):
        self.assertEquals(self.ntrf.filter_host("dummy"), False)

    def test_handled_host(self):
        conf = open(self.confpath, "w")
        conf.write("HOSTS = {'dummy': {}} \n")
        conf.close()
        self.assertEquals(self.ntrf.filter_host("dummy"), True)

    def test_nonExistingHost(self):
        """Reception d'un message pour un hôte absent du fichier de conf"""
        msg = {"timestamp": "123456789",
               "host": "dummy_host",
               "datasource": "dummy_datasource",
               "value": "dummy_value",}
        self.assertRaises(NodeToRRDtoolForwarderError, self.ntrf.createRRD,
                          "/tmp/nonexistant", msg)

    def test_catch_all(self):
        self.ntrf.catch_all = True
        self.assertEquals(self.ntrf.filter_host("dummy"), True)

