#!/usr/bin/twistd -ny
# -*- coding: utf-8 -*-
# vim: set ft=python fileencoding=utf-8 sw=4 ts=4 et :
"""
A bit of glue, you can start this with twistd -ny path/to/file.py
"""

from twisted.application import service
from vigilo.connector_metro.main import ConnectorServiceMaker

application = service.Application('Vigilo Connector for metrology data')
conn_service = ConnectorServiceMaker().makeService()
conn_service.setServiceParent(application)

