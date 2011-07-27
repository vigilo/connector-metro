# -*- coding: utf-8 -*-
# vim: set et sw=4 ts=4 ai:
# pylint: disable-msg=R0904,C0111,W0613,W0212
# Copyright (C) 2006-2011 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>

import unittest
from vigilo.connector_metro import threshold

class ThresholdTest(unittest.TestCase):
    def test_inside_range(self):
        """
        Seuils tels que les valeurs sont à l'intérieur de l'intervalle.
        """
        data = {
            '10': [0, 10],
            '10:': [10, float("inf")],
            '~:10': [float("-inf"), 0, 10],
            '10:20': [10, 15, 20],
            '@10:20': [float("-inf"), 0, 9.9, 20.1, float("inf")],
        }
        for thresh, values in data.iteritems():
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                self.assertFalse(
                    threshold.is_out_of_bounds(value, thresh),
                    "Could not assert %r is inside the range defined by %r" % \
                        (value, thresh)
                )

    def test_outside_range(self):
        """
        Seuils tels que les valeurs sont à l'extérieur de l'intervalle.
        """
        data = {
            '10': [-0.1, 10.1],
            '10:': [0, 9.99],
            '~:10': [10.1, float("inf")],
            '10:20': [float("-inf"), 0, 9.99, 20.1, float("inf")],
            '@10:20': [10, 15, 20],
        }
        for thresh, values in data.iteritems():
            if not isinstance(values, (list, tuple)):
                values = [values]
            for value in values:
                self.assertTrue(
                    threshold.is_out_of_bounds(value, thresh),
                    "Could not assert %r is outside the range defined by %r" % \
                        (value, thresh)
                )

    def test_invalid_range(self):
        """Seuil non valide."""
        self.assertRaises(ValueError, threshold.is_out_of_bounds, 1, '4:2')

