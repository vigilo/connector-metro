# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""
Ce module fournit un demi-connecteur capable de lire des messages
depuis un bus XMPP pour les stocker dans une base de données RRDtool.
"""
from subprocess import Popen, PIPE
import os
import stat
import errno
import signal

from twisted.words.protocols.jabber import xmlstream
from wokkel import xmppim
from wokkel.pubsub import PubSubClient

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.common.logging import get_logger
from vigilo.common.gettext import translate
from vigilo.connector_metro.vigiconf_settings import vigiconf_settings

LOGGER = get_logger(__name__)
_ = translate(__name__)


class NodeToRRDtoolForwarderError(Exception): pass

class NodeToRRDtoolForwarder(PubSubClient):
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

        super(NodeToRRDtoolForwarder, self).__init__()

        # Sauvegarde du handler courant pour SIGHUP
        # et ajout de notre propre handler pour recharger
        # le connecteur (lors d'un service ... reload).
        self._prev_sighup_handler = signal.getsignal(signal.SIGHUP)
        signal.signal(signal.SIGHUP, self._sighup_handler)

        self.fileconf = fileconf
        self.rrd_base_dir = settings['connector-metro']['rrd_base_dir']
        self._rrdtool = None
        self.rrdbin = settings['connector-metro']['rrd_bin']

        # Provoque le chargement de la configuration
        # issues de VigiConf.
        self._sighup_handler(None, None)

        self.startRRDtoolIfNeeded()


    def connectionInitialized(self):
        """
        Cette méthode est appelée lorsque la connexion est initialisée,
        c'est-à-dire lorsque la connexion a réussi et que les échanges
        initiaux (handshakes) sont terminés.
        """

        # Appelé lorsque la connexion est prête (connexion + handshake).
        super(NodeToRRDtoolForwarder, self).connectionInitialized()

        # Ajout d'un observateur pour intercepter
        # les messages de chat "one-to-one".
        self.xmlstream.addObserver("/message[@type='chat']", self.chatReceived)

        # There's probably a way to configure it (on_sub vs on_sub_and_presence)
        # but the spec defaults to not sending subscriptions without presence.
        self.send(xmppim.AvailablePresence())
        LOGGER.info(_('Connection initialized'))
        self.startRRDtoolIfNeeded()

    def startRRDtoolIfNeeded(self):
        """
        Lance une instance de RRDtool dans un sous-processus
        afin de traiter les commandes.
        """
        if not os.access(self.rrd_base_dir, os.F_OK):
            try:
                os.makedirs(self.rrd_base_dir)
                os.chmod(self.rrd_base_dir, # chmod 755
                         stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR |\
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                raise OSError(_("Unable to create directory '%(dir)s'") % {
                                'dir': e.filename,
                            })
        if not os.access(self.rrd_base_dir, os.W_OK):
            raise OSError(_("Unable to write in the "
                            "directory '%(dir)s'") % {
                                'dir': self.rrd_base_dir,
                            })

        if self._rrdtool is None:
            try:
                self._rrdtool = Popen([self.rrdbin, "-"], stdin=PIPE, stdout=PIPE)
                LOGGER.info(_("Started RRDtool subprocess: pid %(pid)d"), {
                                    'pid': self._rrdtool.pid,
                            })
            except OSError, e:
                if e.errno == errno.ENOENT:
                    raise OSError(_('Unable to start "%(rrdtool)s". Make sure '
                                    'RRDtool is installed and you have '
                                    'permissions to use it.') % {
                                        'rrdtool': self.rrdbin,
                                    })
        else:
            r = self._rrdtool.poll()
            if r != None:
                LOGGER.info(_("RRDtool seemed to exit with return code "
                              "%(returncode)d, restarting it..."), {
                                'returncode': r,
                            })
                # Force la création d'un nouveau processus
                # pour remplacer celui qui vient de mourir.
                self._rrdtool = None
                self.startRRDtoolIfNeeded()

    def RRDRun(self, cmd, filename, args):
        """
        update an RRD by sending it a command to an rrdtool's instance pipe.
        @param cmd: la commande envoyée à RRDtool
        @type cmd: C{str}
        @param filename: le nom du fichier RRD.
        @type filename: C{str}
        @param args: les arguments pour la commande envoyée à RRDtool
        @type args: C{str}
        """
        self.startRRDtoolIfNeeded()
        self._rrdtool.stdin.write("%s %s %s\n"%(cmd, filename, args))
        self._rrdtool.stdin.flush()
        res = self._rrdtool.stdout.readline()
        lines = res
        while not res.startswith("OK ") and not res.startswith("ERROR: "):
            res = self._rrdtool.stdout.readline()
            lines += res
        if not res.startswith("OK"):
            LOGGER.error(_("RRDtool choked on this command '%(cmd)s' using "
                            "this file '%(filename)s'. RRDtool replied "
                            "with: '%(msg)s'"), {
                                'cmd': cmd,
                                'filename': filename,
                                'msg': lines.strip(),
                            })

    def createRRD(self, filename, perf, dry_run=False):
        """
        Crée un nouveau fichier RRD avec la configuration adéquate.

        @param filename: Nom du fichier RRD à générer.
        @type filename: C{str}
        @param perf: Dictionnaire décrivant la source de données, contenant les
            clés suivantes:
             - C{host}: nom d'hôte
             - C{datasource}: nom de l'indicateur, qui doit être encodé avec
               urllib.quote_plus (RFC 1738).
             - C{timestamp}: timestamp UNIX de la mise à jour
        @type perf: C{dict}
        @param dry_run: Indique que les actions ne doivent pas réellement
            être effectuées (mode simulation).
        @type dry_run: C{bool}
        """
        # to avoid an error just after creating the rrd file :
        # (minimum one second step)
        # the creation and updating time needs to be different.
        timestamp = int(perf["timestamp"]) - 10
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
                os.chmod(basedir, # chmod 755
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                LOGGER.error(_("Unable to create the directory '%(dir)s'"), {
                                'dir': e.filename,
                            })
                raise e
        host = perf["host"]
        ds = perf["datasource"]
        if host not in self.hosts or ds not in self.hosts[host]:
            LOGGER.error(_("Host '%(host)s' with datasource '%(ds)s' not found "
                            "in the configuration file (%(fileconf)s) !"), {
                                'host': host, 'ds': ds,
                                'fileconf': self.fileconf,
                        })
            raise NodeToRRDtoolForwarderError()

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

        self.RRDRun("create", filename, " ".join(rrd_cmd))
        os.chmod(filename, # chmod 644
                 stat.S_IRUSR | stat.S_IWUSR | \
                 stat.S_IRGRP | stat.S_IROTH )
        if dry_run:
            os.remove(filename)

    def messageForward(self, msg):
        """
        Transmet un message reçu du bus à RRDtool.

        @param msg: Message à transmettre
        @type msg: C{twisted.words.test.domish Xml}
        """
        if msg.name != 'perf':
            LOGGER.error(_("'%(msgtype)s' is not a valid message type for "
                           "metrology"), {'msgtype' : msg.name})
            return
        perf = {}
        for c in msg.children:
            perf[str(c.name)] = str(c.children[0])

        for i in 'timestamp', 'value', 'host', 'datasource':
            if i not in perf:
                LOGGER.error(_(u"Not a valid performance message (missing "
                               "'%(tag)s' tag)"), {
                                    'tag': i,
                                })
                return

        if perf["host"] not in self.hosts:
            LOGGER.debug("Skipping perf update for host %s" % perf["host"])
            return

        cmd = '%(timestamp)s:%(value)s' % perf
        filename = os.path.join(self.rrd_base_dir, perf["host"],
                                "%s.rrd" % perf["datasource"])
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
                os.chmod(basedir, # chmod 755
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                LOGGER.error(_("Unable to create the directory '%s'"),
                    e.filename)
        if not os.path.isfile(filename):
            try:
                self.createRRD(filename, perf)
            except NodeToRRDtoolForwarderError, e:
                return # On saute cette mise à jour
        self.RRDRun('update', filename, cmd)

    def chatReceived(self, msg):
        """
        Fonction de traitement des messages de discussion reçus.

        @param msg: Message à traiter.
        @type  msg: C{twisted.words.xish.domish.Element}

        """
        # Il ne devrait y avoir qu'un seul corps de message (body)
        bodys = [element for element in msg.elements()
                         if element.name in ('body',)]

        for b in bodys:
            # les données dont on a besoin sont juste en dessous
            for data in b.elements():
                LOGGER.debug(_('Chat message to forward: %s'),
                               data.toXml().encode('utf8'))
                self.messageForward(data)


    def itemsReceived(self, event):
        """
        Fonction de traitement des événements XMPP reçus.

        @param event: Événement XMPP à traiter.
        @type  event: C{twisted.words.xish.domish.Element}

        """
        for item in event.items:
            # Item is a domish.IElement and a domish.Element
            # Serialize as XML before queueing,
            # or we get harmless stderr pollution  × 5 lines:
            # Exception RuntimeError: 'maximum recursion depth exceeded in
            # __subclasscheck__' in <type 'exceptions.AttributeError'> ignored
            # Stderr pollution caused by http://bugs.python.org/issue5508
            # and some touchiness on domish attribute access.
            if item.name != 'item':
                # The alternative is 'retract', which we silently ignore
                # We receive retractations in FIFO order,
                # ejabberd keeps 10 items before retracting old items.
                continue
            it = [ it for it in item.elements() if item.name == "item" ]
            for i in it:
                self.messageForward(i)

    def _sighup_handler(self, signum, frames):
        """
        Provoque un rechargement de la configuration Python
        issue de VigiConf pour le connecteur de métrologie.

        @param signum: Signal qui a déclenché le rechargement (= SIGHUP).
        @type signum: C{int} ou C{None}
        @param frames: Frames d'exécution interrompues par le signal.
        @type frames: C{list}
        """

        # Si signum vaut None, alors on a été appelé depuis __init__.
        if signum is not None:
            LOGGER.info(_("Received signal to reload the configuration file"))

        try:
            vigiconf_settings.load_configuration(self.fileconf)
        except IOError, e:
            LOGGER.exception(_("Got exception"))
            raise e
        self.hosts = vigiconf_settings['HOSTS']

        # On appelle le précédent handler s'il y en a un.
        # Eventuellement, il s'agira de signal.SIG_DFL ou signal.SIG_IGN.
        # L'appel n'est pas propagé lorsqu'on est appelé par __init__.
        if callable(self._prev_sighup_handler) and signum is not None:
            self._prev_sighup_handler(signum, frames)

