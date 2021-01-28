# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2021 CS GROUP - France
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import unittest
from vigilo.connector_metro.rrdtool import parse_rrdtool_response

class RRDToolParserTestCase(unittest.TestCase):
    def test_empty(self):
        """Sortie de RRDTool: vide"""
        self.assertTrue(parse_rrdtool_response("", "localhost/ineth0.rrd") is None)

    def test_only_nan(self):
        """Sortie de RRDTool: uniquement des NaN"""
        output = "123456789: nan\n123456789: -nan\n123456789: NaN\n123456789: -NaN\n"
        self.assertTrue(parse_rrdtool_response(output, "localhost/ineth0.rrd") is None)

    def test_simple(self):
        """Sortie de RRDTool: cas simple"""
        output = "123456789: 42\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 42)

    def test_useless_data(self):
        """Les données inutiles doivent être ignorées"""
        output = "  useless data   \n123456789: 42\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 42)

    def test_exponent(self):
        """Gestion des valeurs avec exposants"""
        output = "123456789: 4.2e2\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 420.0)

    def test_choose_last(self):
        """Il faut choisir la dernière valeur"""
        output = "123456789: 41\n123456789: 42\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 42)

    def test_ignore_nan(self):
        """Les lignes avec NaN doivent être ignorées"""
        output = "123456789: 42\n123456789: nan\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 42)

    def test_ignore_not_convertible_to_float(self):
        """Les valeurs non convertibles en float doivent être ignorées"""
        output = "123456789: 42\n123456789: abc\n"
        self.assertEqual(parse_rrdtool_response(output, "localhost/ineth0.rrd"), 42)
