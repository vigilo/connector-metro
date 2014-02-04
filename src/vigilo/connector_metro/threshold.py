# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2014 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce module contient une bibliothèque de fonctions de tests de supervision
utilisant des seuils.
Il s'agit d'un port d'une partie du code du collector.
"""

import time

from zope.interface import implements
from twisted.internet.interfaces import IPushProducer

from vigilo.connector_metro.exceptions import MissingConfigurationData



class ThresholdChecker(object):
    """
    Reçoit des données de métrologie (performances) depuis le bus
    et les transmet à RRDtool pour générer des base de données RRD.
    """

    implements(IPushProducer)
    get_current_time = time.time


    def __init__(self, rrdtool, confdb):
        """
        Instancie un connecteur du bus vers RRDtool pour le stockage des
        données de performance dans les fichiers RRD.

        @param confdb: instance de la base de configuration en provenance de
            VigiConf
        @type  confdb: C{vigilo.connector_metro.confdb.MetroConfDB}
        """
        self.rrdtool = rrdtool
        self.confdb = confdb
        self.consumer = None # BusSender
        self._paused = True
        # Tests unitaires
        self._check_thresholds_synchronously = False


    def pauseProducing(self):
        self._paused = True

    def resumeProducing(self):
        self._paused = False


    def hasThreshold(self, perf):
        d = self.confdb.has_threshold(perf["host"], perf["datasource"])
        def extend_has_th(result, perf):
            perf["has_thresholds"] = result
            return perf
        d.addCallback(extend_has_th, perf)
        return d


    def checkMessage(self, perf, sync=False):
        if (self._paused or self.consumer is None
                or not self.consumer.isConnected()):
            # si en pause ou non connecté, on ne teste pas (info éphémère)
            return
        ds = self.confdb.get_datasource(perf["host"], perf["datasource"],
                                        cache=True)

        def get_last_value(ds, perf):
            last = self.rrdtool.getLastValue(ds, perf)
            last.addCallback(self._compare_thresholds, ds)
            return last
        def eb(f):
            f.trap(MissingConfigurationData)
            return None
        ds.addCallback(get_last_value, perf)
        ds.addErrback(eb)

        if self._check_thresholds_synchronously:
            return ds


    def _compare_thresholds(self, last, ds):
        message = {
            'type': "nagios",
            'routing_key': ds['ventilation'],
            'timestamp': self.get_current_time(),
            'host': ds['hostname'],
            'cmdname': "PROCESS_SERVICE_CHECK_RESULT",
        }

        # La réponse de rrdtool est de la forme " DS\n\ntimestamp: value\n"
        # en cas de succès et "" en cas d'erreur.
        # On s'arrange pour récupérer uniquement la valeur.
        if last is None:
            return

        last *= float(ds['factor'])

        # Si la dernière valeur est entière,
        # on la représente comme telle.
        if int(last) == last:
            last = int(last)

        try:
            if is_out_of_bounds(last, ds['critical_threshold']):
                status = (2, 'CRITICAL: %s' % last)
            elif is_out_of_bounds(last, ds['warning_threshold']):
                status = (1, 'WARNING: %s' % last)
            else:
                status = (0, 'OK: %s' % last)
        except ValueError, e:
            # Le seuil configuré est invalide.
            status = (3, 'UNKNOWN: Invalid threshold configuration (%s)' % e)

        message["value"] = ";".join((ds['hostname'], ds['nagiosname'],
                                     str(status[0]), status[1]))

        return self.consumer.write(message)



def is_out_of_bounds(value, threshold):
    """
    Teste si une valeur se situe hors d'une plage autorisée (seuils),
    défini selon le format de Nagios décrit ici:
    http://nagiosplug.sourceforge.net/developer-guidelines.html#THRESHOLDFORMAT

    @param value: Valeur à tester.
    @type value: C{float}
    @param threshold: Plage autorisée (seuils) au format Nagios.
    @type threshold: C{str}
    @return: Return True si la valeur se trouve hors de la plage autorisée
        ou False si elle se trouve dans la plage autorisée.
    @raise ValueError: La description de la plage autorisée est invalide.
    """
    # Adapté du code du Collector (base.pm:isOutOfBounds)
    # Si des changements sont apportés, il faut aussi les répercuter
    # dans vigilo-nagios-plugins-enterprise/check_nagiostats_vigilo.
    inside = threshold.startswith('@')
    if inside:
        threshold = threshold[1:]
    if not threshold:
        threshold = ":"

    if ":" not in threshold:
        threshold = float(threshold)
        if inside:
            return value >= 0 and value <= threshold
        return value < 0 or value > threshold

    if threshold == ":":
        return inside

    low, up = threshold.split(':', 2)
    if low == '~' or not low:
        up = float(up)
        if inside:
            return (value <= up)
        else:
            return (value > up)

    if not up:
        low = float(low)
        if inside:
            return (value >= low)
        else:
            return (value < low)

    low = float(low)
    up = float(up)
    if low > up:
        raise ValueError('Invalid threshold')

    if inside:
        return (value >= low and value <= up)
    else:
        return (value < low or value > up)

