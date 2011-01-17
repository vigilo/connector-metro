# vim: set fileencoding=utf-8 sw=4 ts=4 et :
""" Chargement du fichier de configuration généré par Vigiconf. """

from __future__ import absolute_import

import os

from twisted.internet import defer, threads, task
from twisted.enterprise import adbapi

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)
from vigilo.common.gettext import translate
_ = translate(__name__)


class NoConfDBError(Exception):
    pass

class ConfDB(object):
    """
    Accès à la configuration fournie par VigiConf (dans une base SQLite)
    @ivar _db: Instance de connexion ADBAPI, voir
        U{http://twistedmatrix.com/documents/10.1.0/core/howto/rdbms.html}.
    @type _db: C{twisted.enterprise.adbapi.ConnectionPool}
    """

    def __init__(self, path):
        self.path = path
        self._db = None
        self._timestamp = 0
        self._reload_task = task.LoopingCall(self.reload)
        self.start()

    def start(self):
        if not self._reload_task.running:
            self._reload_task.start(10) # toutes les 10s

    def stop(self):
        self._reload_task.stop()
        self._db.close()

    def start_db(self):
        if not os.path.exists(self.path):
            LOGGER.warning(_("No configuration database yet !"))
            raise NoConfDBError()
        self._timestamp = os.stat(self.path).st_mtime
        # threads: http://twistedmatrix.com/trac/ticket/3629
        self._db = adbapi.ConnectionPool("sqlite3", self.path,
                                         check_same_thread=False)
        LOGGER.debug("Connected to the configuration database")

    def reload(self):
        """
        Provoque une reconnexion à la base si elle a changé
        """
        if self._db is None:
            try:
                self.start_db()
            except NoConfDBError:
                return
        current_timestamp = os.stat(self.path).st_mtime
        if current_timestamp <= self._timestamp:
            return # ça n'a pas changé
        LOGGER.debug("Reconnecting to the configuration database")
        self._db.close()
        self._db.start()
        self._timestamp = current_timestamp

    def get_hosts(self):
        if self._db is None:
            return defer.succeed([])
        result = self._db.runQuery("SELECT DISTINCT hostname FROM "
                                   "perfdatasource")
        result.addCallback(lambda results: [str(r[0]) for r in results])
        return result

    def has_host(self, hostname):
        if self._db is None:
            return defer.succeed(False)
        result = self._db.runQuery("SELECT COUNT(*) FROM perfdatasource "
                                   "WHERE hostname = ?", (hostname,) )
        result.addCallback(lambda results: bool(results[0][0]))
        return result

    def get_host_datasources(self, hostname):
        if self._db is None:
            return defer.succeed([])
        result = self._db.runQuery("SELECT name FROM perfdatasource WHERE "
                                   "hostname = ?", (hostname,))
        result.addCallback(lambda results: [str(r[0]) for r in results])
        return result

    def get_datasource(self, hostname, dsname):
        properties = ["id", "type", "step", "heartbeat",
                      "min", "max"]
        if self._db is None:
            return defer.succeed(dict([(p, None) for p in properties]))
        result = self._db.runQuery(
                "SELECT idperfdatasource, %s FROM perfdatasource WHERE "
                "name = ? AND hostname = ?" % ", ".join(properties[1:]),
                (dsname, hostname) )
        def format_result(result, properties):
            d = {}
            for propindex, propname in enumerate(properties):
                d[propname] = str(result[0][propindex])
                if (propname == "min" or propname == "max") \
                        and d[propname] == 'None': # hum hum...
                    d[propname] = "U"
            return d
        result.addCallback(format_result, properties)
        return result

    def get_rras(self, dsid):
        if self._db is None:
            return defer.succeed([])
        properties = ["type", "xff", "step", "rows"]
        result = self._db.runQuery("SELECT %s FROM rra "
                    "LEFT JOIN pdsrra ON pdsrra.idrra = rra.idrra "
                    "WHERE pdsrra.idperfdatasource = ?"
                    % ", ".join(properties), (dsid,) )
        def format_result(rows, properties):
            rras = []
            for row in rows:
                rra = {}
                for propindex, propname in enumerate(properties):
                    rra[propname] = str(row[propindex])
                rras.append(rra)
            return rras
        result.addCallback(format_result, properties)
        return result

