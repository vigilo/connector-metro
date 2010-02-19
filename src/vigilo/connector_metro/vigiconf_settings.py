# vim: set fileencoding=utf-8 sw=4 ts=4 et :
""" Chargement du fichier de configuration généré par Vigiconf. """

import re

class VigiconfSettings(object):
    """
    Un dictionnaire en lecture seule contenant 
    la configuration fournie par Vigiconf.
    
    Les noms de constantes valides s'écrivent sous la forme : FOO_BAR_BAZ2.
    """
    
    def __init__(self):
        """
        Initialisation.
        
        @ivar filename: Le fichier de configuration fourni par Vigiconf
        @type filename: C{str}
        """
        self.__dct = {}
        
    def __getitem__(self, name):
        if not re.compile('[A-Z][A-Z0-9]*(_[A-Z0-9]+)*').match(name):
            # Or maybe ValueError
            raise KeyError('Invalid name', name)
        return self.__dct[name]


    def load_configuration(self, filename):
        """
        Charge en mémoire le fichier de configuration fourni par Vigiconf.
        
        @param filename: Le chemin complet vers le fichier à charger.
        @type  filename: C{str}
        """
        settings_raw = {}
        execfile(filename, settings_raw)
        self.__dct = settings_raw

vigiconf_settings = VigiconfSettings()