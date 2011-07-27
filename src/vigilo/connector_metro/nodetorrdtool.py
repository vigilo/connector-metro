# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce module fournit un demi-connecteur capable de lire des messages
depuis un bus XMPP pour les stocker dans une base de données RRDtool.
"""
import os
import stat
import time
import signal
import urllib

from lxml import etree
from twisted.internet import defer
from wokkel.generic import parseXml

from vigilo.common.conf import settings
from vigilo.pubsub.xml import NS_COMMAND

from vigilo.common.logging import get_logger
from vigilo.common.gettext import translate
from vigilo.common import get_rrd_path

from vigilo.connector.forwarder import PubSubListener, PubSubSender
from vigilo.connector import MESSAGEONETOONE
from vigilo.connector_metro.rrdtool import RRDToolManager, RRDToolError
from vigilo.connector_metro.vigiconf_settings import ConfDB
from vigilo.connector_metro.threshold import is_out_of_bounds

LOGGER = get_logger(__name__)
_ = translate(__name__)


class NotInConfiguration(KeyError):
    pass

class InvalidMessage(ValueError):
    pass

class WrongMessageType(Exception):
    pass

class CreationError(Exception):
    pass

class NodeToRRDtoolForwarder(PubSubListener, PubSubSender):
    """
    Reçoit des données de métrologie (performances) depuis le bus XMPP
    et les transmet à RRDtool pour générer des base de données RRD.
    """
    get_current_time = time.time

    def __init__(self, confdb_path):
        """
        Instancie un connecteur BUS XMPP vers RRDtool pour le stockage des
        données de performance dans les fichiers RRD.

        @param confdb_path: le chemin du fichier SQLite contenant la
            configuration en provenance de VigiConf
        @type  confdb_path: C{str}
        """

        super(NodeToRRDtoolForwarder, self).__init__() # pas de db de backup
        self.rrd_base_dir = settings['connector-metro']['rrd_base_dir']
        # Sauvegarde du handler courant pour SIGHUP
        # et ajout de notre propre handler pour recharger
        # le connecteur (lors d'un service ... reload).
        self._prev_sighup_handler = signal.getsignal(signal.SIGHUP)
        signal.signal(signal.SIGHUP, self._sighup_handler)
        # Configuration
        self.confdb = ConfDB(confdb_path)
        # Sous-processus
        self.rrdtool = RRDToolManager()
        self.max_send_simult = len(self.rrdtool.pool)

    def connectionInitialized(self):
        """
        Cette méthode est appelée lorsque la connexion est initialisée,
        c'est-à-dire lorsque la connexion a réussi et que les échanges
        initiaux (handshakes) sont terminés.
        """
        super(NodeToRRDtoolForwarder, self).connectionInitialized()
        self.rrdtool.start()

    @defer.inlineCallbacks
    def createRRD(self, filename, perf):
        """
        Crée un nouveau fichier RRD avec la configuration adéquate.

        @param filename: Nom du fichier RRD à générer, le nom de l'indicateur
            doit être encodé avec urllib.quote_plus (RFC 1738).
        @type  filename: C{str}
        @param perf: Dictionnaire décrivant la source de données, contenant les
            clés suivantes :
             - C{host}: Nom de l'hôte.
             - C{datasource}: Nom de l'indicateur.
             - C{timestamp}: Timestamp UNIX de la mise à jour.
        @type perf: C{dict}
        """
        # to avoid an error just after creating the rrd file :
        # (minimum one second step)
        # the creation and updating time needs to be different.
        timestamp = int(perf["timestamp"]) - 10
        basedir = os.path.dirname(filename)
        self._makedirs(basedir)
        host = perf["host"]
        ds_name = perf["datasource"]
        ds_list = yield self.confdb.get_host_datasources(host)
        if ds_name not in ds_list:
            LOGGER.error(_("Host '%(host)s' with datasource '%(ds)s' not found "
                            "in the configuration !"), {
                                'host': host,
                                'ds': ds_name,
                        })
            raise NotInConfiguration()

        ds = yield self.confdb.get_datasource(host, ds_name)
        rrd_cmd = ["--step", str(ds["step"]), "--start", str(timestamp)]
        rras = yield self.confdb.get_rras(ds["id"])
        for rra in rras:
            rrd_cmd.append("RRA:%s:%s:%s:%s" %
                           (rra["type"], rra["xff"],
                            rra["step"], rra["rows"]))

        rrd_cmd.append("DS:DS:%s:%s:%s:%s" %
                       (ds["type"], ds["heartbeat"], ds["min"], ds["max"]))

        try:
            yield self.rrdtool.run("create", filename, rrd_cmd)
        except Exception, e:
            LOGGER.error(_("RRDtool could not create the file: "
                           "%(filename)s. Message: %(msg)s"),
                         { 'filename': filename,
                           'msg': e })
            raise CreationError()
        else:
            os.chmod(filename, # chmod 644
                     stat.S_IRUSR | stat.S_IWUSR |
                     stat.S_IRGRP | stat.S_IROTH )

    def _parse_message(self, msg):
        if msg.name != 'perf':
            errormsg = _("'%(msgtype)s' is not a valid message type for "
                         "metrology")
            return defer.fail(WrongMessageType(errormsg
                                               % {'msgtype' : msg.name}))
        perf = {}
        for c in msg.children:
            perf[str(c.name)] = str(c.children[0])

        for i in 'timestamp', 'value', 'host', 'datasource':
            if i not in perf:
                errormsg = _(u"Not a valid performance message (missing "
                              "'%(tag)s' tag)")
                return defer.fail(InvalidMessage(errormsg % {"tag": i}))

        d = self.confdb.has_host(perf["host"])
        def cb(isinconf, perf):
            if not isinconf:
                return defer.fail(NotInConfiguration(
                        _("Skipping perf update for host %s") % perf["host"]))
            return perf
        d.addCallback(cb, perf)
        return d

    def _makedirs(self, directory):
        # Création du dossier si besoin
        if os.path.exists(directory):
            return
        if not directory.startswith(self.rrd_base_dir):
            raise ValueError("Directory %s is not in the RRD directory"
                             % directory)
        tocreate = directory[len(self.rrd_base_dir)+1:]
        cur_dir = self.rrd_base_dir
        for subdir in tocreate.split(os.sep):
            cur_dir = os.path.join(cur_dir, subdir)
            if os.path.exists(cur_dir):
                continue
            try:
                os.mkdir(cur_dir)
                # l'option 'mode' de mkdir respecte l'umask, dommage
                os.chmod(cur_dir, # chmod 755
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                LOGGER.error(_("Unable to create the directory '%s'"), cur_dir)
                raise e

    def _get_msg_filename(self, msgdata):
        rrd_dir = settings['connector-metro']['rrd_base_dir']
        rrd_path_mode = settings['connector-metro']['rrd_path_mode']
        filename = get_rrd_path(msgdata["host"], msgdata["datasource"],
                                rrd_dir, rrd_path_mode)
        return filename

    def create_if_needed(self, msgdata):
        """Création du RRD si besoin"""
        filename = self._get_msg_filename(msgdata)
        if os.path.exists(filename):
            return defer.succeed(msgdata)
        # compatibilité
        old_filename = os.path.join(self.rrd_base_dir, msgdata["host"], "%s.rrd"
                                    % urllib.quote_plus(msgdata["datasource"]))
        if os.path.isfile(old_filename):
            os.rename(old_filename, filename)
            return defer.succeed(msgdata)
        else:
            # création
            return self.createRRD(filename, msgdata)

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
        d.addCallbacks(self._run_rrdtool, self._eb)
        d.addErrback(self._eb_rrdtool)
        d.addCallback(self._get_ds)
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

    def _run_rrdtool(self, perf):
        if perf is None:
            return None
        cmd = '%(timestamp)s:%(value)s' % perf
        filename = self._get_msg_filename(perf)
        basedir = os.path.dirname(filename)
        self._makedirs(basedir)
        d2 = self.rrdtool.run("update", filename, cmd)
        d2.addCallback(lambda x: perf)
        return d2

    def _eb_rrdtool(self, f):
        f.trap(RRDToolError)
        LOGGER.error(_("RRDtool could not update the file %(filename)s. "
                       "Message: %(msg)s"), {
                     'filename': f.value.filename,
                     'msg': f.getErrorMessage() })

    def _get_ds(self, perf):
        if perf is None:
            return None
        ds = self.confdb.get_datasource(perf["host"], perf["datasource"])
        ds.addCallback(self._has_threshold, perf)
        return ds

    def _has_threshold(self, ds, perf):
        attrs = [
            'warning_threshold',
            'critical_threshold',
            'nagiosname',
            'jid',
        ]

        # S'il n'y a pas de seuil sur cette source de données,
        # inutile d'aller plus loin.
        for attr in attrs:
            if ds[attr] is None:
                return

        filename = self._get_msg_filename(perf)
        last = self.rrdtool.run("lastupdate", filename, '')
        last.addCallback(self._check_thresholds, ds, perf['host'])
        return last

    def _check_thresholds(self, last, ds, host):
        # Modèle pour la commande à envoyer à Nagios.
        tpl =   u'<%(onetoone)s to="%(recipient)s">'\
                '<command xmlns="%(namespace)s">'\
                    '<timestamp>%(timestamp)f</timestamp>'\
                    '<cmdname>PROCESS_SERVICE_CHECK_RESULT</cmdname>'\
                    '<value>%(host)s;%(service)s;%(state)d;%(msg)s</value>'\
                '</command>'\
                '</%(onetoone)s>'

        # Substitutions pour le template.
        params = {
            'namespace': NS_COMMAND,
            'timestamp': self.get_current_time(),
            'host': host,
            'service': ds['nagiosname'],
            'onetoone': MESSAGEONETOONE,
            'recipient': ds['jid'],
        }

        def msg_sent(_dummy):
            self._messages_sent += 1

        # La réponse de rrdtool est de la forme " DS\n\ntimestamp: value\n"
        # en cas de succès et "" en cas d'erreur.
        # On s'arrange pour récupérer uniquement la valeur.
        if not last:
            return

        last = last.split(':', 2)[1].strip()
        if last == 'U' or not last:
            return

        last = float(last)
        last *= float(ds['factor'])

        # Si la dernière valeur est entière,
        # on la représente comme telle.
        if int(last) == last:
            last = int(last)

        try:
            if is_out_of_bounds(last, ds['critical_threshold']):
                params['state'] = 2 # CRITICAL dans Nagios
                params['msg'] = 'CRITICAL: %s' % last
        except ValueError:
            # La définition de seuils donnée était invalide.
            params['state'] = 3 # UNKNOWN dans Nagios
            params['msg'] = 'UNKNOWN: Invalid critical threshold ' \
                            'specification (%r)' % ds['critical_threshold']

        if 'state' not in params:
            try:
                if is_out_of_bounds(last, ds['warning_threshold']):
                    params['state'] = 1 # WARNING dans Nagios
                    params['msg'] = 'WARNING: %s' % last
                else:
                    params['state'] = 0 # OK dans Nagios
                    params['msg'] = 'OK: %s' % last
            except ValueError:
                # La définition de seuils donnée était invalide.
                params['state'] = 3 # UNKNOWN dans Nagios
                params['msg'] = 'UNKNOWN: Invalid warning threshold ' \
                                'specification (%r)' % ds['warning_threshold']

        sent = self.sendItem(tpl % params)
        sent.addCallback(msg_sent)

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
        stats = yield super(NodeToRRDtoolForwarder, self).getStats()
        ds_count = yield self.confdb.count_datasources()
        stats["pds_count"] = ds_count
        defer.returnValue(stats)

    def stop(self):
        """
        Utilisée par les tests
        """
        if self._task_process_queue.running:
            self._task_process_queue.stop()
        self.confdb.stop()
        self.rrdtool.stop()

    def sendItem(self, item):
        if not isinstance(item, etree.ElementBase):
            item = parseXml(item.encode('utf-8'))
        if item.name == MESSAGEONETOONE:
            self.sendOneToOneXml(item)
            return defer.succeed(None)
        else:
            result = self.publishXml(item)
            return result

