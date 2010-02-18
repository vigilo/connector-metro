#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
from setuptools import setup

tests_require = [
    'coverage',
    'nose',
    'pylint',
]

setup(name='vigilo-connector-metro',
        version='0.1',
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
            'vigilo-pubsub',
            'vigilo-connector',
            'wokkel',
            'Twisted',
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
                'connector-metro = vigilo.connector_metro.main:main',
                ],
            },
        extras_require={
            'tests': tests_require,
        },
        package_dir={'': 'src'},
        )

