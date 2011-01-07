""" metrology vigilo connector """

import os
import urllib
import hashlib

from vigilo.common.conf import settings
settings.load_module(__name__)

__all__ = ("get_rrd_path", )

_DIR_HASHES = {}

def get_rrd_path(hostname, ds):
    rrd_base_dir = settings['connector-metro']['rrd_base_dir']
    rrd_path_mode = settings['connector-metro'].get('rrd_path_mode', 'flat')
    ds = urllib.quote_plus(ds)
    subpath = ""
    if rrd_path_mode == "name" and len(hostname) >= 2:
        subpath = os.path.join(hostname[0], "".join(hostname[0:2]))
    elif rrd_path_mode == "hash":
        if hostname in _DIR_HASHES:
            subpath = _DIR_HASHES[hostname]
        else:
            hash = hashlib.md5(hostname).hexdigest()
            subpath = os.path.join(hash[0], "".join(hash[0:2]))
            _DIR_HASHES[hostname] = subpath
    return os.path.join(rrd_base_dir, subpath, hostname, "%s.rrd" % ds)

