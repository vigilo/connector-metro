# vim: set fileencoding=utf-8 sw=4 ts=4 et :
""" Metrology connector Pubsub client. """
from __future__ import absolute_import, with_statement

from twisted.application import app, service
from twisted.internet import reactor
from twisted.words.protocols.jabber.jid import JID


from wokkel import client
from vigilo.common.gettext import translate
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
        from vigilo.common.logging import get_logger
        import os
        LOGGER = get_logger(__name__)

        xmpp_client = client.XMPPClient(
                JID(settings['VIGILO_CONNECTOR_JID']),
                settings['VIGILO_CONNECTOR_PASS'],
                settings['VIGILO_CONNECTOR_XMPP_SERVER_HOST'])
        xmpp_client.logTraffic = True
        xmpp_client.setName('xmpp_client')

        list_nodeOwner = settings.get('VIGILO_CONNECTOR_TOPIC_OWNER', [])
        list_nodeSubscriber = settings.get('VIGILO_CONNECTOR_TOPIC', [])
        verifyNode = VerificationNode(list_nodeOwner, list_nodeSubscriber, 
                                      doThings=True)
        verifyNode.setHandlerParent(xmpp_client)

        bkpfile = settings.get('VIGILO_MESSAGE_BACKUP_FILE', ":memory:")

        i = bkpfile
        if i != ":memory:" and i is not None:
            if not os.access(os.path.dirname(i), os.F_OK):
                msg = _("Directory not found: '%(dir)s'") % \
                        {'dir': os.path.dirname(i)}
                LOGGER.error(msg)
                raise OSError(msg)
            if not os.access(os.path.dirname(i), os.R_OK):
                msg = _("Directory not readable: '%(dir)s'") % \
                        {'dir': os.path.dirname(i)}
                LOGGER.error(msg)
                raise OSError(msg)
            if not os.access(os.path.dirname(i), os.W_OK):
                msg = _("Directory not writable: '%(dir)s'") % \
                        {'dir': os.path.dirname(i)}
                LOGGER.error(msg)
                raise OSError(msg)
            if not os.access(os.path.dirname(i), os.X_OK):
                msg = _("Directory not executable: '%(dir)s'") % \
                        {'dir': os.path.dirname(i)}
                LOGGER.error(msg)
                raise OSError(msg)

        conf_ = settings.get('VIGILO_METRO_CONF', None)
        message_consumer = NodeToRRDtoolForwarder(conf_)
        message_consumer.setHandlerParent(xmpp_client)

        root_service = service.MultiService()
        xmpp_client.setServiceParent(root_service)
        return root_service

def do_main_programm():
    """ main function designed to launch the program """
    application = service.Application('Twisted PubSub component')
    conn_service = ConnectorServiceMaker().makeService()
    conn_service.setServiceParent(application)
    app.startApplication(application, False)
    reactor.run()

def main():
    """ main function designed to launch the program """

    from vigilo.common.daemonize import daemonize
    context = daemonize()
    with context:
        do_main_programm()


if __name__ == '__main__':
    main()

