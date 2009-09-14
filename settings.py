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
VIGILO_CONNECTOR_PIDFILE = '/var/lib/vigilo/connector/connector.pid'
VIGILO_CONNECTOR_XMPP_SERVER_HOST = 'tburguie3'
VIGILO_CONNECTOR_XMPP_PUBSUB_SERVICE = 'pubsub.tburguie3'
# Respect the ejabberd namespacing, for now. It will be too restrictive soon.
VIGILO_CONNECTOR_JID = 'connectorx@tburguie3'
VIGILO_CONNECTOR_PASS = 'connectorx'

VIGILO_CONNECTOR_TOPIC = '/home/tburguie3/connectorx/BUS'
VIGILO_SOCKETW = '/var/lib/vigilo/connector/recv.sock'
VIGILO_SOCKETR = '/var/lib/vigilo/connector/send.sock'
VIGILO_MESSAGE_BACKUP_FILE = '/var/lib/vigilo/connector/backup'
VIGILO_MESSAGE_BACKUP_TABLE_TOBUS = 'connector_tobus'
VIGILO_MESSAGE_BACKUP_TABLE_FROMBUS = 'connector_frombus'
VIGILO_STOREME_CONF = '/etc/storeme.conf.py'
VIGILO_STOREME_RRDTOOL_BIN = '/usr/bin/rrdtool'

from urllib import quote

# the directory to store RRD file
RRD_BASE_DIR = '/var/lib/rrds'

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
}

# HTTP traffic for localhost
HOSTS["localhost/SFRUUA=="] = { 
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, # on garde deux jours de donnée complète (5 minutes de précision)
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, # on garde deux semaines précision 30 minutes
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, # on garde deux mois précision 2 h
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797} # on garde deux ans précision 1 jour
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# Load 01 for localhost
HOSTS["localhost/TG9hZCAwMQ=="] = {
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# Load 05 for localhost
HOSTS["localhost/TG9hZCAwNQ=="] = {
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# Load 15 for localhost
HOSTS["localhost/TG9hZCAxNQ=="] = {
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# Users for localhost
HOSTS["localhost/VXNlcnM="] = {
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# CPU 1min for host2
HOSTS["host2/Q1BVIDFtaW4="] = { 
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 },
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 },
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 },
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797}
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# CPU 5min for host2
HOSTS["host2/Q1BVIDVtaW4="] = { 
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797}
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ], 
}

# TCP connections for host2
HOSTS["host2/VENQIGNvbm5lY3Rpb25z"] = { 
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "GAUGE", "heartbeat": 600, "min": "U", "max": "U" } ], 
}

# inFE0/1 for host2
HOSTS["host2/aW5GRTAvMQ=="] = { 
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "COUNTER", "heartbeat": 600, "min": "U", "max": "U" } ],
}

# outFE0/1 for host2
HOSTS["host2/b3V0RkUwLzE="] = {
    "step": 300, 
    "RRA": [ 
        { "type": "AVERAGE", "xff": 0.5, "step": 1, "rows": 600 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 6, "rows": 700 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 24, "rows": 775 }, 
        { "type": "AVERAGE", "xff": 0.5, "step": 288, "rows": 797},
    ],
    "DS": [ { "name": "DS", "type": "COUNTER", "heartbeat": 600, "min": "U", "max": "U" } ],
}

