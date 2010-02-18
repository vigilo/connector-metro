# vim: set fileencoding=utf-8 sw=4 ts=4 et :

"""
Extends pubsub clients to compute Node message.
"""
from __future__ import absolute_import

from subprocess import Popen, PIPE
from urllib import quote
import errno
import os

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


class NodeToRRDtoolForwarder(PubSubClient):
    """
    Receives perf messages on the xmpp bus, and passes them to RRDtool.
    Forward Node to RRDtool.
    """

    def __init__(self, fileconf):
        """
        Instancie un connecteur BUS XMPP vers RRDtool pour le stockage des 
        données de performance dans les fichiers RRD.

        @param fileconf: le nom du fichier contenant la définition des hôtes
        @type fileconf: C{str}
        """

        PubSubClient.__init__(self)

        self._fileconf = fileconf
        try:
            vigiconf_settings.load_configuration(self._fileconf)
        except IOError, e:
            LOGGER.exception(_("Got exception"))
            raise e
        self._rrd_base_dir = settings['connector-metro']['rrd_base_dir']
        self._rrdtool = None
        self._rrdbin = settings['connector-metro']['rrd_bin']
        self.startRRDtoolIfNeeded()
        self.increment = 0
        self.hosts = vigiconf_settings['HOSTS']

    
    def connectionInitialized(self):
        """ redefinition of the function for loading RRDtool (if needed) """

        # Called when we are connected and authenticated
        PubSubClient.connectionInitialized(self)
        # add an observer to deal with chat message (oneToOne message)
        self.xmlstream.addObserver("/message[@type='chat']", self.chatReceived)

        # There's probably a way to configure it (on_sub vs on_sub_and_presence)
        # but the spec defaults to not sending subscriptions without presence.
        self.send(xmppim.AvailablePresence())
        LOGGER.info(_('ConnectionInitialized'))
        self.startRRDtoolIfNeeded()

    def startRRDtoolIfNeeded(self):
        """
        Start a Subprocess of rrdtool (if needed) in order to treat command
        """
        if not os.access(self._rrd_base_dir, os.F_OK):
            try:
                os.makedirs(self._rrd_base_dir)
            except OSError, e:
                raise OSError(_("Unable to create directory '%(dir)s'") % {
                                'dir': e.filename,
                            })
        if not os.access(self._rrd_base_dir, os.W_OK):
            raise OSError(_("Unable to write in the "
                            "directory '%(dir)s'") % {
                                'dir': self._rrd_base_dir,
                            })

        if self._rrdtool is None:
            try:
                self._rrdtool = Popen([self._rrdbin, "-"], stdin=PIPE, stdout=PIPE)
                LOGGER.info(_("started rrdtool subprocess: pid %(pid)d") % {
                                    'pid': self._rrdtool.pid,
                            })
            except OSError, e:
                if e.errno == errno.ENOENT:
                    raise OSError(_('Unable to start "%(rrdtool)s". Make sure '
                                    'RRDtool is installed and you have '
                                    'permissions to use it.') % {
                                        'rrdtool': self._rrdbin,
                                    })
        else:
            r = self._rrdtool.poll()
            if r != None:
                LOGGER.info(_("rrdtool seemed to exit with return code "
                              "%(returncode)d, restarting it..." % {
                                'returncode': r,
                            }))
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
        @param cmd: les arguments pour la commande envoyée à RRDtool
        @type cmd: C{str}
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
            LOGGER.error(_("'RRDtool send back Error message on this command"
                           "'%(cmd)s' with this file '%(filename)s'. RRDtool "
                           "replied with: '%(msg)s'") % {
                                'cmd': cmd,
                                'filename': filename,
                                'msg': lines,
                            })

    def createRRD(self, filename, perf, dry_run=False):
        """
        creates a new RRD based on the default fitting configuration.
        @param filename: le nom du fichier RRD.
        @type filename: C{str}
        @param perf: la datasource (host/datasource)
        @type perf: C{str}
        @param dry_run: ne pas créer réellement le fichier.
        @type dry_run: C{boolean}
        """
        # to avoid an error just after creating the rrd file :
        # (minimum one second step)
        # the creation and updating time needs to be different.
        timestamp = int("%(timestamp)s" % perf) - 10 
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
            except OSError, e:
                LOGGER.error(_("Impossible to create the directory '%(dir)s'") % {
                                'dir': e.filename,
                            })
                raise e
        host_ds = "%(host)s/%(datasource)s" % perf
        if not self.hosts.has_key(host_ds) :
            LOGGER.error(_("Host with this datasource '%(host_ds)s' not found "
                            "in the configuration file (%(fileconf)s) !") % {
                                'host_ds': host_ds,
                                'fileconf': self._fileconf,
                        })
            return

        values = self.hosts["%(host)s/%(datasource)s" % perf ]
        rrd_cmd = ["--step", str(values["step"]), "--start", str(timestamp)]
        for rra in values["RRA"]:
            rrd_cmd.append("RRA:%s:%s:%s:%s" % \
                           (rra["type"], rra["xff"], \
                            rra["step"], rra["rows"]))

        for ds in values["DS"]:
            rrd_cmd.append("DS:%s:%s:%s:%s:%s" % \
                           (ds["name"], ds["type"], ds["heartbeat"], \
                            ds["min"], ds["max"]))

        self.RRDRun("create", filename, " ".join(rrd_cmd))
        if dry_run:
            os.remove(filename)

    def messageForward(self, msg):
        """
        function to forward the message to RRDtool
        @param msg: message to forward
        @type msg: twisted.words.test.domish Xml
        """
        if msg.name != 'perf':
            LOGGER.error(_("'%(msgtype)s' is not a valid message type for"
                           "metrology") % {'msgtype' : msg.name})
            return
        perf = {}
        for c in msg.children:
            perf[c.name.__str__()]=quote(c.children[0].__str__())
        
        if 'timestamp' not in perf or 'value' not in perf or \
           'host' not in perf or 'datasource' not in perf:
            
            for i in 'timestamp', 'value', 'host', 'datasource':
                if i not in perf:
                    LOGGER.error(_("not a valid perf message (%(i)s is missing "
                                   "'%(perfmsg)s')") % {
                                        'i': i,
                                        'perfmsg': perf,
                                    })
            return


        cmd = '%(timestamp)s:%(value)s' % perf
        filename = self._rrd_base_dir + '/%(host)s/%(datasource)s' % perf 
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
            except OSError, e:
                message = _("Impossible to create the directory '%s'") % e.filename
                LOGGER.error(message)
        if not os.path.isfile(filename):
            self.createRRD(filename, perf)
        self.RRDRun('update', filename, cmd)

    def chatReceived(self, msg):
        """ 
        function to treat a received chat message 
        
        @param msg: msg to treat
        @type  msg: twisted.words.xish.domish.Element

        """
        # It should only be one body
        # Il ne devrait y avoir qu'un seul corps de message (body)
        bodys = [element for element in msg.elements()
                         if element.name in ('body',)]

        for b in bodys:
            # the data we need is just underneath
            # les données dont on a besoin sont juste en dessous
            for data in b.elements():
                LOGGER.debug(_('Chat message to forward: %s') %
                               data.toXml().encode('utf8'))
                self.messageForward(data)


    def itemsReceived(self, event):
        """ 
        function to treat a received item 
        
        @param event: event to treat
        @type  event: twisted.words.xish.domish.Element

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

