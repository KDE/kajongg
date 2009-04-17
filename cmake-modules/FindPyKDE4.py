# By Simon Edwards <simon@simonzone.com>
# This file is in the public domain.
import sys
import PyKDE4.pykdeconfig

if "_pkg_config" in dir(PyKDE4.pykdeconfig):
    _pkg_config = PyKDE4.pykdeconfig._pkg_config

    for varname in [
            'kde_version',
            'kde_version_extra',
            'kdebasedir',
            'kdeincdir',
            'kdelibdir',
            'libdir',
            'pykde_kde_sip_flags', 
            'pykde_mod_dir',
            'pykde_modules', 
            'pykde_sip_dir',
            'pykde_version',
            'pykde_version_str']:
        print("%s:%s\n" % (varname,_pkg_config[varname]))
else:
    sys.exit(1)