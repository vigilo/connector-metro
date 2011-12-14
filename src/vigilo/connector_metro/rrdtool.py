# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Gestion d'un process RRDTool pour écrire ou lire des RRDs.

@todo: gérer un I{pool} de process RRDTool
@note: U{http://twistedmatrix.com/documents/current/core/howto/process.html}
"""

import os
import stat
import urllib

from twisted.internet import reactor, protocol, defer
from twisted.internet.error import ProcessDone, ProcessTerminated

from vigilo.common import get_rrd_path

from vigilo.common.logging import get_logger
LOGGER = get_logger(__name__, silent_load=True)

from vigilo.common.gettext import translate
_ = translate(__name__)


from vigilo.connector_metro.exceptions import CreationError
from vigilo.connector_metro.exceptions import NotInConfiguration
from vigilo.connector_metro.exceptions import MissingConfigurationData


class NoAvailableProcess(Exception):
    """
    Il n'y a plus de process rrdtool disponible, et pourtant le sémaphore a
    autorisé l'accès
    """
    pass


class RRDToolError(Exception):
    """Erreur à l'exécution de RRDTool"""
    def __init__(self, filename, message):
        Exception.__init__(self, message)
        self.filename = filename



def parse_rrdtool_response(response):
    value = None
    for line in response.split("\n"):
        if not line.count(": ") == 1:
            continue
        timestamp, current_value = line.strip().split(": ")
        if current_value == "nan":
            continue
        value = current_value
    if value is not None:
        value = float(value) # python convertit tout seul la notation exposant
    return value



class RRDToolManager(object):


    def __init__(self, rrdtool, confdb):
        self.rrdtool = rrdtool
        self.confdb = confdb


    def getFilename(self, msgdata):
        filename = get_rrd_path(msgdata["host"], msgdata["datasource"],
                        self.rrdtool.rrd_base_dir, self.rrdtool.rrd_path_mode)
        return filename

    def getOldFilename(self, msgdata):
        old_filename = os.path.join(
            self.rrdtool.rrd_base_dir,
            msgdata["host"].encode('utf-8'),
            "%s.rrd" % urllib.quote_plus(msgdata["datasource"].encode('utf-8'))
        )
        return old_filename


    def processMessage(self, msgdata):
        """
        Traite le message et retourne msgdata pour traitements ultérieurs
        """
        if msgdata is None:
            return defer.succeed(None)
        cmd = '%(timestamp)s:%(value)s' % msgdata
        filename = self.getFilename(msgdata)
        d2 = self.rrdtool.run("update", filename, cmd,
                              no_rrdcached=msgdata["has_thresholds"])
        d2.addCallback(lambda x: msgdata)
        return d2

    def createIfNeeded(self, msgdata):
        """
        Créé le RRD si besoin, et retourne msgdata pour traitements ultérieurs
        """
        filename = self.getFilename(msgdata)
        if os.path.exists(filename):
            return defer.succeed(msgdata)
        # compatibilité
        old_filename = self.getOldFilename(msgdata)
        if os.path.isfile(old_filename):
            os.rename(old_filename, filename)
            return defer.succeed(msgdata)
        else:
            # création
            d = self._create(filename, msgdata)
            d.addCallback(lambda _x: msgdata)
            return d


    @defer.inlineCallbacks
    def _create(self, filename, msgdata):
        """
        Crée un nouveau fichier RRD avec la configuration adéquate.

        @param filename: Nom du fichier RRD à générer, le nom de l'indicateur
            doit être encodé avec urllib.quote_plus (RFC 1738).
        @type  filename: C{str}
        @param msgdata: Dictionnaire décrivant la source de données, contenant les
            clés suivantes :
             - C{host}: Nom de l'hôte.
             - C{datasource}: Nom de l'indicateur.
             - C{timestamp}: Timestamp UNIX de la mise à jour.
        @type msgdata: C{dict}
        """
        # to avoid an error just after creating the rrd file :
        # (minimum one second step)
        # the creation and updating time needs to be different.
        timestamp = int(msgdata["timestamp"]) - 10
        basedir = os.path.dirname(filename)
        self.rrdtool.makedirs(basedir)
        host = msgdata["host"]
        ds_name = msgdata["datasource"]
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
            self._fixperms(filename)

    def _fixperms(self, filename):
        """
        Fait un C{chmod 644}. Séparé pour faciliter les tests unitaires.
        """
        os.chmod(filename, # chmod 644
                 stat.S_IRUSR | stat.S_IWUSR |
                 stat.S_IRGRP | stat.S_IROTH )


    def getLastValue(self, ds, msg):
        attrs = [
            'warning_threshold',
            'critical_threshold',
            'nagiosname',
            'ventilation',
        ]
        for attr in attrs:
            if ds[attr] is None:
                return defer.fail(MissingConfigurationData(attr))
        # récupération de la dernière valeur enregistrée
        filename = self.getFilename(msg)
        d = self.rrdtool.run("fetch", filename,
                    'AVERAGE --start -%d' % (int(ds["step"]) * 2),
                    no_rrdcached=True)
        d.addCallback(parse_rrdtool_response)
        return d

    # Proxies

    def start(self):
        return self.rrdtool.start()

    def stop(self):
        return self.rrdtool.stop()

    def isStarted(self):
        return self.rrdtool.started



class RRDToolPoolManager(object):
    """
    Gère l'interaction avec RRDTool, c'est à dire avec le pool de process et
    les aspects filesystem.
    """


    def __init__(self, rrd_base_dir, rrd_path_mode, rrd_bin,
                 check_thresholds=True, rrdcached=None, pool_size=None,
                 readonly=False):
        self.rrd_base_dir = rrd_base_dir
        self.rrd_path_mode = rrd_path_mode
        self.rrd_bin = rrd_bin
        self.readonly = readonly
        self.job_count = 0
        self.started = False
        self.pool = None
        self.pool_direct = None
        self.createPools(check_thresholds, rrdcached, pool_size)


    def createPools(self, check_thresholds, rrdcached, pool_size):
        if pool_size is None:
            # POSIX seulement: http://www.boduch.ca/2009/06/python-cpus.html
            pool_size = int(os.sysconf('SC_NPROCESSORS_ONLN'))
            if pool_size > 4:
                # on limite, sinon on passe trop de temps à choisir
                pool_size = 4
        self.pool = RRDToolPool(pool_size, self.rrd_bin, rrdcached=rrdcached)
        if rrdcached and check_thresholds:
            # On créé un petit pool sans RRDcached
            self.pool_direct = RRDToolPool(1, self.rrd_bin)


    def makedirs(self, directory):
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
            self._mkdir(cur_dir)


    def _mkdir(self, directory):
        try:
            os.makedirs(directory)
            os.chmod(directory, # chmod 755
                     stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |\
                     stat.S_IRGRP | stat.S_IXGRP | \
                     stat.S_IROTH | stat.S_IXOTH)
        except OSError, e:
            LOGGER.error(_("Unable to create the directory '%s'"), e.filename)
            raise e


    def start(self):
        """
        Lance une instance de RRDtool dans un sous-processus
        """
        if self.started:
            return defer.succeed(None)
        try:
            self.ensureDirectory(self.rrd_base_dir)
            self.checkBinary()
        except OSError, e:
            return defer.fail(e)

        d = self.pool.start()
        if self.pool_direct is not None:
            d.addCallback(lambda x: self.pool_direct.start())
        def flag_started(r):
            self.started = True
        d.addCallback(flag_started)
        return d


    def stop(self):
        d = self.pool.stop()
        if self.pool_direct is not None:
            d.addCallback(lambda x: self.pool_direct.stop())
        def flag_stopped(r):
            self.started = False
        d.addCallback(flag_stopped)
        return d


    def checkBinary(self):
        if not os.path.isfile(self.rrd_bin):
            raise OSError(_('Unable to start "%(rrdtool)s". Make sure the '
                            'path is correct.') % {'rrdtool': self.rrd_bin})
        if not os.access(self.rrd_bin, os.X_OK):
            raise OSError(_('Unable to start "%(rrdtool)s". Make sure '
                            'RRDtool is installed and you have '
                            'permissions to use it.') % {
                                'rrdtool': self.rrd_bin,
                            })


    def ensureDirectory(self, directory):
        """
        Vérifier la présence et les permissions d'un dossier, et le crée si
        besoin avec ces bonnes permissions
        """
        if not os.access(directory, os.F_OK):
            if self.readonly:
                raise OSError(_("The RRD directory does not exist: %s"),
                              directory)
            self._mkdir(directory)
        if not self.readonly and not os.access(directory, os.W_OK):
            raise OSError((_("Unable to write in the directory '%(dir)s'") %
                    {'dir': directory}).encode('utf-8'))


    def run(self, command, filename, args, no_rrdcached=False):
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
        self.job_count += 1
        d = self.start() # enchaîne tout de suite si on est déjà démarré
        if no_rrdcached and self.pool_direct is not None:
            pool = self.pool_direct
        else:
            pool = self.pool
        d.addCallback(lambda x: pool.run(command, filename, args))
        return d



class RRDToolProcessProtocol(protocol.ProcessProtocol):


    def __init__(self, rrd_bin, env=None):
        self.rrd_bin = rrd_bin
        self.deferred = None
        self.deferred_start = None
        self.deferred_stop = None
        self._current_data = []
        self._keep_alive = True
        self._filename = None
        self.working = False
        if env is None:
            self.env = {}
        else:
            self.env = env


    def start(self):
        if self.transport is not None:
            return defer.succeed(self.transport.pid)
        LOGGER.debug("Starting rrdtool process in server mode")
        self.deferred_start = defer.Deferred()
        reactor.spawnProcess(self, self.rrd_bin, [self.rrd_bin, "-"],
                             env=self.env)
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
        self.working = True
        assert self.deferred is None, \
                    _("The process has not yet completed the previous job"
                     ).encode("utf8") # unicode interdit
        self.deferred = defer.Deferred()
        def state_finish(r):
            self.working = False
            self._current_data = []
            self.deferred = None
            return r
        self.deferred.addBoth(state_finish)
        self._filename = filename
        if isinstance(args, list):
            args = " ".join(args)
        complete_cmd = "%s %s %s" % (command, filename, args)
        #LOGGER.debug('Running this command: %s' % complete_cmd)
        try:
            # attention, unicode interdit
            self.transport.write("%s\n" % complete_cmd.encode("utf8"))
        except Exception, e:
            self.working = False
            return defer.fail(e)
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
                self.deferred.errback(RRDToolError(self._filename, line[7:]))
                break
            self._current_data.append(line)


    def quit(self):
        self._keep_alive = False
        self.deferred_stop = defer.Deferred()
        if self.transport is not None:
            self.transport.write("quit\n")
            self.transport.loseConnection()
            return self.deferred_stop
        else:
            return defer.succeed(None)
        #self.transport.signalProcess('TERM')


    def processEnded(self, reason):
        if isinstance(reason.value, ProcessDone):
            LOGGER.info(_('The RRDTool process exited normally'))
        elif isinstance(reason.value, ProcessTerminated):
            LOGGER.warning(_('The RRDTool process was terminated abnormally '
                             'with exit code %(rcode)s and message: %(msg)s'),
                           {"rcode": reason.value.exitCode, # peut être None
                            "msg": reason.getErrorMessage()})
        if not self._keep_alive:
            if self.deferred_stop is not None:
                self.deferred_stop.callback(None)
            return
        # respawn
        LOGGER.info(_('Restarting...'))
        self.start()



class RRDToolPool(object):
    """
    Gestionnaire de pool de processus RRDTool, interface bas-niveau
    """

    processProtocolFactory = RRDToolProcessProtocol

    def __init__(self, size, rrd_bin, rrdcached=None):
        self.size = size
        self.rrd_bin = rrd_bin
        self.rrdcached = rrdcached
        self.pool = []
        self._lock = defer.DeferredSemaphore(self.size)

    def __len__(self):
        return self.size
    def __contains__(self, elem):
        return elem in self.pool
    def __iter__(self):
        return self.pool.__iter__()

    def build(self):
        env = {}
        if self.rrdcached:
            env["RRDCACHED_ADDRESS"] = self.rrdcached
        for i in range(self.size):
            self.pool.append(self.processProtocolFactory(self.rrd_bin, env))

    def start(self):
        if not self.pool:
            self.build()
        results = []
        for rrdtool in self.pool:
            results.append(rrdtool.start())
        return defer.DeferredList(results)

    def stop(self):
        results = []
        for rrdtool in self.pool:
            results.append(rrdtool.quit())
        return defer.DeferredList(results)

    def run(self, command, filename, args):
        """
        Lance une commande par RRDTool.  Attention, le pool doit déjà avoir été
        démarré.
        """
        return self._lock.run(self._dispatch, command, filename, args)

    def _dispatch(self, command, filename, args):
        """
        Distribue les tâches sur les processus RRDtool disponibles
        """
        for index, rrdtool in enumerate(self.pool):
            if rrdtool.working:
                continue
            #LOGGER.debug("Running job %d on process %d",
            #             self.job_count, index+1)
            return rrdtool.run(command, filename, args)
        raise NoAvailableProcess()
