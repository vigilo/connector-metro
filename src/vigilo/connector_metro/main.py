# vim: set fileencoding=utf-8 sw=4 ts=4 et :
""" Metrology connector Pubsub client. """
from __future__ import with_statement
import sys

from twisted.application import app, service
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID

from vigilo.common.gettext import translate
from vigilo.connector import client
_ = translate(__name__)

class ConnectorServiceMaker(object):
    """
    Creates a service that wraps everything the connector needs.
    """

    #implements(service.IServiceMaker, IPlugin)

    def makeService(self):
        """ the service that wraps everything the connector needs. """ 
        from vigilo.connector_metro.nodetorrdtool import NodeToRRDtoolForwarder
        from vigilo.pubsub.checknode import VerificationNode
        from vigilo.common.conf import settings
        settings.load_module(__name__)
        from vigilo.common.logging import get_logger
        import os
        LOGGER = get_logger(__name__)

        try:
            conf_ = settings['connector-metro']['config']
        except KeyError:
            LOGGER.error(_("Please set the path to the configuration "
                "file generated by Vigiconf in the settings.ini."))
            sys.exit(1)

        try:
            require_tls = settings['bus'].as_bool('require_tls')
        except KeyError:
            require_tls = False

        xmpp_client = client.XMPPClient(
                JID(settings['bus']['jid']),
                settings['bus']['password'],
                settings['bus']['host'],
                require_tls=require_tls)
        xmpp_client.setName('xmpp_client')

        try:
            xmpp_client.logTraffic = settings['bus'].as_bool('log_traffic')
        except KeyError:
            xmpp_client.logTraffic = False

        try:
            list_nodeOwner = settings['bus'].as_list('owned_topics')
        except KeyError:
            list_nodeOwner = []

        try:
            list_nodeSubscriber = settings['bus'].as_list('watched_topics')
        except KeyError:
            list_nodeSubscriber = []

        verifyNode = VerificationNode(list_nodeOwner, list_nodeSubscriber, 
                                      doThings=True)
        verifyNode.setHandlerParent(xmpp_client)

        try:
            message_consumer = NodeToRRDtoolForwarder(conf_)
        except OSError, e:
            LOGGER.exception(e)
            raise

        message_consumer.setHandlerParent(xmpp_client)

        root_service = service.MultiService()
        xmpp_client.setServiceParent(root_service)
        return root_service

def do_main_program():
    """ main function designed to launch the program """
    application = service.Application('Vigilo Connector for metrology data')
    conn_service = ConnectorServiceMaker().makeService()
    conn_service.setServiceParent(application)
    app.startApplication(application, False)
    reactor.run()
    return 0

def main():
    """Lancement avec Twistd"""
    import os, sys
    tac_file = os.path.join(os.path.dirname(__file__), "twisted_service.py")
    sys.argv[1:1] = ["-y", tac_file]
    from twisted.scripts.twistd import run
    run()

if __name__ == '__main__':
    sys.exit(main())

