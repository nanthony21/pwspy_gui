# Copyright © 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
#
# This file is part of PWSpy.
#
# PWSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PWSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PWSpy.  If not, see <https://www.gnu.org/licenses/>.

"""

@author: Nick Anthony
"""
import typing

from PyQt5 import QtCore
from PyQt5.QtCore import QModelIndex
from pwspy.utility.acquisition import SequencerStep


class TreeModel(QtCore.QAbstractItemModel):
    def __init__(self, root: SequencerStep, parent=None):
        super(TreeModel, self).__init__(parent)
        self._rootItem = SequencerStep(None, None, None)  # This will be invisible but will determine the header labels.
        self._rootItem.addChild(root)

    def invisibleRootItem(self) -> SequencerStep:
        return self._rootItem

    def columnCount(self, parent: QModelIndex) -> int:
        return 1

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole:  # We only support this role type. Return the SequencerStep itself as the data.
            return None
        item: SequencerStep = index.internalPointer()
        return item

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

    def setData(self, index: QModelIndex, value: typing.Any, role: int = ...) -> bool:
        return True  # We don't allow setting data. Always report success.

    def headerData(self, section, orientation, role):
        return "Steps"
        # if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
        #     return self._rootItem.data(section)
        # return None

    def index(self, row: int, column: int, parent: QModelIndex):
        # if not self.hasIndex(row, column, parent): #This was causing bugs
        #     return QtCore.QModelIndex()
        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self._rootItem
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        childItem = index.internalPointer()
        parentItem = childItem.parent()
        if parentItem == self._rootItem:
            return QtCore.QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent: QModelIndex):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            return self._rootItem.childCount()
        else:
            return parent.internalPointer().childCount()

