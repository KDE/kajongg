"""

Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0




This is to be executed on windows.
The directory 'share' must already be filled.
That can be done with winprep.py which should run
on linux in the src directory with Kajongg fully installed.

Usage: see ../README.windows
"""

# pylint: disable=wrong-import-order, wrong-import-position, import-error

from typing import List

# ==== adapt this part =====
AUTHOR = "Wolfgang Rohdewald"
EMAIL = "wolfgang@rohdewald.de"
LICENSE = 'GNU General Public License v2'
URL = "https://apps.kde.org/kajongg"
try:
    from appversion import VERSION  # type:ignore[import]
except ImportError:
    VERSION = "Unknown"
# ==========================

import os
import sys
import msilib  # pylint:disable=deprecated-module
from shutil import rmtree

from cx_Freeze import setup, Executable  # type:ignore[import]

# pylint: disable=invalid-name

if os.path.exists('build'):
    rmtree('build')

includes = [
    "zope.interface",
    "twisted.internet",
    "twisted.internet.protocol",
    "pkg_resources"]
packages : List[str] = []
namespace_packages = ["zope"]
include_files = ('share', os.path.join(sys.base_prefix, 'DLLs', 'sqlite3.dll'))

excludes = ['tcl', 'tk', 'ttk', 'tkinter', 'Tkconstants', 'Tkinter']
# strangely, excluding modules does not get rid of warnings about missing
# modules

build_exe_options = {
    "packages": packages, "excludes": excludes, "includes": includes,
    "include_files": include_files,
    "namespace_packages": namespace_packages, 'silent': False}

kajExe = Executable('kajongg.py', icon='kajongg.ico', base='Win32GUI',
                    shortcutName='kajongg', shortcutDir='ProgramMenuFolder')
kajServer = Executable('kajonggserver.py', icon='kajongg.ico')
executables = [kajExe, kajServer]


from cx_Freeze import windist


class bdist_msi(windist.bdist_msi):

    """we add an icon for the uninstaller"""

    def productcode(self) ->str:
        """get our productcode"""
        view = self.db.OpenView(
            "SELECT Value FROM Property WHERE Property = 'ProductCode'")
        view.Execute(None)
        record = view.Fetch()
        result = record.GetString(1)
        view.Close()
        return result

    def add_config(self, fullname:str) ->None:
        """add the uninstaller icon"""
        windist.bdist_msi.add_config(self, fullname)
        msilib.add_data(self.db, "Registry", [("DisplayIcon",  # type:ignore[attr-defined]
                                               -1,  # Root
                                               r"Software\Microsoft\Windows\CurrentVersion\Uninstall\%s" %
                                               self.productcode(),  # Key
                                               "DisplayIcon",  # Name
                                               r"[icons]kajongg.ico",  # Value
                                               "TARGETDIR")])  # default Component

setup(
    cmdclass={'bdist_msi': bdist_msi},  # define custom build class
    name='kajongg',
    version=VERSION,
    description='The classical game of Mah Jongg',
    long_description="This is the classical Mah Jongg for four players. "
    "If you are looking for the Mah Jongg solitaire please use the "
    "application kmahjongg.",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    download_url='https://www.linux-apps.com/p/1109453/',
    options={"build_exe": build_exe_options},
    executables=executables,
    license=LICENSE)
