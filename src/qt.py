# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

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

# pylint: disable=unused-import, no-name-in-module

from PyQt5 import uic
from PyQt5.QtCore import PYQT_VERSION_STR
from PyQt5.QtCore import QT_VERSION_STR
from PyQt5.QtCore import QAbstractAnimation
from PyQt5.QtCore import QAbstractItemModel
from PyQt5.QtCore import QAbstractTableModel
from PyQt5.QtCore import QByteArray
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtCore import QStandardPaths
from PyQt5.QtCore import QEasingCurve
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import QEventLoop
from PyQt5.QtCore import QMetaObject
from PyQt5.QtCore import QMimeData
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QObject
from PyQt5.QtCore import QParallelAnimationGroup
from PyQt5.QtCore import QPersistentModelIndex
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QPoint
from PyQt5.QtCore import QPointF
from PyQt5.QtCore import QPropertyAnimation
from PyQt5.QtCore import QRect
from PyQt5.QtCore import QRectF
from PyQt5.QtCore import QSize
from PyQt5.QtCore import QSizeF
from PyQt5.QtCore import QSocketNotifier
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QTranslator
from PyQt5.QtCore import QLocale
from PyQt5.QtCore import pyqtProperty
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QAbstractItemView
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QBrush
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QDialog
from PyQt5.QtWidgets import QDialogButtonBox
from PyQt5.QtGui import QDrag
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtWidgets import QGraphicsObject
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.QtWidgets import QGraphicsSimpleTextItem
from PyQt5.QtWidgets import QGraphicsView
from PyQt5.QtWidgets import QGridLayout
from PyQt5.QtWidgets import QHBoxLayout
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QImageReader
from PyQt5.QtCore import QItemSelectionModel
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QListWidget
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtWidgets import QListView
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QMenu
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import QPainter
from PyQt5.QtGui import QPalette
from PyQt5.QtGui import QPen
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPixmapCache
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtWidgets import QRadioButton
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QScrollArea
from PyQt5.QtWidgets import QScrollBar
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QSlider
from PyQt5.QtWidgets import QSpacerItem
from PyQt5.QtWidgets import QSpinBox
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtWidgets import QStackedWidget
from PyQt5.QtWidgets import QStatusBar
from PyQt5.QtCore import QStringListModel
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QStyledItemDelegate
from PyQt5.QtWidgets import QStyleOption
from PyQt5.QtWidgets import QStyleOptionGraphicsItem
from PyQt5.QtWidgets import QStyleOptionViewItem
from PyQt5.QtWidgets import QTableView
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import QTextBrowser
from PyQt5.QtGui import QTextDocument
from PyQt5.QtWidgets import QTextEdit
from PyQt5.QtWidgets import QToolBar
from PyQt5.QtWidgets import QToolButton
from PyQt5.QtGui import QTransform
from PyQt5.QtWidgets import QTreeView
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QValidator
from PyQt5.QtSvg import QGraphicsSvgItem
from PyQt5.QtSvg import QSvgRenderer
