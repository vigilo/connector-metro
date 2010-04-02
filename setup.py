#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
import os
from setuptools import setup

sysconfdir = os.getenv("SYSCONFDIR", "/etc")
localstatedir = os.getenv("LOCALSTATEDIR", "/var")

tests_require = [
    'coverage',
    'nose',
    'pylint',
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
        version='2.0.0',
        author='Vigilo Team',
        author_email='contact@projet-vigilo.org',
        url='http://www.projet-vigilo.org/',
        description='vigilo metrology connector component',
        license='http://www.gnu.org/licenses/gpl-2.0.html',
        long_description='The vigilo metrology connector component is a connector between:\n'
        +'   - XMPP/PubSub BUS of message\n'
        +'   - RRDtool\n',
        install_requires=[
            # dashes become underscores
            # order is important (wokkel before Twisted)
            'setuptools',
            'vigilo-common',
            'vigilo-connector',
            #'rrdtool',
            ],
        namespace_packages = [
            'vigilo',
            ],
        packages=[
            'vigilo',
            'vigilo.connector_metro',
            ],
        entry_points={
            'console_scripts': [
                'vigilo-connector-metro = vigilo.connector_metro.main:main',
                ],
            },
        extras_require={
            'tests': tests_require,
        },
        package_dir={'': 'src'},
        data_files=[
                    (os.path.join(sysconfdir, "vigilo/connector-metro"),
                        ["settings.ini", "connector-metro.conf.py.example"]),
                    (os.path.join(localstatedir, "lib/vigilo/connector-metro"), []),
                    (os.path.join(localstatedir, "lib/vigilo/rrd"), []),
                    (os.path.join(localstatedir, "run/vigilo-connector-metro"), []),
                   ] + install_i18n("i18n", "/usr/share/locale"),
        )

