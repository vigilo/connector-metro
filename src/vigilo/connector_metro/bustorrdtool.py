# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2021 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce module fournit un demi-connecteur capable de lire des messages
depuis un bus pour les stocker dans une base de données RRDtool.
"""

from __future__ import absolute_import

import time

from twisted.internet import defer

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from vigilo.connector.handlers import MessageHandler

from vigilo.connector_metro.rrdtool import RRDToolError
from vigilo.connector_metro.exceptions import InvalidMessage
from vigilo.connector_metro.exceptions import WrongMessageType
from vigilo.connector_metro.exceptions import CreationError
from vigilo.connector_metro.exceptions import NotInConfiguration



class BusToRRDtool(MessageHandler):
    """
    Reçoit des données de métrologie (performances) depuis le bus
    et les transmet à RRDtool pour générer des base de données RRD.
    """
    get_current_time = time.time


    def __init__(self, confdb, rrdtool, threshold_checker):
        """
        Instancie un connecteur du bus vers RRDtool pour le stockage des
        données de performance dans les fichiers RRD.

        @param confdb: instance de la base de configuration en provenance de
            VigiConf
        @type  confdb: C{vigilo.connector_metro.confdb.MetroConfDB}
        """
        super(BusToRRDtool, self).__init__()
        self.confdb = confdb
        self.rrdtool = rrdtool
        self.threshold_checker = threshold_checker
        self._illegal_updates = 0


    def connectionInitialized(self):
        """
        Cette méthode est appelée lorsque la connexion est initialisée,
        c'est-à-dire lorsque la connexion a réussi et que les échanges
        initiaux (handshakes) sont terminés.
        """
        # On réinitialise le compteur à chaque connexion établie avec succès.
        self._illegal_updates = 0


    def processMessage(self, msg):
        """
        Transmet un message reçu du bus à RRDtool.

        Attention, c'est complexe parce qu'on a pas le droit d'utiliser
        inlineDeferred (sinon le yield qui est fait sur le résultat de cette
        fonction ne servira à rien et on va manger de la RAM comme des gorets
        en consommant la file d'attente)

        @param msg: Message à transmettre
        @type msg: C{dict}
        """
        d = self._parse_message(msg)
        d.addCallback(self.rrdtool.createIfNeeded)
        d.addCallback(self._check_has_thresholds)
        d.addCallback(self.rrdtool.processMessage)
        d.addCallback(self._check_thresholds)
        d.addErrback(self._eb)
        return d


    def _parse_message(self, msg):
        if msg["type"] != 'perf':
            errormsg = _("'%(msgtype)s' is not a valid message type for "
                         "metrology")
            return defer.fail(WrongMessageType((
                    errormsg % {'msgtype' : msg["type"]}
                ).encode('utf-8')))

        for i in 'timestamp', 'value', 'host', 'datasource':
            if i not in msg:
                errormsg = _(u"Not a valid performance message (missing "
                              "'%(tag)s' tag)")
                return defer.fail(InvalidMessage((
                        errormsg % {"tag": i}
                    ).encode('utf-8')))

        if msg["value"] == "":
            msg["value"] = u"U"
        if msg["value"] != u"U":
            try:
                float(msg["value"])
            except ValueError:
                return defer.fail(InvalidMessage((
                        _("Invalid metrology value for datasource %(ds)s "
                          "on host %(host)s: %(value)s") % {
                            'value': msg["value"],
                            'ds': msg['datasource'],
                            'host': msg['host'],
                          }
                    ).encode('utf-8')))

        d = self.confdb.has_host(msg["host"])
        def cb(isinconf, msg):
            if not isinconf:
                return defer.fail(NotInConfiguration((
                        _("Skipping perf update for host %s") % msg["host"]
                    ).encode('utf-8')))
            return msg
        d.addCallback(cb, msg)
        return d


    def _check_has_thresholds(self, perf):
        """Ajoute au message l'information de la présence d'un seuil"""
        if perf is None:
            return None
        if self.threshold_checker is None:
            perf["has_thresholds"] = False
            return perf
        return self.threshold_checker.hasThreshold(perf)


    def _check_thresholds(self, perf, sync=False):
        if perf is None:
            return None
        if (self.threshold_checker is None or not perf["has_thresholds"]):
            return perf
        return self.threshold_checker.checkMessage(perf)


    def _eb(self, f):
        err_class = f.trap(InvalidMessage, WrongMessageType,
                           NotInConfiguration, CreationError, RRDToolError)
        error_msg = f.getErrorMessage()
        if err_class == InvalidMessage:
            LOGGER.error(error_msg)
        elif (err_class == NotInConfiguration or
              err_class == WrongMessageType):
            self._messages_received -= 1
            #LOGGER.debug(str(f.value))
        elif err_class == RRDToolError:
            # Le message de rrdtool ne dépend pas de la locale,
            # donc on peut faire ce test sans crainte.
            if error_msg.endswith('(minimum one second step)'):
                self._illegal_updates += 1
            else:
                LOGGER.error(_("RRDtool could not update the file "
                        "%(filename)s. Message: %(msg)s"), {
                             'filename': f.value.filename,
                             'msg': error_msg })
        # on ne renvoie pas le message en file (erreurs permanentes)
        return None


    @defer.inlineCallbacks
    def getStats(self):
        """Récupère des métriques de fonctionnement du connecteur"""
        stats = yield super(BusToRRDtool, self).getStats()
        ds_count = yield self.confdb.count_datasources()
        stats["pds_count"] = ds_count
        stats["illegal_updates"] = self._illegal_updates
        defer.returnValue(stats)


    def startService(self):
        return self.rrdtool.start()

    def stopService(self):
        return self.rrdtool.stop()
