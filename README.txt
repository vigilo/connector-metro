Connector Metro
===============

Connector Metro est le composant de Vigilo_ qui réceptionne les messages de
performance transitant sur le bus pour les stocker dans des fichiers RRDtool.

Pour les détails du fonctionnement du Connector Metro, se reporter à la
`documentation officielle`_.


Dépendances
-----------
Vigilo nécessite une version de Python supérieure ou égale à 2.5. Le chemin de
l'exécutable python peut être passé en paramètre du ``make install`` de la
façon suivante::

    make install PYTHON=/usr/bin/python2.6

Le Connector Metro a besoin de RRDtool_ et des modules Python suivants :

- setuptools (ou distribute)
- vigilo-common
- vigilo-connector


Installation
------------
L'installation se fait par la commande ``make install`` (à exécuter en
``root``).


License
-------
Connector Metro est sous licence `GPL v2`_.


.. _documentation officielle: Vigilo_
.. _Vigilo: https://www.vigilo-nms.com
.. _RRDtool: http://oss.oetiker.ch/rrdtool
.. _GPL v2: http://www.gnu.org/licenses/gpl-2.0.html

.. vim: set syntax=rst fileencoding=utf-8 tw=78 :
