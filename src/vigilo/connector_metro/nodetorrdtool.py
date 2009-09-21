# vim: set fileencoding=utf-8 sw=4 ts=4 et :

"""
Extends pubsub clients to compute Node message.
"""
from __future__ import absolute_import

#from twisted.words.xish import domish

from vigilo.common.logging import get_logger
from vigilo.common.conf import settings
import os
import popen2
from wokkel import xmppim
from wokkel.pubsub import PubSubClient
from twisted.words.protocols.jabber import xmlstream
#import rrdtool
from urllib import quote

LOGGER = get_logger(__name__)

from vigilo.common.gettext import translate
_ = translate(__name__)

#class MetroError(Exception):
#    def __init__(self, msg):
#        self.msg = msg
#        LOGGER.error(self.msg)

class NodeToRRDtoolForwarder(PubSubClient):
    """
    Receives perf messages on the xmpp bus, and passes them to RRDtool.
    Forward Node to RRDtool.
    """

    def __init__(self, fileconf):
        LOGGER.debug("entrée dans NodeToRRDtoolForwarder")
        PubSubClient.__init__(self)

        self._fileconf = fileconf
        try :
            settings.load_file(self._fileconf)
        except IOError, e:
            LOGGER.error(_(e))
            raise e
        self._rrd_base_dir = settings['RRD_BASE_DIR']
        self._rrdtool = None
        self._rrdbin = settings['RRD_BIN']
        self.startRRDtoolIfNeeded()
        self.increment = 0
        self.hosts = settings['HOSTS']


    
    def connectionInitialized(self):
        # Called when we are connected and authenticated
        PubSubClient.connectionInitialized(self)
        self.send(xmppim.AvailablePresence())
        self.startRRDtoolIfNeeded()

    def startRRDtoolIfNeeded(self):
        """
        Start a Subprocess of rrdtool (if needed) in order to treat command
        """
        if not os.access(self._rrd_base_dir, os.F_OK):
            try:
                os.makedirs(self._rrd_base_dir)
            except OSError, e:
                LOGGER.error(_("Impossible to create the directory '%(dir)s'") % \
                             {'dir': e.filename})
                raise e
        if not os.access(self._rrd_base_dir, os.W_OK):
            LOGGER.error(_("Impossible to write in the directory '%(dir)s'") % \
                         {'dir': self._rrd_base_dir})
            raise OSError(_("Impossible to write in the directory '%(dir)s'") % \
                         {'dir': self._rrd_base_dir})

        if self._rrdtool == None:
            self._rrdtool = popen2.Popen3("%s -" % self._rrdbin)
            LOGGER.info(_("started rrdtool subprocess: pid %(pid)d") % \
                        {'pid': self._rrdtool.pid})
        else:
            r = self._rrdtool.poll()
            if r != -1:
                self._rrdtool = popen2.Popen3("%s -" % "/usr/bin/rrdtool")
                LOGGER.info(_("rrdtool seemed to exit with return code %(returncode)d, restarting it... pid %(pid)d" % \
                            {'returncode': r, 'pid': self._rrdtool.pid}))

    def RRDRun(self, cmd, filename, args):
        """
        update an RRD by sending it a command to an rrdtool's instance pipe
        """
        self.startRRDtoolIfNeeded()
        self._rrdtool.tochild.write("%s %s %s\n"%(cmd, filename, args))
        self._rrdtool.tochild.flush()
        res = self._rrdtool.fromchild.readline()
        lines = res
        while not res.startswith("OK ") and not res.startswith("ERROR: "):
            res = self._rrdtool.fromchild.readline()
            lines += res
        if not res.startswith("OK"):
            LOGGER.error(_("'RRDtool send back Error message on this command '%(cmd)s' with this file '%(filename)s' the message from RRDtool is '%(msg)s") % \
                         {'cmd': cmd, 'filename': filename, 'msg': lines})

    def createRRD(self, filename, perf, dry_run = False):
        """creates a new RRD based on the default fitting configuration"""
        # to avoid an error just after creating the rrd file :
        # (minimum one second step)
        # the creation and updating time needs to be different.
        timestamp = int("%(timestamp)s" % perf) - 10 
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
            except OSError, e:
                LOGGER.error(_("Impossible to create the directory '%(dir)s'") % \
                             {'dir': e.filename})
                raise e
        host_ds = "%(host)s/%(datasource)s" % perf
        if not self.hosts.has_key(host_ds) :
            LOGGER.error(_("Host with this datasource '%(host_ds)s' not found in the configuration file (%(fileconf)s) !") % \
                         {'host_ds': host_ds, 'fileconf': self._fileconf})
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
        LOGGER.debug("entrée dans messageForward()")
        if msg.name != 'perf':
            LOGGER.error(_("'%(msgtype)s' is not a valid message type for metrology") % \
                         {'msgtype' : msg.name})
            return
        perf = {}
        for c in msg.children:
            perf[c.name.__str__()]=quote(c.children[0].__str__())
        
        if 'timestamp' not in perf or 'value' not in perf or \
           'host' not in perf or 'datasource' not in perf:
            
            for i in 'timestamp', 'value', 'host', 'datasource':
                if i not in perf:
                    LOGGER.error(_("not a valid perf message (%(i)s is missing '%(perfmsg)s'") % \
                            {'i': i, 'perfmsg': perf})
            return
        

        # just to test TODO remove the next lines in production 
        # (the on with the increment of timestamp)
        self.increment += 1
        print self.increment
        timestamp = int(perf['timestamp'])

        perf['timestamp'] = (timestamp + self.increment).__str__()

        cmd = '%(timestamp)s:%(value)s' % perf

        print cmd

        filename = self._rrd_base_dir + '/%(host)s/%(datasource)s' % perf 
        basedir = os.path.dirname(filename)
        if not os.path.exists(basedir):
            try:
                os.makedirs(basedir)
            except OSError, e:
                message = "Impossible to create the directory '%s'" % e.filename
                print message
        if not os.path.isfile(filename):
            self.createRRD(filename, perf)
        self.RRDRun('update', filename, cmd)
        #rrdtool.update(cmd)



    def itemsReceived(self, event):
        """ 
        function to treat a received item 
        
        @param event: event to treat
        @type  event: xml object

        """
        LOGGER.debug("entrée dans itemsReceived()")
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

