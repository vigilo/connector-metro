**********************
Guide d'administration
**********************


Installation
============

Pré-requis logiciels
--------------------
Afin de pouvoir faire fonctionner le connecteur de métrologie, l'installation
préalable des logiciels suivants est requise :

* python (>= 2.5), sur la machine où le connecteur est installé
* ejabberd (>= 2.1), éventuellement sur une machine distante
* rrdtool (>= 1.3), sur la machine où le connecteur est installé


.. Installation du RPM
.. include:: ../buildenv/doc/package.rst

.. Compte sur le bus et fichier de configuration
.. include:: ../../connector/doc/admin-conf-1.rst

.. Lister ici les sections spécifiques au connecteur

connector-metro
    Contient les options spécifiques au connecteur metro.

.. include:: ../../connector/doc/admin-conf-2.rst

.. Documenter ici les sections spécifiques au connecteur

Configuration spécifique au connecteur de métrologie
----------------------------------------------------
Ce chapitre décrit les options de configuration spécifiques au connecteur de
métrologie. Ces options sont situées dans la section ``[connector-metro]`` du
fichier de configuration (dans ``/etc/vigilo/connector-metro/settings.ini``).

Emplacement du fichier de configuration auto-généré
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Le connecteur de métrologie utilise un fichier de configuration auto-généré
(par VigiConf) afin de connaître la liste des équipements du parc dont il a la
responsabilité pour le stockage des données de métrologie.

L'option « config » permet de spécifier l'emplacement de ce fichier de
configuration auto-généré. En règle générale, il s'agira de
``/etc/vigilo/connector-metro/connector-metro.conf.py``.

Dossier de stockage des fichiers RRD
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option « rrd_base_dir » donne le nom du dossier racine sous lequel les
données de métrologie seront enregistrées.

Le module connector-metro crée automatiquement un dossier au nom de l'hôte la
première fois qu'il reçoit une mesure de métrologie portant sur cet hôte. À
l'intérieur de ce dossier, un fichier « .rrd » est créé pour chaque indicateur
de métrologie disponible sur cet hôte ou sur l'un de ses services.

Emplacement de l'outil « rrdtool »
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option « rrd_bin » donne l'emplacement de l'outil « rrdtool » sur le système.
Une valeur adéquate est « /usr/bin/rrdtool » car il s'agit de l'emplacement par
défaut de cet outil sur la plupart des distributions Linux.


.. Administration du service
.. include:: ../buildenv/doc/service.rst


Annexes
=======

.. include:: ../../connector/doc/glossaire.rst


.. vim: set tw=79 :
