**********************
Guide d'administration
**********************

Ce document a pour objectif de présenter le fonctionnement du module
connector-metro aux administrateurs.


Installation
============

Pré-requis logiciels
--------------------
Afin de pouvoir faire fonctionner le connecteur de métrologie, l'installation
préalable des logiciels suivants est requise :

* python (>= 2.5), sur la machine où le connecteur est installé
* rrdtool (>= 1.3), sur la machine où le connecteur est installé
* ejabberd (>= 2.1), éventuellement sur une machine distante

Reportez-vous aux manuels de ces différents logiciels pour savoir comment
procéder à leur installation sur votre machine.

Le connecteur de métrologie requiert également la présence de plusieurs
dépendances Python. Ces dépendances seront automatiquement installées en même
temps que le paquet du connecteur.

Installation du paquet RPM
--------------------------
L'installation du connecteur se fait en installant simplement le paquet RPM
« vigilo-connector-metro ». La procédure exacte d'installation dépend du
gestionnaire de paquets utilisé. Les instructions suivantes décrivent la
procédure pour les gestionnaires de paquets RPM les plus fréquemment
rencontrés.

Installation à l'aide de urpmi::

    urpmi vigilo-connector-metro

Installation à l'aide de yum::

    yum install vigilo-connector-metro

Création du compte XMPP
-----------------------
Le connector-metro nécessite qu'un compte soit créé sur la machine hébergeant
le bus XMPP pour le composant.

Les comptes doivent être créés sur la machine qui héberge le serveur ejabberd,
à l'aide de la commande::

    $ su -c 'ejabberdctl register connector-metro localhost connector-metro' ejabberd

**Note :** si plusieurs instances du connecteur s'exécutent simultanément sur
le parc, chaque instance doit disposer de son propre compte (JID). Dans le cas
contraire, des conflits risquent de survenir qui peuvent perturber le bon
fonctionnement de la solution.



Configuration
=============

Le module connector-metro est fourni avec un fichier de configuration situé
par défaut dans ``/etc/vigilo/connector-metro/settings.ini``.

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


Administration du service
=========================

Le connecteur est fourni avec un script de démarrage standard pour Linux,
facilitant les opérations d'administration du connecteur. Ce chapitre décrit
les différentes opérations d'administration disponibles.

Démarrage
---------
Pour démarrer le module connector-metro en mode démon, lancez la commande
suivante en tant que super-utilisateur::

    service vigilo-connector-metro start

Si le service parvient à démarrer correctement, le message « OK » apparaît dans
le terminal.

Vérification de l'état du service
---------------------------------
L'état du service peut être vérifié à tout moment, grâce à la commande::

    service vigilo-connector-metro status

S'il est bien en cours d'exécution, le module connector-metro est maintenant
apte à traiter les messages issus du bus XMPP. Dans le cas contraire, analysez
les logs système consignés dans ``/var/log/syslog``.

Arrêt
-----
Pour arrêter le module connector-metro en mode démon, lancez la commande
suivante en tant que super-utilisateur::

    service vigilo-connector-metro stop



Annexes
=======

.. include:: ../../connector/doc/glossaire.rst

RRD
    Round-Robin Database. Base de données circulaire permettant de stocker des
    données disposant d'une granularité différente.


.. vim: set tw=79 :
