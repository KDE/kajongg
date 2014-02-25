# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

kajongg is free software you can redistribute it and/or modify
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

# pylint: disable=unused-import

from PyQt4 import uic
from PyQt4.QtCore import QT_VERSION_STR
from PyQt4.QtCore import PYQT_VERSION_STR
from PyQt4.QtCore import QAbstractAnimation
from PyQt4.QtCore import QAbstractItemModel
from PyQt4.QtCore import QAbstractTableModel
from PyQt4.QtCore import QByteArray
from PyQt4.QtCore import QCoreApplication
from PyQt4.QtCore import QEasingCurve
from PyQt4.QtCore import QEvent
from PyQt4.QtCore import QEventLoop
from PyQt4.QtCore import QMetaObject
from PyQt4.QtCore import QMimeData
from PyQt4.QtCore import QModelIndex
from PyQt4.QtCore import QObject
from PyQt4.QtCore import QParallelAnimationGroup
from PyQt4.QtCore import QPersistentModelIndex
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QVariant
from PyQt4.QtCore import QPoint
from PyQt4.QtCore import QPointF
from PyQt4.QtCore import QPropertyAnimation
from PyQt4.QtCore import QRect
from PyQt4.QtCore import QRectF
from PyQt4.QtCore import QSize
from PyQt4.QtCore import QSizeF
from PyQt4.QtCore import QSocketNotifier
try:
    from PyQt4.QtCore import QString
except ImportError:
    from qstring import QString
from PyQt4.QtCore import QTimer
from PyQt4.QtCore import QTranslator
from PyQt4.QtCore import SLOT
from PyQt4.QtCore import pyqtProperty
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QAbstractItemView
from PyQt4.QtGui import QAction
from PyQt4.QtGui import QApplication
from PyQt4.QtGui import QBrush
from PyQt4.QtGui import QCheckBox
from PyQt4.QtGui import QColor
from PyQt4.QtGui import QComboBox
from PyQt4.QtGui import QCursor
from PyQt4.QtGui import QDialog
from PyQt4.QtGui import QDialogButtonBox
from PyQt4.QtGui import QDrag
from PyQt4.QtGui import QFont
from PyQt4.QtGui import QFontMetrics
from PyQt4.QtGui import QFormLayout
from PyQt4.QtGui import QFrame
from PyQt4.QtGui import QGraphicsItem
from PyQt4.QtGui import QGraphicsEllipseItem
from PyQt4.QtGui import QGraphicsObject
from PyQt4.QtGui import QGraphicsRectItem
from PyQt4.QtGui import QGraphicsScene
from PyQt4.QtGui import QGraphicsSimpleTextItem
from PyQt4.QtGui import QGraphicsView
from PyQt4.QtGui import QGridLayout
from PyQt4.QtGui import QHBoxLayout
from PyQt4.QtGui import QHeaderView
from PyQt4.QtGui import QIcon
from PyQt4.QtGui import QImageReader
from PyQt4.QtGui import QItemSelectionModel
from PyQt4.QtGui import QLabel
from PyQt4.QtGui import QLineEdit
KLineEdit = QLineEdit  # pylint: disable=invalid-name
from PyQt4.QtGui import QListWidget
from PyQt4.QtGui import QListWidgetItem
from PyQt4.QtGui import QListView
from PyQt4.QtGui import QMainWindow
from PyQt4.QtGui import QMenu
from PyQt4.QtGui import QMessageBox
from PyQt4.QtGui import QPainter
from PyQt4.QtGui import QPalette
from PyQt4.QtGui import QPen
from PyQt4.QtGui import QPixmap
from PyQt4.QtGui import QPixmapCache
from PyQt4.QtGui import QProgressBar
from PyQt4.QtGui import QRadioButton
from PyQt4.QtGui import QPushButton
from PyQt4.QtGui import QScrollArea
from PyQt4.QtGui import QScrollBar
from PyQt4.QtGui import QSizePolicy
from PyQt4.QtGui import QSlider
from PyQt4.QtGui import QSpacerItem
from PyQt4.QtGui import QSpinBox
from PyQt4.QtGui import QSplitter
from PyQt4.QtGui import QStackedWidget
from PyQt4.QtGui import QStatusBar
from PyQt4.QtGui import QStringListModel
from PyQt4.QtGui import QStyle
from PyQt4.QtGui import QStyledItemDelegate
from PyQt4.QtGui import QStyleOption
from PyQt4.QtGui import QStyleOptionGraphicsItem
from PyQt4.QtGui import QStyleOptionViewItem
from PyQt4.QtGui import QTableView
from PyQt4.QtGui import QTableWidget
from PyQt4.QtGui import QTableWidgetItem
from PyQt4.QtGui import QTabWidget
from PyQt4.QtGui import QTextBrowser
from PyQt4.QtGui import QTextDocument
from PyQt4.QtGui import QTextEdit
from PyQt4.QtGui import QToolBar
from PyQt4.QtGui import QToolButton
from PyQt4.QtGui import QTransform
from PyQt4.QtGui import QTreeView
from PyQt4.QtGui import QVBoxLayout
from PyQt4.QtGui import QWidget
from PyQt4.QtGui import QValidator
from PyQt4.QtSvg import QGraphicsSvgItem
from PyQt4.QtSvg import QSvgRenderer

def variantValue(variant):
    """convert QVariant to a python variable"""
    return variant.toPyObject()
