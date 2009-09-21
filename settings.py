# vim: set fileencoding=utf-8 sw=4 ts=4 et :
import logging
LOGGING_PLUGINS = (
#        'vigilo.pubsub.logging',       
        )
LOGGING_SETTINGS = { 'level': logging.DEBUG, }
LOGGING_LEVELS = {}
LOGGING_SYSLOG = True
LOG_TRAFFIC = True


LOGGING_SETTINGS = {
        # 5 is the 'SUBDEBUG' level.
        'level': logging.DEBUG,
        'format': '%(levelname)s::%(name)s::%(message)s',
        }
LOGGING_LEVELS = {
        'multiprocessing': logging.DEBUG,
        'twisted': logging.DEBUG,
        'vigilo.pubsub': logging.DEBUG,
        'vigilo.connector': logging.DEBUG,
    }


VIGILO_CONNECTOR_DAEMONIZE = True
VIGILO_CONNECTOR_DAEMONIZE = False
VIGILO_CONNECTOR_PIDFILE = '/var/lib/vigilo/connector-metro/connector-metro.pid'
VIGILO_CONNECTOR_XMPP_SERVER_HOST = 'tburguie3'
VIGILO_CONNECTOR_XMPP_PUBSUB_SERVICE = 'pubsub.tburguie3'
# Respect the ejabberd namespacing, for now. It will be too restrictive soon.
VIGILO_CONNECTOR_JID = 'connector-metro@tburguie3'
VIGILO_CONNECTOR_PASS = 'connector-metro'

VIGILO_CONNECTOR_METRO_TOPIC = ['/home/tburguie3/connectorx/BUS',]
#VIGILO_CONNECTOR_METRO_TOPIC = []
VIGILO_CONNECTOR_METRO_TOPIC_OWNER = ['/home/tburguie3/connector-metro/BUS']
#VIGILO_CONNECTOR_METRO_TOPIC_OWNER = []
VIGILO_METRO_CONF = '/etc/connector-metro.conf.py'
