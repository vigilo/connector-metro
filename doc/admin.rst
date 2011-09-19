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
le bus XMPP pour le composant. Si plusieurs instances doivent être lancées sur
la même machine, chaque instance doit utiliser un JID différent.

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

Ce fichier est composé de différentes sections permettant de paramétrer des
aspects divers du module, chacune de ces sections peut contenir un ensemble de
valeurs sous la forme ``clé = valeur``. Les lignes commençant par « ; » ou
« # » sont des commentaires et sont par conséquent ignorées.

Le format de ce fichier peut donc être résumé dans l'extrait suivant::

    # Ceci est un commentaire
    ; Ceci est également un commentaire
    [section1]
    option1=valeur1
    option2=valeur2
    ...
    
    [section2]
    option1=val1
    ...

Les sections utilisées par le connecteur de métrologie et leur rôle sont
recensées dans le tableau suivant.

+-------------------+---------------------------------------------------------------------------+
| Section           | Description                                                               |
+===================+===========================================================================+
| bus               | Contient les options relatives à la configuration de l'accès au bus XMPP. |
+-------------------+---------------------------------------------------------------------------+
| connector         | Contient les options de configuration génériques d'un connecteur de       |
|                   | Vigilo.                                                                   |
+-------------------+---------------------------------------------------------------------------+
| connector-metro   | Contient les options spécifiques au connecteur metro.                     |
+-------------------+---------------------------------------------------------------------------+
| loggers           | Contient la configuration du mécanisme de journalisation des événements   |
+-------------------+ (voir chapitre correspondant).                                            |
| handlers          |                                                                           |
+-------------------+ « * » correspond au nom d'un logger/handler/formatter défini dans la      |
| formatters        | section loggers, handlers ou formatters (respectivement).                 |
+-------------------+                                                                           |
| logger_*          |                                                                           |
+-------------------+                                                                           |
| handler_*         |                                                                           |
+-------------------+                                                                           |
| formatter_*       |                                                                           |
+-------------------+---------------------------------------------------------------------------+


Configuration de la connexion au serveur XMPP (Jabber)
------------------------------------------------------
Le composant connector-metro utilise un bus de communication basé sur le
protocole XMPP pour communiquer avec les autres connecteurs de Vigilo.

Ce chapitre décrit les différentes options de configuration se rapportant à la
connexion à ce bus de communication, situées dans la section ``[bus]`` du fichier
de configuration.

Trace des messages échangés avec le bus
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option « log_traffic » est un booléen permettant d'afficher tous les messages
échangés avec le bus XMPP lorsqu'il est positionné à « True ». Cette option
génère un volume d'événements de journalisation très important et n'est donc
pas conseillée en production.

Adresse du bus
^^^^^^^^^^^^^^
L'option « host » permet d'indiquer le nom ou l'adresse IP de l'hôte sur lequel
le bus XMPP fonctionne.

Nom du service de publication sur le bus
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Le connecteur utilise le protocole de publication de messages décrit dans le
document XEP-0060 pour échanger des informations avec les autres connecteurs de
Vigilo.

Ce protocole nécessite de spécifier le nom du service de publication utilisé
pour l'échange de messages sur le bus XMPP. Ce nom de service est généralement
de la forme ``pubsub.<hôte>`` où ``<hôte>`` correspond au nom de l'hôte sur
lequel ejabberd fonctionne (indiqué par l'option « host »).

Identifiant Jabber
^^^^^^^^^^^^^^^^^^
Chaque connecteur de Vigilo est associé à un compte Jabber différent et possède
donc son propre JID. L'option « jid » permet d'indiquer le JID à utiliser pour
se connecter au serveur Jabber.

Mot de passe du compte Jabber
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option « password » permet de spécifier le mot de passe associé au compte
Jabber indiqué dans l'option « jid ».

Politique de gestion des connexions sécurisées
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Les connecteurs ont la possibilité de spécifier la politique de sécurité à
appliquer pour les connexions avec le serveurs XMPP. Il est possible de forcer
l'utilisation d'une connexion chiffrée entre le connecteur et le bus en
positionnant l'option « require_tls » à « True ». Une erreur sera levée si le
connecteur ne parvient pas à établir une connexion chiffrée.

Lorsque cette option est positionnée à une autre valeur, le connecteur tente
malgré tout d'établir une connexion chiffrée. Si cela est impossible, le
connecteur ne déclenche pas d'erreur mais bascule automatiquement vers
l'utilisation d'une connexion en clair au bus XMPP.

Politique de gestion de la compression des données
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Les connecteurs ont la possibilité de spécifier si les échanges XMPP seront
compressés. Il est possible de forcer l'utilisation de la compression entre le
connecteur et le bus en positionnant l'option « require_compression » à
« True ». Une erreur est levée si le connecteur ne parvient pas à mettre en
place la compression lors des premiers échanges.

Lorsque les deux options « require_tls » et « require_compression » sont à
« True », un message d'avertissement est inscrit dans les fichiers de log, et
le connecteur utilisera le chiffrement.

Liste des nœuds XMPP auxquels le connecteur est abonné
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
L'option « subscriptions » contient la liste des nœuds XMPP auxquels le
connecteur est abonné (séparés par des virgules), c'est-à-dire les nœuds pour
lesquels il recevra des messages lorsqu'un autre composant de Vigilo publie des
données. La valeur proposée par défaut lors de l'installation du connecteur
convient généralement à tous les types d'usages.

La valeur spéciale « , » (une virgule seule) permet d'indiquer que le
connecteur n'est abonné à aucun nœud (par exemple, dans le cas où le connecteur
se contente d'écrire des informations sur le bus, sans jamais en recevoir).

Nœud d'envoi des informations sur le statut du connecteur
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Les connecteurs de Vigilo sont capables de s'auto-superviser, c'est-à-dire que
des alertes peuvent être émises par Vigilo concernant ses propres connecteurs
lorsque le fonctionnement de ceux-ci est perturbé ou en défaut.

Ce mécanisme est rendu possible grâce à des signaux de vie émis par les
connecteurs à intervalle régulier. Chaque signal de vie correspond à un message
de type « state ».

L'option « status_node » permet de choisir le nœud XMPP vers lequel les
messages de survie du connecteur sont envoyés. Dans le cas où cette option ne
serait pas renseignée, les nœuds de publication sont utilisés pour déterminer
le nœud de destination des messages. Si aucun nœud de publication n'est trouvé
pour l'envoi des messages de vie, un message d'erreur est enregistré dans les
journaux d'événements.


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


Configuration des journaux
--------------------------
Le module connector-metro est capable de transmettre un certain nombre
d'informations au cours de son fonctionnement à un mécanisme de journalisation
des événements (par exemple, des journaux systèmes, une trace dans un fichier,
un enregistrement des événements en base de données, etc.).

Le document Vigilo - Journaux d'événements décrit spécifiquement la
configuration de la journalisation des événements au sein de toutes les
applications de Vigilo, y compris les connecteurs.



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

.. TODO
.. Annexe : Messages d’erreurs/d’alerte/d’informations
.. ---------------------------------------------------
.. 
.. Ce chapitre recense les messages d'erreurs les plus courants que vous êtes
.. susceptibles de rencontrer, ainsi que la méthode de résolution de ces
.. problèmes.
.. 

Annexe : Glossaire - Terminologie
---------------------------------

Ce chapitre recense les différents termes techniques employés dans ce document
et donne une brève définition de chacun de ces termes.

XML
    eXtensible Markup Language. Langage de balisage extensible.

XMPP
    eXtensible Messaging and Presense Protocol. Protocole de messagerie
    instantanée pour l'envoi de textes courts au format XML.

RRD
    Round-Robin Database. Base de données circulaire permettant de stocker des
    données disposant d'une granularité différente.



.. vim: set tw=79 :

