# vim: set fileencoding=utf-8 sw=4 ts=4 et :
import logging
LOGGING_PLUGINS = (
#        'vigilo.pubsub.logging',
        )
LOGGING_SYSLOG = True
LOG_TRAFFIC = True


LOGGING_SETTINGS = {
        # 5 is the 'SUBDEBUG' level.
        'level': logging.INFO,
        'format': '%(levelname)s::%(name)s::%(message)s',
        }
LOGGING_LEVELS = {
        'twisted': logging.INFO,
        'vigilo.pubsub': logging.INFO,
        'vigilo.connector': logging.INFO,
        'vigilo.connector_metro': logging.INFO
    }


VIGILO_CONNECTOR_XMPP_SERVER_HOST = 'vigilo-dev'
VIGILO_CONNECTOR_XMPP_PUBSUB_SERVICE = 'pubsub.localhost'
# Respect the ejabberd namespacing, for now. It will be too restrictive soon.
VIGILO_CONNECTOR_JID = 'connector-metro@localhost'
VIGILO_CONNECTOR_PASS = 'connector-metro'

VIGILO_CONNECTOR_TOPIC = [
        '/home/localhost/connectorx/BUS',
        ]
VIGILO_CONNECTOR_TOPIC_OWNER = []
VIGILO_METRO_CONF = '/etc/connector-metro.conf.py'
