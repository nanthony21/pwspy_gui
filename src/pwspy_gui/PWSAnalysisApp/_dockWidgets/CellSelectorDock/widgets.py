# Copyright 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
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
import typing as t_
import json
import os
from json import JSONDecodeError

import logging
from PyQt5 import QtCore, QtGui
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import QPushButton, QTableWidgetItem, QTableWidget, QAbstractItemView, QMenu, QWidget, QMessageBox, \
    QInputDialog, QHeaderView

from pwspy_gui.PWSAnalysisApp.sharedWidgets import ScrollableMessageBox
from pwspy.dataTypes import Acquisition, PwsMetaData, DynMetaData

from pwspy_gui.PWSAnalysisApp.sharedWidgets.dictDisplayTree import DictDisplayTreeDialog
from pwspy_gui.PWSAnalysisApp.sharedWidgets.tables import NumberTableWidgetItem
if t_.TYPE_CHECKING:
    from pwspy.analysis.pws import PWSAnalysisResults
    from pwspy.analysis.dynamics import DynamicsAnalysisResults


def evalToolTip(cls: t_.Type[QWidget], method):
    """Given a QWidget and a function that returns a string, this decorator returns a modified class that will evaluate
    the function each time the tooltip is requested."""
    class newClass(cls):
        def event(self, e: QtCore.QEvent):
            if e.type() == QtCore.QEvent.ToolTip:
                self.setToolTip(method())
            return super().event(e)
    return newClass


class PreferencesMetadata:
    def __init__(self, filePath: str, invalid: bool = False, reference: bool = False):
        self.filePath = filePath
        self._invalid = invalid
        self._reference = reference
        self._stale: bool = True  # Keeps track of if this object is in sync with the file. False means no saving is needed.

    def close(self):
        if self._stale:
            self._toJson()  # Save if needed.

    def __del__(self):  # This doesn't always work but it doesn't hurt to try
        self.close()

    @property
    def reference(self): return self._reference

    @reference.setter
    def reference(self, ref: bool):
        if self._reference != ref:
            self._reference = ref
            self._stale = True

    @property
    def invalid(self): return self._invalid

    @invalid.setter
    def invalid(self, inv: bool):
        if self._invalid != inv:
            self._invalid = inv
            self._stale = True


    def _toJson(self):
        d = {'invalid': self._invalid, 'reference': self._reference}
        with open(self.filePath, 'w') as f:
            json.dump(d, f)
        self._stale = False

    @classmethod
    def fromJson(cls, filePath: str):
        with open(filePath, 'r') as f:
            d = json.load(f)
        md = PreferencesMetadata(filePath, invalid=d['invalid'], reference=d['reference'])
        md._stale = False
        return md


class CellTableWidgetItem:
    """Represents a single row of the CellTableWidget and corresponds to a single PWS acquisition."""
    def __init__(self, acq: Acquisition, label: str, num: int, additionalWidgets: t_.Sequence[QWidget] = None):
        self.Acquisition = acq
        self.num = num
        self.path = label
        self.pluginWidgets = [] if additionalWidgets is None else additionalWidgets
        self.notesButton = evalToolTip(QPushButton, acq.getNotes)("Open")
        self.notesButton.setFixedSize(40, 30)
        self.pathLabel = QTableWidgetItem(self.path)
        self.pathLabel.setToolTip(acq.idTag)
        self.numLabel = NumberTableWidgetItem(num)
        self.numLabel.setToolTip(acq.idTag)
        self.roiLabel = NumberTableWidgetItem(0)
        self.anLabel = NumberTableWidgetItem(0)
        self.notesButton.released.connect(self.Acquisition.editNotes)
        self.pLabel = QTableWidgetItem()
        self.pLabel.setToolTip("Indicates if PWS measurement is present")
        self.dLabel = QTableWidgetItem()
        self.dLabel.setToolTip("Indicates if Dynamics measurement is present")
        self.fLabel = QTableWidgetItem()
        self.fLabel.setToolTip("Indicates if Fluorescence measurement is present")
        for i in [self.pLabel, self.dLabel, self.fLabel]:
            i.setTextAlignment(QtCore.Qt.AlignCenter)
        for i in [self.pathLabel, self.pLabel, self.dLabel, self.fLabel]:  # Make uneditable
            i.setFlags(i.flags() ^ QtCore.Qt.ItemIsEditable)
        for metadata, label in [(self.Acquisition.pws, self.pLabel), (self.Acquisition.dynamics, self.dLabel)]:
            if metadata is not None:
                label.setText('Y')
                label.setBackground(QtCore.Qt.darkGreen)
                label.setToolTip(metadata.idTag)
            else:
                label.setText('N')
                label.setBackground(QtCore.Qt.white)
        if len(self.Acquisition.fluorescence) != 0: self.fLabel.setText('Y'); self.fLabel.setBackground(QtCore.Qt.darkGreen)
        else: self.fLabel.setText('N'); self.fLabel.setBackground(QtCore.Qt.white)
        self._items = [self.pathLabel, self.numLabel, self.roiLabel, self.anLabel] + self.pluginWidgets #This list is used for changing background color and for setting all items selected.
        self.refresh()
        mdPath = os.path.join(self.Acquisition.filePath, 'AnAppPrefs.json')
        self.md: PreferencesMetadata
        try:
            self.md = PreferencesMetadata.fromJson(mdPath)
        except (JSONDecodeError, FileNotFoundError):
            self.md = PreferencesMetadata(mdPath)
        self.setInvalid(self.md.invalid)  # Update item color based on saved status. Since invalid status overrides reference status we must do this first.
        self.setReference(self.md.reference)  # We override the default automatic saving of metadata since we're just loading anyway, nothing has been changed.

    @property
    def row(self):
        """Since this can be added to a table that uses sorting we can't know that the row number will remain constant.
        This should return the correct row number."""
        return self.numLabel.row()

    def setInvalid(self, invalid: bool):
        if invalid:
            self._setItemColor(QtCore.Qt.red)
            self.md.reference = False
        else:
            self._setItemColor(QtCore.Qt.white)
        self.md.invalid = invalid

    def setReference(self, reference: bool) -> None:
        if self.isInvalid():
            return
        if reference:
            self._setItemColor(QtCore.Qt.darkGreen)
        else:
            self._setItemColor(QtCore.Qt.white)
        self.md.reference = reference

    def isInvalid(self) -> bool:
        return self.md.invalid

    def isReference(self) -> bool:
        return self.md.reference

    def setSelected(self, select: bool):
        for i in self._items:
            i.setSelected(select)

    def setHighlighted(self, select: bool):
        originalFont = self._items[0].font()
        originalFont.setBold(select)
        for i in self._items:
            i.setFont(originalFont)

    def close(self):
        try:
            self.md.close()
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to save app metadata for {self.md.filePath}")
            logger.exception(e)

    def refresh(self):
        """Set the number of roiFile's and analyses. Update the tooltips."""
        rois = self.Acquisition.getRois()
        self.roiLabel.setNumber(len(rois))
        anNumber = 0  # This is in case the next few statements evaluate to false.
        anToolTip = ""
        if self.Acquisition.pws is not None:
            pwsAnalyses = self.Acquisition.pws.getAnalyses()
            anNumber += len(pwsAnalyses)
            if len(pwsAnalyses) != 0:
                anToolTip += "PWS:" + ', '.join(pwsAnalyses)
        if self.Acquisition.dynamics is not None:
            dynAnalyses = self.Acquisition.dynamics.getAnalyses()
            anNumber += len(dynAnalyses)
            if len(dynAnalyses) != 0:
                anToolTip += "\nDYN:" + ', '.join(dynAnalyses)
        self.anLabel.setNumber(anNumber)
        self.anLabel.setToolTip(anToolTip)
        if self.Acquisition.getNotes() != '':
            self.notesButton.setStyleSheet('QPushButton { background-color: lightgreen;}')
        else:
            self.notesButton.setStyleSheet('QPushButton { background-color: lightgrey;}')

        nameNums = [(name, num) for name, num, fformat in rois]
        if len(nameNums) > 0:
            names = set(list(zip(*nameNums))[0])
            d = {name: [num for nname, num in nameNums if nname == name] for name in names}
            self.roiLabel.setToolTip("\n".join([f'{k}: {v}' for k, v in d.items()]))

    def __del__(self):
        self.close()  # This is here just in case. realistically del rarely gets called, need to manually close each cell item.

    def _setItemColor(self, color):
        for i in self._items:
            i.setBackground(color)


class CellTableWidget(QTableWidget):
    """This is the table from which the user can select which cells to analyze, plot, etc. Each row of the table is
    represented by a CellTableWidgetItem which are stored in the self._cellItems list"""
    referencesChanged = QtCore.pyqtSignal(bool, list)
    itemsCleared = QtCore.pyqtSignal()

    def __init__(self, parent, additionalColumns: t_.Sequence[str] = None):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._showContextMenu)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Columns in the form {name: (width, resizable)}
        columns = {'Path': (60, True), 'Cell#': (40, True), 'ROIs': (40, True), 'Analyses': (50, True),
                   'Notes': (40, False), 'P': (20, False), 'D': (20, False), 'F': (20, False)}
        if additionalColumns is not None:
            for colName in additionalColumns:
                columns[colName] = (50, True) # Automatically determine width from fontmetrics.
        self.setRowCount(0)
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns.keys())
        self.verticalHeader().hide()
        [self.setColumnWidth(i, w) for i, (w, resizable) in enumerate(columns.values())]  # Set the column widths
        [self.horizontalHeader().setSectionResizeMode(i, self.horizontalHeader().Fixed) for i, (w, resizable) in enumerate(columns.values()) if not resizable] #set the notes, and p/d/f columns nonresizeable
        self.cellItems: t_.Dict[Acquisition, CellTableWidgetItem] = {}
        #This makes the items stay looking selected even when the table is inactive
        self.setStyleSheet("""QTableWidget::item:active {
                                selection-background-color: darkblue;
                                selection-color: white;}
                                
                                QTableWidget::item:inactive {
                                selection-background-color: darkblue;
                                selection-color: white;}""")
        self.palette().setColor(QPalette.Highlight, QtGui.QColor("#3a7fc2")) # This makes it so the selected cells stay colored even when the table isn't active.
        self.palette().setColor(QPalette.HighlightedText, QtCore.Qt.white)

    @property
    def selectedCellItems(self) -> t_.Tuple[CellTableWidgetItem]:
        """Returns the rows that have been selected."""
        rowIndices = [i.row() for i in self.selectedIndexes() if i.column()==0]  # This returns indexes for all items, which means we get several for a single row. Only look at the 0 column indexes.

        rowIndices.sort()
        _ = {i.row: i for i in self.cellItems.values()} #Cell items keyed by their current row position.
        return tuple(_[i] for i in rowIndices)

    def refreshCellItems(self, cells: t_.List[Acquisition] = None):
        """`Cells` indicates which cells need refreshing. If cells is None then all cells will be refreshed."""
        if cells is None:
            cells = self.cellItems.keys()
        for acq in cells:
            self.cellItems[acq].refresh()

    def addCellItems(self, items: t_.Dict[Acquisition, CellTableWidgetItem]) -> None:
        row = len(self.cellItems)
        self.setSortingEnabled(False)
        self.setRowCount(row + len(items))
        for i, item in enumerate(items.values()):
            newrow = row + i
            self.setItem(newrow, 0, item.pathLabel)
            self.setItem(newrow, 1, item.numLabel)
            self.setItem(newrow, 2, item.roiLabel)
            self.setItem(newrow, 3, item.anLabel)
            self.setCellWidget(newrow, 4, item.notesButton)
            self.setItem(newrow, 5, item.pLabel)
            self.setItem(newrow, 6, item.dLabel)
            self.setItem(newrow, 7, item.fLabel)
            for j, widg in enumerate(item.pluginWidgets):
                self.setItem(newrow, 8+j, widg)
        self.setSortingEnabled(True)
        self.cellItems.update(items)  # update the dict

    def clearCellItems(self) -> None:
        self.setRowCount(0)
        for c in self.cellItems.values():
            c.close() #This causes the cell item to save it's metadata.
        self.cellItems = {}
        self.itemsCleared.emit()

    def _showContextMenu(self, point: QtCore.QPoint):
        if len(self.selectedCellItems) > 0:
            menu = QMenu("Context Menu", parent=self)
            state = not self.selectedCellItems[0].isInvalid()
            stateString = "Disable Cell(s)" if state else "Enable Cell(s)"
            refState = not self.selectedCellItems[0].isReference()
            refStateString = "Set as Reference" if refState else "Unset as Reference"
            invalidAction = menu.addAction(stateString)
            invalidAction.triggered.connect(lambda: self._toggleSelectedCellsInvalid(state))
            refAction = menu.addAction(refStateString)
            refAction.triggered.connect(lambda: self._toggleSelectedCellsReference(refState))

            menu.addSeparator()
            mdAction = menu.addAction("Display Metadata")
            mdAction.triggered.connect(self._displayCellMetadata)
            anAction = menu.addAction("View analysis settings")
            anAction.triggered.connect(self._displayAnalysisSettings)
            if os.name == 'nt':  # Must be on windows.
                folderAction = menu.addAction("Open folder")
                folderAction.triggered.connect(lambda: [os.startfile(os.path.realpath(cellItem.Acquisition.filePath)) for cellItem in self.selectedCellItems])

            menu.addSeparator()
            delAnAction = menu.addAction("Delete analysis by name")
            delAnAction.triggered.connect(self._deleteAnalysisByName)
            delRoiAction = menu.addAction("Delete ROIs by name")
            delRoiAction.triggered.connect(self._deleteRoisByName)

            menu.exec(self.mapToGlobal(point))

    def _deleteAnalysisByName(self):
        anName, clickedOk = QInputDialog.getText(self, "Analysis Name", "Analysis name to delete")
        if not clickedOk:
            return
        deletableCells = []
        for i in self.selectedCellItems:
            if i.Acquisition.pws is not None:
                if anName in i.Acquisition.pws.getAnalyses():
                    deletableCells.append(i.Acquisition.pws)
            if i.Acquisition.dynamics is not None:
                if anName in i.Acquisition.dynamics.getAnalyses():
                    deletableCells.append(i.Acquisition.dynamics)
        if len(deletableCells)==0:
            QMessageBox.information(self, "Hmm", "No matching analysis files were found.")
        else:
            ret = ScrollableMessageBox.question(self, "Delete Analysis?",
                f"Are you sure you want to delete {anName} from:"
                f"\nPWS: {', '.join([os.path.split(i.acquisitionDirectory.filePath)[-1] for i in deletableCells if isinstance(i, PwsMetaData)])}"
                f"\nDynamics: {', '.join([os.path.split(i.acquisitionDirectory.filePath)[-1] for i in deletableCells if isinstance(i, DynMetaData)])}")
            if ret == QMessageBox.Yes:
                [i.removeAnalysis(anName) for i in deletableCells]
            self.refreshCellItems()

    def _deleteRoisByName(self):
        roiName, clickeOk = QInputDialog.getText(self, "ROI Name", "ROI name to delete")
        if not clickeOk:
            return
        deletableCells = []
        for i in self.selectedCellItems:
            if roiName in [roiName for roiName, roiNum, fformat in i.Acquisition.getRois()]:
                deletableCells.append(i.Acquisition)
        if len(deletableCells)==0:
            QMessageBox.information(self, "Hmm", "No matching ROI files were found.")
        else:
            if ScrollableMessageBox.question(self, "Delete ROI?",
                                             f"Are you sure you want to delete ROI: {roiName} from: \n{', '.join([os.path.split(i.filePath)[-1] for i in deletableCells])}") == QMessageBox.Yes:
                [i.deleteRoi(roiName, roiNum) for i in deletableCells for ROIName, roiNum, fformat in i.getRois() if ROIName == roiName]
            self.refreshCellItems()

    def _displayAnalysisSettings(self):
        pwsAnalyses = set()
        for i in self.selectedCellItems:
            if i.Acquisition.pws is not None:
                #We assume that analyses with the same name have the same settings
                pwsAnalyses.update(i.Acquisition.pws.getAnalyses())
        for an in pwsAnalyses:
            for i in self.selectedCellItems:
                if i.Acquisition.pws is not None:
                    if an in i.Acquisition.pws.getAnalyses():
                        analysis: PWSAnalysisResults = i.Acquisition.pws.loadAnalysis(an)
                        settingsDict = analysis.settings.asDict()
                        settingsDict['referenceIdTag'] = analysis.referenceIdTag  # Add useful runtime information from the analysis.
                        d = DictDisplayTreeDialog(self, settingsDict, title=an)
                        d.show()
                        break
        dynAnalysis = set()
        for i in self.selectedCellItems:
            if i.Acquisition.dynamics is not None:
                dynAnalysis.update(i.Acquisition.dynamics.getAnalyses())
        for an in dynAnalysis:
            for i in self.selectedCellItems:
                if i.Acquisition.dynamics is not None:
                    if an in i.Acquisition.dynamics.getAnalyses():
                        analysis: DynamicsAnalysisResults = i.Acquisition.dynamics.loadAnalysis(an)
                        settingsDict = analysis.settings.asDict()
                        settingsDict['referenceIdTag'] = analysis.referenceIdTag  # Add useful runtime information
                        d = DictDisplayTreeDialog(self, settingsDict, title=an)
                        d.show()
                        break

    def _displayCellMetadata(self):
        for i in self.selectedCellItems:
            d = DictDisplayTreeDialog(self, i.Acquisition.pws.dict, title=os.path.join(i.path, f"Cell{i.num}"))
            d.show()

    def _toggleSelectedCellsInvalid(self, state: bool):
        changedItems = []
        for i in self.selectedCellItems:
            if i.isInvalid() != state:
                i.setInvalid(state)
                changedItems.append(i)
        if state:
            self.referencesChanged.emit(False, changedItems)

    def _toggleSelectedCellsReference(self, state: bool) -> None:
        """State indicates whether the cells are being marked as reference or as non-reference."""
        items = self.selectedCellItems
        changedItems = []
        for i in items:
            if (i.isReference() != state) and (not i.isInvalid()):
                i.setReference(state)
                changedItems.append(i)
        self.referencesChanged.emit(state, changedItems)


class ReferencesTableItem(QTableWidgetItem):
    """A single row of the reference table."""
    def __init__(self, item: CellTableWidgetItem):
        self.item = item
        super().__init__(os.path.join(item.pathLabel.text(), f'Cell{item.num}'))
        self.setToolTip(os.path.join(item.pathLabel.text(), f'Cell{item.num}'))

    def setHighlighted(self, select: bool):
        originalFont = self.font()
        originalFont.setBold(select)
        self.setFont(originalFont)


class ReferencesTable(QTableWidget):
    """This table shows all acquisitions which can be used as a reference in an analysis."""
    def __init__(self, parent: QWidget, cellTable: CellTableWidget):
        super().__init__(parent)
        #This makes the items stay looking selected even when the table is inactive
        self.setStyleSheet("""QTableWidget::item:active {   
                                selection-background-color: darkblue;
                                selection-color: white;}
                                QTableWidget::item:inactive {
                                selection-background-color: darkblue;
                                selection-color: white;}""")
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(('Reference',))
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setRowCount(0)
        self.verticalHeader().hide()
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._showContextMenu)
        cellTable.referencesChanged.connect(self.updateReferences)
        cellTable.itemsCleared.connect(self._clearItems)
        self._references: t_.List[CellTableWidgetItem] = []

    def updateReferences(self, state: bool, items: t_.List[CellTableWidgetItem]):
        """state indicates if the cells are being added or being removed as references."""
        if state:
            for item in items:
                if item not in self._references:
                    row = len(self._references)
                    self.setRowCount(row + 1)
                    self.setItem(row, 0, ReferencesTableItem(item))
                    self._references.append(item)
        else:
            for item in items:
                if item in self._references:
                    self._references.remove(item)
                    item.setReference(False)
                    # find row number
                    for i in range(self.rowCount()):
                        if item is self.item(i, 0).item:
                            self.removeRow(i)
                            break

    @property
    def selectedReferenceMeta(self) -> t_.Optional[Acquisition]:
        """Returns the PwsMetaData that have been selected. Return None if nothing is selected."""
        items: List[ReferencesTableItem] = self.selectedItems()
        assert len(items) <= 1
        if len(items) == 0:
            return None
        else:
            return items[0].item.Acquisition

    def _showContextMenu(self, point: QtCore.QPoint):
        items = self.selectedItems()
        if len(items) > 0:
            menu = QMenu("Context Menu", parent=self)
            refStateString = "Unset as Reference"
            refAction = menu.addAction(refStateString)
            refAction.triggered.connect(
                lambda: self.updateReferences(False, [i.item for i in self.selectedItems()]))
            menu.exec(self.mapToGlobal(point))

    def _clearItems(self):
        self.setRowCount(0)
        self._references = []

