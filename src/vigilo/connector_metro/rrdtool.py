# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""
Gestion d'un process RRDTool pour écrire ou lire des RRDs.

@todo: gérer un I{pool} de process RRDTool
@note: U{http://twistedmatrix.com/documents/current/core/howto/process.html}
"""

import sys
import os
import stat
import inspect
import warnings

from twisted.internet import stdio, reactor, protocol, defer, task
from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.protocols import basic
from twisted.python.failure import Failure

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__, silent_load=True)

from vigilo.common.gettext import translate
_ = translate(__name__)

from vigilo.connector_metro.vigiconf_settings import vigiconf_settings


class RRDToolManager(object):
    """
    Lance une instance de RRDTool en mode démon dans un sous-processus et le
    redémarre s'il s'arrête.
    """

    def __init__(self, readonly=False):
        self.readonly = readonly
        rrd_bin = settings['connector-metro']['rrd_bin']
        self._rrdtool = RRDToolProcessProtocol(rrd_bin)

    def start(self):
        """
        Lance une instance de RRDtool dans un sous-processus
        """
        try:
            self.ensureDirectory(settings['connector-metro']['rrd_base_dir'])
            self.checkBinary()
        except OSError, e:
            return defer.fail(e)

        if self._rrdtool.transport is not None:
            return defer.succeed(self._rrdtool.transport.pid)
        return self._rrdtool.start()

    def stop(self):
        self._rrdtool.quit()

    def checkBinary(self):
        rrd_bin = settings['connector-metro']['rrd_bin']
        if not os.path.isfile(rrd_bin):
            raise OSError(_('Unable to start "%(rrdtool)s". Make sure the '
                            'path is correct.') % {'rrdtool': self.rrdbin})
        if not os.access(rrd_bin, os.X_OK):
            raise OSError(_('Unable to start "%(rrdtool)s". Make sure '
                            'RRDtool is installed and you have '
                            'permissions to use it.') % {
                                'rrdtool': self.rrdbin,
                            })

    def ensureDirectory(self, directory):
        """
        Vérifier la présence et les permissions d'un dossier, et le crée si
        besoin avec ces bonnes permissions
        """
        if not os.access(directory, os.F_OK):
            if self.readonly:
                raise OSError(_("The RRD directory does not exist: %s" % directory))
            try:
                os.makedirs(directory)
                os.chmod(directory, # chmod 755
                         stat.S_IRUSR|stat.S_IWUSR|stat.S_IXUSR |\
                         stat.S_IRGRP | stat.S_IXGRP | \
                         stat.S_IROTH | stat.S_IXOTH)
            except OSError, e:
                raise OSError(_("Unable to create directory '%(dir)s'") % {
                                'dir': e.filename,
                            })
        if not self.readonly and not os.access(directory, os.W_OK):
            raise OSError(_("Unable to write in the "
                            "directory '%(dir)s'") % {'dir': directory})

    def run(self, command, filename, args):
        """
        Lance une commande par RRDTool

        @param command: le type de commande envoyée à RRDtool (C{fetch},
            C{create}, C{update}...)
        @type  command: C{str}
        @param filename: le nom du fichier RRD
        @type  filename: C{str}
        @param args: les arguments pour la commande envoyée à RRDtool
        @type  args: C{str} ou C{list}
        @return: le Deferred contenant le résultat ou l'erreur
        @rtype: C{Deferred}
        """
        return self._rrdtool.run(command, filename, args)


class RRDToolProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, rrd_bin):
        self.rrd_bin = rrd_bin
        self.deferred = None
        self.deferred_start = None
        self._current_data = []
        self._keep_alive = True

    def start(self):
        if self.transport is not None:
            return defer.succeed(self.transport.pid)
        LOGGER.debug("Starting rrdtool process in server mode")
        self.deferred_start = defer.Deferred()
        reactor.spawnProcess(self, self.rrd_bin, [self.rrd_bin, "-"])
        return self.deferred_start

    def connectionMade(self):
        if self.deferred_start is not None:
            LOGGER.info(_("Started RRDtool subprocess: pid %(pid)d"),
                          {'pid': self.transport.pid})
            self.deferred_start.callback(self.transport.pid)

    def run(self, command, filename, args):
        """
        Execute une commande par le process RRDTool, et retourne le Deferred
        associé.

        @param command: le type de commande envoyée à RRDtool (C{fetch},
            C{create}, C{update}...)
        @type  command: C{str}
        @param filename: le nom du fichier RRD
        @type  filename: C{str}
        @param args: les arguments pour la commande envoyée à RRDtool
        @type  args: C{str} ou C{list}
        @return: le Deferred contenant le résultat ou l'erreur
        @rtype: C{Deferred}
        """
        self.deferred = defer.Deferred()
        if isinstance(args, list):
            args = " ".join(args)
        complete_cmd = "%s %s %s" % (command, filename, args)
        LOGGER.debug('Running this command: %s' % complete_cmd)
        self.transport.write("%s\n" % complete_cmd)
        return self.deferred

    def outReceived(self, data):
        self._current_data.append(data)
        if data.count("OK ") == 0 and data.count("ERROR: ") == 0:
            return # pas encore fini
        data = "".join(self._current_data)
        return self._handle_result(data)

    def errReceived(self, data):
        return self.outReceived(data)

    def _handle_result(self, data):
        self._current_data = []
        if self.deferred is None:
            LOGGER.warning(_("No deferred available in _handle_result(), "
                             "this should not happen"))
            return
        for line in data.split("\n"):
            if line.startswith("OK "):
                self.deferred.callback("\n".join(self._current_data))
                break
            elif line.startswith("ERROR: "):
                self.deferred.errback(line[7:])
                break
            self._current_data.append(line)
        self._current_data = []

    def quit(self):
        self._keep_alive = False
        self.transport.write("quit\n")
        self.transport.loseConnection()
        #self.transport.signalProcess('TERM')

    def processEnded(self, reason):
        if isinstance(reason.value, ProcessDone):
            LOGGER.warning(_('The RRDTool process exited normally'))
        elif isinstance(reason.value, ProcessTerminated):
            LOGGER.warning(_('The RRDTool process was terminated abnormally '
                             'with exit code %(rcode)d and message: %(msg)s'),
                           {"rcode": reason.value.exitCode,
                            "msg": reason.getErrorMessage()})
        if not self._keep_alive:
            return
        # respawn
        LOGGER.info(_('Restarting...'))
        self.start()


