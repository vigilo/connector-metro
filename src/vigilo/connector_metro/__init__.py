# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2015 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""Metrology to RRDTool connector."""

from __future__ import absolute_import

import sys

from twisted.application import service


def makeService(options):
    """ the service that wraps everything the connector needs. """
    from vigilo.connector.options import getSettings, parseSubscriptions
    settings = getSettings(options, __name__)

    from vigilo.common.logging import get_logger
    LOGGER = get_logger(__name__)

    from vigilo.common.gettext import translate
    _ = translate(__name__)

    from vigilo.connector.client import client_factory
    from vigilo.connector.handlers import buspublisher_factory

    from vigilo.connector_metro.rrdtool import RRDToolPoolManager
    from vigilo.connector_metro.rrdtool import RRDToolManager
    from vigilo.connector_metro.confdb import MetroConfDB
    from vigilo.connector_metro.threshold import ThresholdChecker
    from vigilo.connector_metro.bustorrdtool import BusToRRDtool

    root_service = service.MultiService()

    # Client du bus
    client = client_factory(settings)
    client.setServiceParent(root_service)
    providers = []

    # Configuration
    try:
        conffile = settings['connector-metro']['config']
    except KeyError:
        LOGGER.error(_("Please set the path to the configuration "
            "database generated by VigiConf in the settings.ini."))
        sys.exit(1)
    confdb = MetroConfDB(conffile)
    confdb.setServiceParent(root_service)

    try:
        must_check_th = settings['connector-metro'].as_bool('check_thresholds')
    except KeyError:
        must_check_th = True

    # Gestion RRDTool
    rrd_base_dir = settings['connector-metro']['rrd_base_dir']
    rrd_path_mode = settings['connector-metro']['rrd_path_mode']
    rrd_bin = settings['connector-metro'].get('rrd_bin', '/usr/bin/rrdtool')
    rrdcached = settings["connector-metro"].get("rrdcached", None)
    try:
        pool_size = settings["connector-metro"].as_int("rrd_processes")
    except KeyError:
        pool_size = None
    rrdtool_pool = RRDToolPoolManager(rrd_base_dir, rrd_path_mode, rrd_bin,
                             check_thresholds=must_check_th,
                             rrdcached=rrdcached, pool_size=pool_size)
    rrdtool = RRDToolManager(rrdtool_pool, confdb)

    # Gestion des seuils
    if must_check_th:
        threshold_checker = ThresholdChecker(rrdtool, confdb)
        bus_publisher = buspublisher_factory(settings, client)
        bus_publisher.registerProducer(threshold_checker, streaming=True)
        providers.append(bus_publisher)
    else:
        threshold_checker = None

    # Gestionnaire principal des messages
    bustorrdtool = BusToRRDtool(confdb, rrdtool, threshold_checker)
    bustorrdtool.setClient(client)
    subs = parseSubscriptions(settings)
    queue = settings["bus"]["queue"]
    queue_messages_ttl = int(settings['bus'].get('queue_messages_ttl', 0))
    bustorrdtool.subscribe(queue, queue_messages_ttl, subs)
    providers.append(bustorrdtool)

    # Statistiques
    from vigilo.connector.status import statuspublisher_factory

    status_publisher = statuspublisher_factory(settings, client,
                                               providers=providers)

    return root_service
