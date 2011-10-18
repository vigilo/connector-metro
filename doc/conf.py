# -*- coding: utf-8 -*-

project = u'Vigilo connector-metro'

pdf_documents = [
        ('admin', "admin-connector-metro", "Connector-metro : Guide d'administration", u'Vigilo'),
]

latex_documents = [
        ('admin', 'admin-connector-metro.tex', u"Connector-metro : Guide d'administration",
         'AA100004-2/ADM00001', 'vigilo'),
]

execfile("../buildenv/doc/conf.py")
