# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

"""
Ce module contient une bibliothèque de fonctions de tests de supervision
utilisant des seuils.
Il s'agit d'un port d'une partie du code du collector.
"""

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

