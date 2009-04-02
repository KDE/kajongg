#
import PyQt4.pyqtconfig

if "_pkg_config" in dir(PyQt4.pyqtconfig):
    _pkg_config = PyQt4.pyqtconfig._pkg_config
else:
    import PyQt4.pyqtconfig_nd
    _pkg_config = PyQt4.pyqtconfig_nd._pkg_config

for varname in [
        'pyqt_bin_dir',
        'pyqt_config_args',
        'pyqt_mod_dir',
        'pyqt_modules',
        'pyqt_sip_dir',
        'pyqt_sip_flags',
        'pyqt_version',
        'pyqt_version_str']:
    print("%s:%s\n" % (varname,_pkg_config[varname]))
