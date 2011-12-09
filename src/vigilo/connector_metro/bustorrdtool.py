# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce module fournit un demi-connecteur capable de lire des messages
depuis un bus pour les stocker dans une base de données RRDtool.
"""

from __future__ import absolute_import

import os
import stat
import time
import signal
import urllib

from twisted.internet import defer

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

from vigilo.connector.client import MessageHandler

from vigilo.connector_metro.rrdtool import RRDToolError



class NotInConfiguration(KeyError):
    pass


class InvalidMessage(ValueError):
    pass


class WrongMessageType(Exception):
    pass


class CreationError(Exception):
    pass



class BusToRRDtool(MessageHandler):
    """
    Reçoit des données de métrologie (performances) depuis le bus XMPP
    et les transmet à RRDtool pour générer des base de données RRD.
    """
    get_current_time = time.time


    def __init__(self, confdb, rrdtool, threshold_checker):
        """
        Instancie un connecteur BUS XMPP vers RRDtool pour le stockage des
        données de performance dans les fichiers RRD.

        @param confdb_path: le chemin du fichier SQLite contenant la
            configuration en provenance de VigiConf
        @type  confdb_path: C{str}
        """
        super(BusToRRDtool, self).__init__()
        self.confdb = confdb
        self.rrdtool = rrdtool
        self.threshold_checker = threshold_checker
        # Sauvegarde du handler courant pour SIGHUP
        # et ajout de notre propre handler pour recharger
        # le connecteur (lors d'un service ... reload).
        self._prev_sighup_handler = signal.getsignal(signal.SIGHUP)
        signal.signal(signal.SIGHUP, self._sighup_handler)
        self._illegal_updates = 0


    def connectionInitialized(self):
        """
        Cette méthode est appelée lorsque la connexion est initialisée,
        c'est-à-dire lorsque la connexion a réussi et que les échanges
        initiaux (handshakes) sont terminés.
        """
        self.rrdtool.start()
        # On réinitialise le compteur à chaque connexion établie avec succès.
        self._illegal_updates = 0


    def isConnected(self):
        """Sauf cas exceptionnel, on est toujours connecté"""
        return self.rrdtool.started


    def processMessage(self, msg):
        """
        Transmet un message reçu du bus à RRDtool.

        Attention, c'est complexe parce qu'on a pas le droit d'utiliser
        inlineDeferred (sinon le yield qui est fait sur le résultat de cette
        fonction ne servira à rien et on va manger de la RAM comme des gorets
        en consommant la file d'attente)

        @param msg: Message à transmettre
        @type msg: C{twisted.words.test.domish Xml}
        """
        d = self._parse_message(msg)
        d.addCallbacks(self._create_if_needed, self._eb)
        d.addCallback(self._check_has_thresholds)
        d.addCallbacks(self._run_rrdtool, self._eb)
        d.addErrback(self._eb_rrdtool)
        d.addCallback(self._check_thresholds)
        return d


    def _parse_message(self, msg):
        if msg.name != 'perf':
            errormsg = _("'%(msgtype)s' is not a valid message type for "
                         "metrology")
            return defer.fail(WrongMessageType((
                    errormsg % {'msgtype' : msg.name}
                ).encode('utf-8')))
        perf = {}
        for c in msg.children:
            perf[str(c.name)] = unicode(c.children[0])

        for i in 'timestamp', 'value', 'host', 'datasource':
            if i not in perf:
                errormsg = _(u"Not a valid performance message (missing "
                              "'%(tag)s' tag)")
                return defer.fail(InvalidMessage((
                        errormsg % {"tag": i}
                    ).encode('utf-8')))

        if perf["value"] != u"U":
            try:
                float(perf["value"])
            except ValueError:
                return defer.fail(InvalidMessage((
                        _("Invalid metrology value: %s") % perf["value"]
                    ).encode('utf-8')))

        d = self.confdb.has_host(perf["host"])
        def cb(isinconf, perf):
            if not isinconf:
                return defer.fail(NotInConfiguration((
                        _("Skipping perf update for host %s") % perf["host"]
                    ).encode('utf-8')))
            return perf
        d.addCallback(cb, perf)
        return d


    def _create_if_needed(self, perf):
        """
        La création du deferred et le addCallbacks sont là pour propager
        le message de perf plutôt que le résultat de la fonction
        create_if_needed
        """
        d = defer.Deferred()
        create_d = self.create_if_needed(perf)
        create_d.addCallbacks(lambda x: d.callback(perf), d.errback)
        return d


    def _eb(self, f):
        err_class = f.trap(InvalidMessage, WrongMessageType,
                           NotInConfiguration, CreationError)
        if err_class == InvalidMessage:
            LOGGER.error(str(f.value))
        elif (err_class == NotInConfiguration or
              err_class == WrongMessageType):
            self._messages_forwarded -= 1
            #LOGGER.debug(str(f.value))
        return None


    def _check_has_thresholds(self, perf):
        """Ajoute au message l'information de la présence d'un seuil"""
        if perf is None:
            return None
        if self.threshold_checker is None:
            perf["has_thresholds"] = False
            return perf
        return self.threshold_checker.hasThreshold(perf)


    def _run_rrdtool(self, perf):
        if perf is None:
            return None
        cmd = '%(timestamp)s:%(value)s' % perf
        filename = self.rrdtool.getFilename(perf)
        d2 = self.rrdtool.run("update", filename, cmd,
                              no_rrdcached=perf["has_thresholds"])
        d2.addCallback(lambda x: perf)
        return d2


    def _eb_rrdtool(self, f):
        f.trap(RRDToolError)
        error_msg = f.getErrorMessage()

        # Le message de rrdtool ne dépend pas de la locale,
        # donc on peut faire ce test sans crainte.
        if error_msg.endswith('(minimum one second step)'):
            self._illegal_updates += 1
            return

        LOGGER.error(_("RRDtool could not update the file %(filename)s. "
                       "Message: %(msg)s"), {
                     'filename': f.value.filename,
                     'msg': error_msg })


    def _check_thresholds(self, perf, sync=False):
        if perf is None:
            return None
        if (self.threshold_checker is None or
                not perf["has_thresholds"]):
            return perf
        return self.threshold_checker.checkMessage(perf)


    def _sighup_handler(self, signum, frames):
        """
        Gestionnaire du signal SIGHUP: recharge la conf.

        @param signum: Signal qui a déclenché le rechargement (= SIGHUP).
        @type signum: C{int} ou C{None}
        @param frames: Frames d'exécution interrompues par le signal.
        @type frames: C{list}
        """
        LOGGER.info(_("Received signal to reload the configuration"))
        self.confdb.reload()
        # On appelle le précédent handler s'il y en a un.
        # Eventuellement, il s'agira de signal.SIG_DFL ou signal.SIG_IGN.
        if callable(self._prev_sighup_handler):
            self._prev_sighup_handler(signum, frames)


    @defer.inlineCallbacks
    def getStats(self):
        """Récupère des métriques de fonctionnement du connecteur"""
        stats = yield super(BusToRRDtool, self).getStats()
        ds_count = yield self.confdb.count_datasources()
        stats["pds_count"] = ds_count
        stats["illegal_updates"] = self._illegal_updates
        defer.returnValue(stats)


    def stopService(self):
        self.confdb.stop()
        self.rrdtool.stop()
