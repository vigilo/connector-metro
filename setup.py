#!/usr/bin/env python
# vim: set fileencoding=utf-8 sw=4 ts=4 et :
from setuptools import setup

setup(name='vigilo-connector-metro',
        version='0.1',
        author='Thomas BURGUIERE',
        author_email='thomas.burguiere@c-s.fr',
        url='http://www.projet-vigilo.org/',
        description='vigilo metrology connector component',
        license='http://www.gnu.org/licenses/gpl-2.0.html',
        long_description='The vigilo metrology connector component is a connector between:\n'
        +'   - XMPP/PubSub BUS of message\n'
        +'   - RRDtool\n',
        install_requires=[
            # dashes become underscores
            # order is important (wokkel before Twisted)
            'coverage',
            'nose',
            'pylint',
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
            'vigilo.connector-metro',
            ],
        entry_points={
            'console_scripts': [
                'connector = vigilo.connector-metro.main:daemonize',
                ],
            },
        package_dir={'': 'src'},
        )

