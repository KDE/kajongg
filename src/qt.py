# -*- coding: utf-8 -*-

"""
Copyright (C) 2008-2012 Wolfgang Rohdewald <wolfgang@rohdewald.de>

SPDX-License-Identifier: GPL-2.0

"""

# pylint: disable=unused-import

from qtpy import uic, QT5, QT6
from qtpy.QtCore import QAbstractAnimation
from qtpy.QtCore import QAbstractItemModel
from qtpy.QtCore import QAbstractTableModel
from qtpy.QtCore import QByteArray
from qtpy.QtCore import QCoreApplication
from qtpy.QtCore import QCommandLineParser
from qtpy.QtCore import QCommandLineOption
from qtpy.QtCore import QLibraryInfo
from qtpy.QtCore import QStandardPaths
from qtpy.QtCore import QEasingCurve
from qtpy.QtCore import QEvent
from qtpy.QtCore import QEventLoop
from qtpy.QtCore import QItemSelection
from qtpy.QtCore import QMetaObject
from qtpy.QtCore import QMimeData
from qtpy.QtCore import QModelIndex
from qtpy.QtCore import QObject
from qtpy.QtCore import QParallelAnimationGroup
from qtpy.QtCore import QPersistentModelIndex
from qtpy.QtCore import Qt
from qtpy.QtCore import QPoint
from qtpy.QtCore import QPointF
from qtpy.QtCore import QPropertyAnimation
from qtpy.QtCore import QRect
from qtpy.QtCore import QRectF
from qtpy.QtCore import QSize
from qtpy.QtCore import QSizeF
from qtpy.QtCore import QSocketNotifier
from qtpy.QtCore import QTimer
from qtpy.QtCore import QTranslator
from qtpy.QtCore import QLocale
from qtpy.QtCore import Property
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QAbstractItemView
from qtpy.QtWidgets import QAction
from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QBrush
from qtpy.QtGui import QKeyEvent
from qtpy.QtGui import QFocusEvent
from qtpy.QtGui import QHideEvent
from qtpy.QtGui import QShowEvent
from qtpy.QtGui import QMouseEvent
from qtpy.QtGui import QWheelEvent
from qtpy.QtGui import QResizeEvent
from qtpy.QtWidgets import QCheckBox
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QComboBox
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QDialog
from qtpy.QtWidgets import QDialogButtonBox
from qtpy.QtGui import QDrag
from qtpy.QtGui import QFont
from qtpy.QtGui import QFontMetrics
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QLayout
from qtpy.QtWidgets import QFormLayout
from qtpy.QtWidgets import QFrame
from qtpy.QtWidgets import QGraphicsItem
from qtpy.QtWidgets import QGraphicsItemGroup
from qtpy.QtWidgets import QGraphicsObject
from qtpy.QtWidgets import QGraphicsRectItem
from qtpy.QtWidgets import QGraphicsScene
from qtpy.QtWidgets import QGraphicsSimpleTextItem
from qtpy.QtWidgets import QGraphicsView
from qtpy.QtWidgets import QGraphicsSceneDragDropEvent
from qtpy.QtWidgets import QGridLayout
from qtpy.QtWidgets import QHBoxLayout
from qtpy.QtWidgets import QHeaderView
from qtpy.QtGui import QIcon
from qtpy.QtGui import QImageReader
from qtpy.QtCore import QItemSelectionModel
from qtpy.QtWidgets import QLabel
from qtpy.QtWidgets import QLineEdit
from qtpy.QtWidgets import QListWidget
from qtpy.QtWidgets import QListWidgetItem
from qtpy.QtWidgets import QListView
from qtpy.QtWidgets import QMainWindow
from qtpy.QtWidgets import QMenu
from qtpy.QtWidgets import QMessageBox
from qtpy.QtGui import QPainter
from qtpy.QtGui import QPalette
from qtpy.QtGui import QPen
from qtpy.QtGui import QPixmap
from qtpy.QtGui import QPixmapCache
from qtpy.QtWidgets import QProgressBar
from qtpy.QtWidgets import QRadioButton
from qtpy.QtWidgets import QPushButton
from qtpy.QtWidgets import QScrollArea
from qtpy.QtWidgets import QScrollBar
from qtpy.QtWidgets import QSizePolicy
from qtpy.QtWidgets import QSlider
from qtpy.QtWidgets import QSpacerItem
from qtpy.QtWidgets import QSpinBox
from qtpy.QtWidgets import QSplitter
from qtpy.QtWidgets import QStackedWidget
from qtpy.QtWidgets import QStatusBar
from qtpy.QtCore import QStringListModel
from qtpy.QtWidgets import QStyle
from qtpy.QtWidgets import QStyledItemDelegate
from qtpy.QtWidgets import QStyleOption
from qtpy.QtWidgets import QStyleOptionGraphicsItem
from qtpy.QtWidgets import QStyleOptionViewItem
from qtpy.QtWidgets import QTableView
from qtpy.QtWidgets import QTableWidget
from qtpy.QtWidgets import QTableWidgetItem
from qtpy.QtWidgets import QTabWidget
from qtpy.QtWidgets import QTextBrowser
from qtpy.QtGui import QTextDocument
from qtpy.QtWidgets import QTextEdit
from qtpy.QtWidgets import QToolBar
from qtpy.QtWidgets import QToolButton
from qtpy.QtGui import QTransform
from qtpy.QtWidgets import QTreeView
from qtpy.QtWidgets import QVBoxLayout
from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QValidator
from qtpy.QtGui import QGuiApplication
try:
    # it seems this moved in Qt6
    from qtpy.QtSvgWidgets import QGraphicsSvgItem  # type: ignore
except ImportError:
    # as it was in Qt5:
    from qtpy.QtSvg import QGraphicsSvgItem  # type:ignore[assignment,attr-defined,no-redef]
from qtpy.QtSvg import QSvgRenderer

# pylint:disable=c-extension-no-member

HAVE_SIP = True
if QT5:
    from PyQt5 import sip
    def sip_cast(obj, _type):
        """hide not so nice things in qt.py"""
        return sip.cast(obj, _type)
elif QT6:
    from PyQt6 import sip  # type:ignore[no-redef]
    def sip_cast(obj, _type):
        """hide not so nice things in qt.py"""
        return sip.cast(obj, _type)
else:
    HAVE_SIP = False

def modeltest_is_supported() ->bool:
    """Is the QT binding supported."""
    if not HAVE_SIP:
        return False
    try:
        _ = sip_cast(QSize(), QSize)
        return True
    except TypeError:
        return False

SIP_VERSION_STR = 'no sip'
if HAVE_SIP:
    SIP_VERSION_STR = sip.SIP_VERSION_STR
