# vim: set fileencoding=utf-8 sw=4 ts=4 et :
"""
Sous-agent SNMP pour mettre à disposition les données RRD.

Inspiré de :
http://twistedmatrix.com/documents/current/core/examples/stdiodemo.py
et de http://dreness.com/wikimedia/index.php?title=Net_SNMP
API à respecter : http://www.net-snmp.org/docs/man/snmpd.conf.html#lbBB
"""

import sys
import os
import inspect
import warnings

warnings.filterwarnings('ignore', category=DeprecationWarning,
                        module='^twisted\.')
from twisted.internet import stdio, reactor, protocol, defer, task
from twisted.protocols import basic
from twisted.python.failure import Failure

from vigilo.common.conf import settings
settings.load_module(__name__)

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__, silent_load=True)
# suppression du log sur la sortie standard
for h in LOGGER.parent.handlers:
    if not hasattr(h, "stream"):
        continue
    if h.stream.name == "<stdout>":
        h.close()

from vigilo.common.gettext import translate
_ = translate(__name__)

from vigilo.connector_metro.vigiconf_settings import vigiconf_settings


class RRDNoDataError(Exception):
    pass

class SNMPProtocol(basic.LineReceiver):
    delimiter = '\n' # unix terminal style newlines. remove this line
                     # for use with Telnet
    current_command = None
    current_args = []

    def __init__(self, parent):
        self.parent = parent
        self.commands = self.list_commands()

    def connectionMade(self):
        LOGGER.info(_("Connection to the SNMP daemon established"))

    def connectionLost(self, reason):
        LOGGER.info("Connection lost")
        self.parent.quit()

    def lineReceived(self, line):
        line = line.strip()
        if not line:
            return self.do_quit()

        if line in self.commands:
            self.current_command = line
            argslen = self.commands[line]["argslen"]
            if argslen == 0:
                self.commands[line]["method"]()
                self.current_command = None
            self.current_args = []
            return
        elif not self.current_command:
            LOGGER.error("ERROR: no such command: %s" % line)
            self.sendLine("ERROR: no such command: %s" % line)
            return

        argslen = self.commands[self.current_command]["argslen"]
        self.current_args.append(line)
        if len(self.current_args) == argslen:
            # Exécution de la commande
            method = self.commands[self.current_command]["method"]
            try:
                method(*self.current_args)
            except Exception, e:
                self.sendLine('Error: ' + str(e))
            self.current_command = None

    def list_commands(self):
        commands = {}
        for method_name in dir(self):
            if not method_name.startswith("do_"):
                continue
            method = getattr(self, method_name)
            commands[method_name[3:]] = {
                    "method": method,
                    "argslen": len(inspect.getargspec(method)[0]) - 1,
                    }
        return commands

    def do_quit(self):
        """quit: Quit this session"""
        self.sendLine('Goodbye.')
        self.transport.loseConnection()
    def do_exit(self):
        self.do_quit()

    def do_PING(self):
        d = self.parent.start()
        def pong(pid, self):
            self.sendLine("PONG")
        d.addCallback(pong, self)

    def do_set(self, oid, value):
        """Non disponible"""
        self.sendLine("not-writable")

    def do_get(self, oid):
        LOGGER.debug("Getting OID %s" % oid)
        base_oid = settings['connector-metro'].get('base_oid')
        if not oid.startswith(base_oid+"."):
            LOGGER.warning(_("Received OID outside my base: %s"), oid)
            self.sendLine("NONE")
            return
        d = self.parent.get(oid)
        d.addCallback(self.write_result, oid)
        d.addErrback(self.write_error, oid)

    def do_getnext(self, oid):
        # On ne fait pas de getnext, trop consommateur
        self.sendLine("NONE")

    def write_result(self, result, oid):
        #LOGGER.debug("Sending result: %s" % result)
        self.sendLine(oid)
        self.sendLine("gauge") # integer, gauge, counter, timeticks, ipaddress, objectid, string
        self.sendLine(result)

    def write_error(self, error, oid):
        LOGGER.warning("Error: %s" % error.getErrorMessage())
        if error.check(RRDNoDataError) is not None:
            self.sendLine(oid)
            self.sendLine("string")
            self.sendLine(error.getErrorMessage())
        else:
            self.sendLine("NONE")


class RRDToolProcessProtocol(protocol.ProcessProtocol):

    def __init__(self):
        self.deferred = None
        self.deferred_start = None
        self._current_data = []
        self._keep_alive = True

    def start(self):
        if self.transport is not None:
            return defer.succeed(self.transport.pid)
        LOGGER.debug("Starting rrdtool process in server mode")
        rrd_bin = settings['connector-metro']['rrd_bin']
        self.deferred_start = defer.Deferred()
        reactor.spawnProcess(self, rrd_bin, [rrd_bin, "-"])
        return self.deferred_start

    def connectionMade(self):
        if self.deferred_start is not None:
            self.deferred_start.callback(self.transport.pid)

    def run(self, command, filename, args):
        self.deferred = defer.Deferred()
        if isinstance(args, list):
            args = " ".join(args)
        complete_cmd = "%s %s %s" % (command, filename, args)
        LOGGER.debug('Running this command: %s' % complete_cmd)
        self.transport.write("%s\n" % complete_cmd)
        return self.deferred

    def outReceived(self, data):
        self._current_data.append(data)
        if data.count("\nOK ") == 0 and data.count("\nERROR: ") == 0:
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
        #os.kill(self.transport.pid, signal.SIGTERM)

    def processEnded(self, status_object):
        LOGGER.warning(_('The RRDTool process stopped: %s'), status_object.getErrorMessage())
        if not self._keep_alive:
            return
        # respawn
        self.start()


class SNMPtoRRDTool(object):

    def __init__(self):
        LOGGER.info(_("SNMP to RRDTool gateway started"))
        self._rrdtool = None
        self.hosts = {}
        self.conf_timestamp = 0
        # Vérification des permissions
        self.flight_checks()
        # Lecture de la conf
        read_conf = task.LoopingCall(self.load_conf)
        read_conf.start(10) # toutes les 10s
        # Interface SNMP
        self.snmp = SNMPProtocol(self)
        stdio.StandardIO(self.snmp)

    def quit(self):
        LOGGER.info(_("SNMP to RRDTool gateway stopped"))
        if self._rrdtool is not None:
            self._rrdtool.quit()
        reactor.stop()

    def start(self):
        d = self.start_rrdtool()
        return d

    def load_conf(self):
        conffile = settings['connector-metro']['config']
        current_timestamp = os.stat(conffile).st_mtime
        if current_timestamp <= self.conf_timestamp:
            return # ça a pas changé
        LOGGER.debug("Re-reading configuration file")
        vigiconf_settings.load_configuration(conffile)
        self.hosts = vigiconf_settings['HOSTS']
        self.conf_timestamp = current_timestamp

    def flight_checks(self):
        # configuration
        try:
            settings['connector-metro']['base_oid']
        except KeyError, e:
            if len(sys.argv) > 1:
                settings['connector-metro']['base_oid'] = sys.argv[1]
            else:
                return self._die(_("ERROR: The 'base_oid' configuration setting is not set"))
        # permissions sur le dossier
        rrd_dir = settings['connector-metro']['rrd_base_dir']
        if not os.access(rrd_dir, os.F_OK):
            return self._die(_("ERROR: RRD directory does not exist: %s" % rrd_dir))

    def _die(self, message):
        LOGGER.error(message)
        print message
        sys.exit(1)

    def get(self, oid):
        try:
            rrd_file = self.oid_to_rrdfile(oid)
        except ValueError, e:
            return defer.fail(e)
        host, ds = rrd_file.split("/")
        LOGGER.debug("getting last value for host %s and ds %s" % (host, ds))
        rrd_dir = settings['connector-metro']['rrd_base_dir']
        rrd_file = os.path.join(rrd_dir, rrd_file+".rrd")
        if not os.path.exists(rrd_file):
            return defer.fail(IOError(_("no such RRD file: %s") % rrd_file))
        step = int(self.hosts[host][ds]["step"])
        duration = step * 3
        d = self._rrdtool.run("fetch", rrd_file, ["AVERAGE", "--start", "-%s" % duration])
        d.addCallback(self.rrdtool_result, oid, duration)
        return d

    def oid_to_rrdfile(self, oid):
        base_oid = settings['connector-metro'].get('base_oid')
        oid = oid[len(base_oid)+1:]
        oid = map(int, oid.split("."))
        result = "".join(map(chr, oid))
        if "/" not in result:
            raise ValueError(_("this does not look like an RRD file path: %s"
                             % result))
        return "".join(map(chr, oid))

    def start_rrdtool(self):
        """
        Lance une instance de RRDtool dans un sous-processus
        afin de traiter les commandes.
        """
        if self._rrdtool is not None:
            return defer.succeed(self._rrdtool.transport.pid)
        self._rrdtool = RRDToolProcessProtocol()
        return self._rrdtool.start()

    def rrdtool_result(self, result, oid, duration):
        value = None
        for line in result.split("\n"):
            if not line.count(": "):
                continue
            timestamp, current_value = line.strip().split(": ")
            if current_value == "nan":
                continue
            value = current_value
        if value is None:
            raise RRDNoDataError("no value found for %s minutes"
                                 % (duration / 60))
        if value.count("e") == 1:
            # conversion de la notation exposant
            value_base, value_exp = value.split("e")
            value_base = float(value_base)
            value_exp = int(value_exp)
            value = str(value_base * pow(10, value_exp))
        return value



def main():
    SNMPtoRRDTool()
    reactor.run()


if __name__ == "__main__":
    main()

