# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""Metrology to RRDTool connector."""

from __future__ import absolute_import

import sys
import os

from twisted.application import service


def makeService(self, options):
    """ the service that wraps everything the connector needs. """
    from vigilo.connector import getSettings
    settings = getSettings(options)

    from vigilo.common.logging import get_logger
    LOGGER = get_logger(__name__)

    from vigilo.common.gettext import translate
    _ = translate(__name__)

    from vigilo.connector.client import client_factory

    from vigilo.connector_metro.bustorrdtool import bustorrdtool_factory
    from vigilo.connector.forwarder import buspublisher_factory
    from vigilo.connector.status import statuspublisher_factory

    root_service = service.MultiService()

    client = client_factory(settings)
    client.setServiceParent(root_service)

    bustorrdtool = bustorrdtool_factory(settings, client)

    # Statistiques
    servicename = options["name"]
    if servicename is None:
        servicename = "vigilo-connector-metro"
    status_publisher = statuspublisher_factory(settings, servicename, client,
            providers=(bustorrdtool,))
    stats_publisher = StatusPublisher(message_consumer,
                    settings["connector"].get("hostname", None),
                    servicename=servicename,
                    node=settings["connector"].get("status_node", None))
    stats_publisher.setHandlerParent(xmpp_client)
    presence_manager.registerStatusPublisher(stats_publisher)

    return root_service
