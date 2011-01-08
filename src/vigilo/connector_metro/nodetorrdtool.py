# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""
Ce module fournit un demi-connecteur capable de lire des messages
depuis un bus XMPP pour les stocker dans une base de données RRDtool.
"""
import os
import stat
import signal
import urllib

from twisted.internet import task, defer

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.common.logging import get_logger
from vigilo.common.gettext import translate
from vigilo.connector.forwarder import PubSubListener
from vigilo.common import get_rrd_path
from vigilo.connector_metro.rrdtool import RRDToolManager
from vigilo.connector_metro.vigiconf_settings import vigiconf_settings

LOGGER = get_logger(__name__)
_ = translate(__name__)


class NotInConfiguration(KeyError):
    pass

class InvalidMessage(ValueError):
    pass

class NodeToRRDtoolForwarder(PubSubListener):
    """
    Reçoit des données de métrologie (performances) depuis le bus XMPP
    et les transmet à RRDtool pour générer des base de données RRD.
    """

    def __init__(self, fileconf):
        """
        Instancie un connecteur BUS XMPP vers RRDtool pour le stockage des
        données de performance dans les fichiers RRD.

        @param fileconf: le nom du fichier contenant la définition des hôtes
        @type fileconf: C{str}
        """

        super(NodeToRRDtoolForwarder, self).__init__() # pas de db de backup
        self.rrd_base_dir = settings['connector-metro']['rrd_base_dir']
        # Sauvegarde du handler courant pour SIGHUP
        # et ajout de notre propre handler pour recharger
        # le connecteur (lors d'un service ... reload).
        self._prev_sighup_handler = signal.getsignal(signal.SIGHUP)
        signal.signal(signal.SIGHUP, self._sighup_handler)
        # Configuration
        self._conf_timestamp = 0
        self.fileconf = fileconf
        self._read_conf = task.LoopingCall(self.load_conf)
        self._read_conf.start(10) # toutes les 10s (et maintenant)
        # Sous-processus
        self.rrdtool = RRDToolManager()
        self.max_send_simult = len(self.rrdtool.pool)
        self.rrdtool.start()

    def connectionInitialized(self):
        """
        Cette méthode est appelée lorsque la connexion est initialisée,
        c'est-à-dire lorsque la connexion a réussi et que les échanges
        initiaux (handshakes) sont terminés.
        """
        super(NodeToRRDtoolForwarder, self).connectionInitialized()
        self.rrdtool.start()

    def createRRD(self, filename, perf):
        """
        Crée un nouveau fichier RRD avec la configuration adéquate.

        @param filename: Nom du fichier RRD à générer, le nom de l'indicateur
            doit être encodé avec urllib.quote_plus (RFC 1738).
        @type filename: C{str}
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
        ds = perf["datasource"]
        if host not in self.hosts or ds not in self.hosts[host]:
            LOGGER.error(_("Host '%(host)s' with datasource '%(ds)s' not found "
                            "in the configuration file (%(fileconf)s) !"), {
                                'host': host,
                                'ds': ds,
                                'fileconf': self.fileconf,
                        })
            raise NotInConfiguration()

        values = self.hosts[host][ds]
        rrd_cmd = ["--step", str(values["step"]), "--start", str(timestamp)]
        for rra in values["RRA"]:
            rrd_cmd.append("RRA:%s:%s:%s:%s" % \
                           (rra["type"], rra["xff"], \
                            rra["step"], rra["rows"]))

        ds_tpl = values["DS"]
        rrd_cmd.append("DS:%s:%s:%s:%s:%s" % \
                   (ds_tpl["name"], ds_tpl["type"], ds_tpl["heartbeat"], \
                    ds_tpl["min"], ds_tpl["max"]))

        def chmod_644(result, filename):
            os.chmod(filename, # chmod 644
                     stat.S_IRUSR | stat.S_IWUSR | \
                     stat.S_IRGRP | stat.S_IROTH )
        def errback(result, filename):
            LOGGER.error(_("RRDtool could not create the file: "
                           "%(filename)s. Message: %(msg)s"),
                         { 'filename': filename,
                           'msg': result })
        d = self.rrdtool.run("create", filename, rrd_cmd)
        d.addCallback(chmod_644, filename)
        d.addErrback(errback, filename)
        return d

    def _parse_message(self, msg):
        if msg.name != 'perf':
            errormsg = _("'%(msgtype)s' is not a valid message type for "
                         "metrology")
            raise InvalidMessage(errormsg % {'msgtype' : msg.name})
        perf = {}
        for c in msg.children:
            perf[str(c.name)] = str(c.children[0])

        for i in 'timestamp', 'value', 'host', 'datasource':
            if i not in perf:
                errormsg = _(u"Not a valid performance message (missing "
                              "'%(tag)s' tag)")
                raise InvalidMessage(errormsg % {"tag": i})

        if perf["host"] not in self.hosts:
            raise NotInConfiguration("Skipping perf update for host %s"
                                     % perf["host"])
        return perf

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
                os.mkdir(cur_dir) # l'option 'mode' de mkdir respecte l'umask, dommage
                os.chmod(cur_dir, # chmod 755
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                LOGGER.error(_("Unable to create the directory '%s'"), cur_dir)
                raise e

    def create_if_needed(self, filename, msgdata):
        """Création du RRD si besoin"""
        if os.path.isfile(filename):
            return defer.succeed(None)
        # compatibilité
        old_filename = os.path.join(self.rrd_base_dir, msgdata["host"], "%s.rrd"
                                    % urllib.quote_plus(msgdata["datasource"]))
        if os.path.isfile(old_filename):
            os.rename(old_filename, filename)
            return defer.succeed(None)
        else:
            # création
            return self.createRRD(filename, msgdata)

    def isConnected(self):
        """Sauf cas exceptionnel, on est toujours connecté"""
        return self.rrdtool.started

    def processMessage(self, msg):
        """
        Transmet un message reçu du bus à RRDtool.
        @param msg: Message à transmettre
        @type msg: C{twisted.words.test.domish Xml}
        """
        try:
            perf = self._parse_message(msg)
        except InvalidMessage, e:
            LOGGER.error(str(e))
            return defer.succeed(None)
        except NotInConfiguration, e:
            LOGGER.debug(str(e))
            return defer.succeed(None)

        cmd = '%(timestamp)s:%(value)s' % perf
        rrd_dir = settings['connector-metro']['rrd_base_dir']
        rrd_path_mode = settings['connector-metro']['rrd_path_mode']
        filename = get_rrd_path(perf["host"], perf["datasource"],
                                rrd_dir, rrd_path_mode)
        basedir = os.path.dirname(filename)
        self._makedirs(basedir)

        try:
            create_d = self.create_if_needed(filename, perf)
        except NotInConfiguration:
            return defer.succeed(None) # On saute cette mise à jour
        # MAJ du RRD
        def update_rrd(result):
            update_d = self.rrdtool.run("update", filename, cmd)
            update_d.addErrback(errback, filename)
            return update_d # chaînage
        def errback(result, filename):
            LOGGER.error(_("RRDtool could not update the file: "
                           "%(filename)s. Message: %(msg)s"),
                         { 'filename': filename,
                           'msg': result.getErrorMessage() })
        create_d.addCallback(update_rrd)
        return create_d

    def load_conf(self):
        """
        Provoque un rechargement de la configuration Python
        issue de VigiConf pour le connecteur de métrologie.
        """
        current_timestamp = os.stat(self.fileconf).st_mtime
        if current_timestamp <= self._conf_timestamp:
            return # ça n'a pas changé
        LOGGER.debug("Re-reading configuration file")
        try:
            vigiconf_settings.load_configuration(self.fileconf)
        except IOError, e:
            LOGGER.exception(_("Got exception"))
            raise e
        self.hosts = vigiconf_settings['HOSTS']
        self._conf_timestamp = current_timestamp

    def _sighup_handler(self, signum, frames):
        """
        Gestionnaire du signal SIGHUP: recharge la conf.

        @param signum: Signal qui a déclenché le rechargement (= SIGHUP).
        @type signum: C{int} ou C{None}
        @param frames: Frames d'exécution interrompues par le signal.
        @type frames: C{list}
        """
        LOGGER.info(_("Received signal to reload the configuration file"))
        self.load_conf()
        # On appelle le précédent handler s'il y en a un.
        # Eventuellement, il s'agira de signal.SIG_DFL ou signal.SIG_IGN.
        if callable(self._prev_sighup_handler):
            self._prev_sighup_handler(signum, frames)

    def stop(self):
        """
        Utilisée par les tests
        """
        self._read_conf.stop()
        self.rrdtool.stop()

