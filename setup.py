#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import os, sys
from setuptools import setup, find_packages

sysconfdir = os.getenv("SYSCONFDIR", "/etc")
localstatedir = os.getenv("LOCALSTATEDIR", "/var")

tests_require = [
    'coverage',
    'nose',
    'pylint',
    'mock',
]

def install_i18n(i18ndir, destdir):
    data_files = []
    langs = []
    for f in os.listdir(i18ndir):
        if os.path.isdir(os.path.join(i18ndir, f)) and not f.startswith("."):
            langs.append(f)
    for lang in langs:
        for f in os.listdir(os.path.join(i18ndir, lang, "LC_MESSAGES")):
            if f.endswith(".mo"):
                data_files.append(
                        (os.path.join(destdir, lang, "LC_MESSAGES"),
                         [os.path.join(i18ndir, lang, "LC_MESSAGES", f)])
                )
    return data_files

setup(name='vigilo-connector-metro',
        version='2.0.8',
        author='Vigilo Team',
        author_email='contact@projet-vigilo.org',
        url='http://www.projet-vigilo.org/',
        description="Vigilo Metrology connector",
        license='http://www.gnu.org/licenses/gpl-2.0.html',
        long_description="Gateway from the Vigilo message bus (XMPP) "
                         "to RRD files.",
        zip_safe=False, # pour pouvoir écrire le dropin.cache de twisted
        install_requires=[
            'setuptools',
            'vigilo-common',
            'vigilo-connector',
            'lxml',
            ],
        namespace_packages = [
            'vigilo',
            ],
        packages=find_packages("src")+["twisted"],
        package_data={
            'twisted': ['plugins/vigilo_metro.py'],
            'vigilo.connector_metro.test': ["connector-metro.db"],
        },
        message_extractors={
            'src': [
                ('**.py', 'python', None),
            ],
        },
        extras_require={
            'tests': tests_require,
        },
        entry_points={
            'console_scripts': [
                'vigilo-connector-metro = twisted.scripts.twistd:run',
            ],
        },
        package_dir={'': 'src'},
        data_files=[
                    (os.path.join(sysconfdir, "vigilo/connector-metro"),
                        ["settings.ini"]),
                    (os.path.join(localstatedir, "lib/vigilo/connector-metro"), []),
                    (os.path.join(localstatedir, "lib/vigilo/rrd"), []),
                    (os.path.join(localstatedir, "run/vigilo-connector-metro"), []),
                    (os.path.join(localstatedir, "run/vigilo-rrdcached"), []),
                   ] + install_i18n("i18n", os.path.join(sys.prefix, 'share', 'locale')),
        )

