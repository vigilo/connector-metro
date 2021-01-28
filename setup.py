#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2006-2021 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import os, sys
from setuptools import setup, find_packages

setup_requires = ['vigilo-common'] if not os.environ.get('CI') else []

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
        version='5.2.0',
        author='Vigilo Team',
        author_email='contact.vigilo@csgroup.eu',
        url='https://www.vigilo-nms.com/',
        description="Vigilo Metrology connector",
        license='http://www.gnu.org/licenses/gpl-2.0.html',
        long_description="Store performance data from the Vigilo "
                         "message bus in RRD files.",
        zip_safe=False, # pour pouvoir écrire le dropin.cache de twisted
        setup_requires=setup_requires,
        install_requires=[
            'setuptools',
            'vigilo-common',
            'vigilo-connector',
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
        test_suite='nose.collector',
        vigilo_build_vars={
            'sysconfdir': {
                'default': '/etc',
                'description': "installation directory for configuration files",
            },
            'localstatedir': {
                'default': '/var',
                'description': "local state directory",
            },
        },
        data_files=[
            (os.path.join("@sysconfdir@", "vigilo", "connector-metro"), ["settings.ini.in"]),
            (os.path.join("@localstatedir@", "lib", "vigilo", "connector-metro"), []),
            (os.path.join("@localstatedir@", "log", "vigilo", "connector-metro"), []),
            (os.path.join("@localstatedir@", "lib", "vigilo", "rrd"), []),
           ] + install_i18n("i18n", os.path.join(sys.prefix, 'share', 'locale')),
        )

