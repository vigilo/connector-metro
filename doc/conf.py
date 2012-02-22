# -*- coding: utf-8 -*-

name = u'connector-metro'

project = u'Vigilo %s' % name

pdf_documents = [
        ('admin', "admin-%s" % name, "Connector-metro : Guide d'administration", u'Vigilo'),
]

latex_documents = [
        ('admin', 'admin-%s.tex' % name, u"Connector-metro : Guide d'administration",
         'AA100004-2/ADM00001', 'vigilo'),
]

execfile("../buildenv/doc/conf.py")
