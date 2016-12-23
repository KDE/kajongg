#!/usr/bin/setenv python3

# Copyright (c) 2007, Simon Edwards <simon@simonzone.com>
# Copyright (c) 2014, Raphael Kubo da Costa <rakuco@FreeBSD.org>
# Copyright (c) 2016, Wolfgang Rohdewald <wolfgang@rohdewald.de>
# Redistribution and use is allowed according to the terms of the BSD license.
# For details see the accompanying COPYING-CMAKE-SCRIPTS file.

import PyQt5.QtCore
import os
import sys

def get_default_sip_dir():
    # This is based on QScintilla's configure.py, and only works for the
    # default case where installation paths have not been changed in PyQt's
    # configuration process.
    if sys.platform == 'win32':
        pyqt_sip_dir = os.path.join(sys.prefix, 'sip', 'PyQt5')
    else:
        pyqt_sip_dir = os.path.join(sys.prefix, 'share', 'sip', 'PyQt5')
    return pyqt_sip_dir

def get_qt5_tag(sip_flags):
    in_t = False
    for item in sip_flags.split(' '):
        if item == '-t':
            in_t = True
        elif in_t:
            if item.startswith('Qt_5'):
                return item
        else:
            in_t = False
    raise ValueError('Cannot find Qt\'s tag in PyQt5\'s SIP flags.')

if __name__ == '__main__':
    try:
        import PyQt5.pyqtconfig
        pyqtcfg = PyQt5.pyqtconfig.Configuration()
        sip_dir = pyqtcfg.pyqt_sip_dir
        sip_flags = pyqtcfg.pyqt_sip_flags
    except ImportError:
        # PyQt5 >= 4.10.0 was built with configure-ng.py instead of
        # configure.py, so pyqtconfig.py is not installed.
        sip_dir = get_default_sip_dir()
        sip_flags = PyQt5.QtCore.PYQT_CONFIGURATION['sip_flags']

    print('pyqt_version:%06.x' % PyQt5.QtCore.PYQT_VERSION)
    print('pyqt_version_str:%s' % PyQt5.QtCore.PYQT_VERSION_STR)
    print('pyqt_version_tag:%s' % get_qt5_tag(sip_flags))
    print('pyqt_sip_dir:%s' % sip_dir)
    print('pyqt_sip_flags:%s' % sip_flags)
