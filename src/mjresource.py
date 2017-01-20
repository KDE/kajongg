# -*- coding: utf-8 -*-

"""
Authors of original libkmahjongg in C++:
    Copyright (C) 1997 Mathias Mueller <in5y158@public.uni-hamburg.de>
    Copyright (C) 2006 Mauricio Piacentini <mauricio@tabuleiro.com>

this adapted python code:
    Copyright (C) 2008-2016 Wolfgang Rohdewald <wolfgang@rohdewald.de>

Kajongg is free software you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""

import os
from qt import QStandardPaths
from log import logWarning, logException
from kde import KConfig
from mi18n import i18n

RESOURCEFORMAT = 1 # as long as backgrounds and tilesets are synchronous in their versions


class Resource:

    """Common code for backgrounds and tilesets"""

    resourceName = None # to be overridden in Tileset and Background
    configGroupName = None

    """represents a complete tileset"""
    # pylint: disable=too-many-instance-attributes

    cache = {}

    def __new__(cls, name):
        return cls.cache.get(name) or cls.cache.get(cls.__name(name)) or cls.__build(name)

    @classmethod
    def __directories(cls):
        """where to look for resources"""
        result = QStandardPaths.locateAll(
            QStandardPaths.GenericDataLocation,
            'kmahjongglib/{}s'.format(cls.resourceName), QStandardPaths.LocateDirectory)
        result.insert(0, os.path.join('share', 'kmahjongglib', '{}s'.format(cls.resourceName)))
        return (x for x in result if os.path.exists(x))

    @classmethod
    def locate(cls, which):
        """locate the file with a resource"""
        for directory in cls.__directories():
            path = os.path.join(directory, which)
            if os.path.exists(path):
                return path
        logException('cannot find kmahjongg%s %s in %s' % (cls.resourceName, which, cls.__directories()))

    @classmethod
    def loadAll(cls):
        """loads all available resources into cache"""
        resourceDirectories = cls.__directories()
        for directory in resourceDirectories:
            for name in os.listdir(directory):
                if name.endswith('.desktop'):
                    if not name.endswith('alphabet.desktop') and not name.endswith('egypt.desktop'):
                        cls(os.path.join(directory, name))

    @classmethod
    def available(cls):
        """ready for the selector dialog, default first"""
        cls.loadAll()
        return sorted(set(cls.cache.values()), key=lambda x: x.desktopFileName != 'default')

    @classmethod
    def __noTilesetFound(cls):
        """No resources found"""
        directories = '\n\n' + '\n'.join(cls.__directories())
        logException(
            i18n(
                'cannot find any %1 in the following directories, '
                'is libkmahjongg installed?', cls.resourceName) + directories) # TODO: nicht schoen

    @staticmethod
    def __name(path):
        """extract the name from path: this is the filename minus the .desktop ending"""
        return os.path.split(path)[1].replace('.desktop', '')

    @classmethod
    def __build(cls, name):
        """build a new Resource. name is either a full file path or a desktop name. None stands for 'default'."""
        result = object.__new__(cls)
        if os.path.exists(name):
            result.path = name
            result.desktopFileName = cls.__name(name)
        else:
            result.desktopFileName = name or 'default'
            result.path = cls.locate(result.desktopFileName + '.desktop')
            if not result.path:
                result.path = cls.locate('default.desktop')
                result.desktopFileName = 'default'
                if not result.path:
                    cls.__noTilesetFound()
                else:
                    logWarning(i18n('cannot find %1, using default', name))

        cls.cache[result.desktopFileName] = result
        cls.cache[result.path] = result
        return result

    def __init__(self, dummyName):
        """continue __build"""
        self.group = KConfig(self.path).group(self.configGroupName)

        self.name = self.group.readEntry("Name") or i18n("unknown name")
        self.author = self.group.readEntry("Author") or i18n("unknown author")
        self.description = self.group.readEntry(
            "Description") or i18n(
                "no description available")
        self.authorEmail = self.group.readEntry(
            "AuthorEmail") or i18n(
                "no E-Mail address available")

        # Version control
        resourceVersion = self.group.readInteger("VersionFormat", default=0)
        # Format is increased when we have incompatible changes, meaning that
        # older clients are not able to use the remaining information safely
        if resourceVersion > RESOURCEFORMAT:
            logException('version file / program: %d/%d' % (resourceVersion, RESOURCEFORMAT))

    def __str__(self):
        return "%s id=%d name=%s, name id=%d" % \
            (self.resourceName, id(self), self.desktopFileName, id(self.desktopFileName))

    @staticmethod
    def current():
        """the currently wanted tileset. If not yet defined, do so"""
        pass
