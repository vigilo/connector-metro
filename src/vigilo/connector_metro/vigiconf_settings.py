# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

""" Chargement du fichier de configuration généré par Vigiconf. """

from __future__ import absolute_import

import os

from twisted.internet import defer, task
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
        self._cache = {"hosts": None, "has_threshold": None, "ds": {}}
        self.start()

    def start(self):
        if not self._reload_task.running:
            self._reload_task.start(10) # toutes les 10s

    def stop(self):
        if self._reload_task.running:
            self._reload_task.stop()
        if self._db is not None:
            self._db.close()

    def start_db(self):
        if not os.path.exists(self.path):
            LOGGER.warning(_("No configuration database yet!"))
            raise NoConfDBError()
        self._timestamp = os.stat(self.path).st_mtime
        # threads: http://twistedmatrix.com/trac/ticket/3629
        self._db = adbapi.ConnectionPool("sqlite3", self.path,
                                         check_same_thread=False)
        LOGGER.debug("Connected to the configuration database")
        self._rebuild_cache()

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
        self._rebuild_cache()

    def _rebuild_cache(self):
        self._cache["hosts"] = None
        self._cache["has_threshold"] = None
        self._cache["ds"] = {}
        self.get_hosts()
        self.list_thresholds()

    def get_hosts(self):
        if self._db is None:
            return defer.succeed([])
        result = self._db.runQuery("SELECT DISTINCT hostname FROM "
                                   "perfdatasource")
        result.addCallback(lambda results: [str(r[0]) for r in results])
        def cache_hosts(hosts):
            self._cache["hosts"] = hosts
            return hosts
        result.addCallback(cache_hosts)
        return result

    def list_thresholds(self):
        if self._db is None:
            return defer.succeed(None)
        result = self._db.runQuery("SELECT hostname, name FROM perfdatasource "
                                   "WHERE warning_threshold IS NOT NULL "
                                   "AND critical_threshold IS NOT NULL")
        result.addCallback(lambda results: [(r[0], r[1]) for r in results])
        def cache_thresholds(thresholds):
            self._cache["has_threshold"] = thresholds
            return thresholds
        result.addCallback(cache_thresholds)
        return result

    def has_host(self, hostname):
        if self._db is None:
            return defer.succeed(False)
        if self._cache["hosts"] is not None:
            return defer.succeed(hostname in self._cache["hosts"])
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

    def has_threshold(self, hostname, dsname):
        if self._db is None:
            return defer.succeed(False)
        if self._cache["has_threshold"] is not None:
            return defer.succeed((hostname, dsname)
                                 in self._cache["has_threshold"])
        result = self._db.runQuery("SELECT 1 FROM perfdatasource "
                                   "WHERE hostname = ? AND name = ? "
                                   "AND (warning_threshold IS NOT NULL "
                                   "     AND critical_threshold IS NOT NULL) "
                                   "LIMIT 1",
                                   (hostname, dsname))
        result.addCallback(lambda results: bool(len(results)))
        return result

    def get_datasource(self, hostname, dsname, cache=False):
        properties = ["id", "type", "step", "heartbeat",
                      "min", "max",
                      "factor",
                      "warning_threshold", "critical_threshold",
                      "nagiosname", "jid"]
        if self._db is None:
            return defer.succeed(dict([(p, None) for p in properties]))
        if cache and (hostname, dsname) in self._cache["ds"]:
            return defer.succeed(self._cache["ds"][(hostname, dsname)])
        result = self._db.runQuery(
                "SELECT idperfdatasource, %s FROM perfdatasource WHERE "
                "name = ? AND hostname = ?" % ", ".join(properties[1:]),
                (dsname, hostname) )
        def format_result(result, properties):
            if not result:
                raise KeyError("No such datasource %s on host %s"
                               % (dsname, hostname))
            d = {}
            for propindex, propname in enumerate(properties):
                d[propname] = str(result[0][propindex])
                if (propname == "min" or propname == "max") \
                        and d[propname] == 'None': # hum hum...
                    d[propname] = "U"
            d["name"] = dsname
            d["hostname"] = hostname
            if cache:
                self._cache["ds"][(d["hostname"], d["name"])] = d
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

    def count_datasources(self):
        if self._db is None:
            return defer.succeed(0)
        result = self._db.runQuery("SELECT COUNT(*) FROM perfdatasource")
        result.addCallback(lambda r: r[0][0])
        return result
