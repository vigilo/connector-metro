# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""Metrology to RRDTool connector."""
import sys, os

from zope.interface import implements
from twisted.plugin import IPlugin
from twisted.application import service


from vigilo.common.gettext import translate
from vigilo.connector import client
from vigilo.connector import options as base_options

_ = translate('vigilo.connector_metro')

class MetroConnectorServiceMaker(object):
    """
    Creates a service that wraps everything the connector needs.
    """
    implements(service.IServiceMaker, IPlugin)
    tapname = "vigilo-metro"
    description = "Vigilo connector for performance data"
    options = base_options.make_options('vigilo.connector_metro')

    def makeService(self, options):
        """ the service that wraps everything the connector needs. """
        from vigilo.connector_metro import makeService
        return makeService(options)

metro_connector = MetroConnectorServiceMaker()
