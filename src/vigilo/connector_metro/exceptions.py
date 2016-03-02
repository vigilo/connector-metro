# vim: set fileencoding=utf-8 sw=4 ts=4 et :
# Copyright (C) 2011-2016 CS-SI
# License: GNU GPL v2 <http://www.gnu.org/licenses/gpl-2.0.html>


class InvalidMessage(ValueError):
    pass


class WrongMessageType(Exception):
    pass


class CreationError(Exception):
    pass


class NotInConfiguration(KeyError):
    pass


class MissingConfigurationData(KeyError):
    pass



