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

from __future__ import annotations

import typing as t_
import numpy as np
import pwspy.dataTypes as pwsdt
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidget, QGridLayout, QButtonGroup, QPushButton, QDialog, QSpinBox, QLabel, \
    QMessageBox, QMenu, QAction, QApplication
from pwspy_gui.PWSAnalysisApp._roiManager import _DefaultROIManager
from pwspy_gui.PWSAnalysisApp.componentInterfaces import ROIManager

from pwspy_gui.PWSAnalysisApp.utilities.conglomeratedAnalysis import ConglomerateAnalysisResults
import os
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting._analysisViewer import AnalysisViewer
from mpl_qt_viz.roiSelection import FullImPaintCreator, AdjustableSelector, LassoCreator, EllipseCreator, RegionalPaintCreator, PolygonModifier, WaterShedPaintCreator
if t_.TYPE_CHECKING:
    from pwspy.analysis.pws import PWSAnalysisResults
    from pwspy.analysis.dynamics import DynamicsAnalysisResults

    AnalysisResultsComboType = t_.Union[ConglomerateAnalysisResults,  # Internally we will use the ConglomerateAnalysisResults but we accept a regular tuple as well.
                                        t_.Tuple[
                                            t_.Optional[PWSAnalysisResults],
                                            t_.Optional[DynamicsAnalysisResults]
                                        ]]


class RoiDrawer(QWidget):
    """
    A widget for interactively drawing ROIs. Defaults to showing as it's own window, this can be overridden with the `flags` argument.

    Args:
        metadatas: A list of pwspy AcquisitionDirectory `Acquisition` objects paired with optional analysis results objects for that acquisition.
    """
    roiCreated = pyqtSignal(pwsdt.Acquisition, pwsdt.RoiFile, bool)  # Fired when a roi is created by this widget.
    roiDeleted = pyqtSignal(pwsdt.Acquisition, pwsdt.RoiFile)
    roiModified = pyqtSignal(pwsdt.Acquisition, pwsdt.RoiFile)
    metadataChanged = pyqtSignal(pwsdt.Acquisition)  # The acquisition we are looking at has been switched.

    def __init__(self, metadatas: t_.List[t_.Tuple[pwsdt.Acquisition, t_.Optional[AnalysisViewer.AnalysisResultsComboType]]],
                 roiManager: ROIManager = None, parent=None, flags=QtCore.Qt.Window,
                 title: str = "Roi Drawer 3000", initialField=AnalysisViewer.PlotFields.Thumbnail):
        QWidget.__init__(self, parent=parent, flags=flags)
        self.setWindowTitle(title)
        self.metadatas = metadatas

        layout = QGridLayout()

        self._mdIndex = 0
        self.roiManager = roiManager if roiManager else _DefaultROIManager(self)
        self.anViewer = AnalysisViewer(self.metadatas[self._mdIndex][0], self.metadatas[self._mdIndex][1], title, initialField=initialField, roiManager=self.roiManager)
        self.anViewer.roiPlot.roiDeleted.connect(lambda acq, roi: self.roiDeleted.emit(acq, roi))
        self.anViewer.roiPlot.roiModified.connect(lambda acq, roi: self.roiModified.emit(acq, roi))
        self.anViewer.roiPlot.roiCreated.connect(lambda acq, roi: self.roiCreated.emit(acq, roi, False))

        self.newRoiDlg = NewRoiDlg(self)

        self.noneButton = QPushButton("Inspect")
        self.lassoButton = QPushButton("Lasso")
        self.lassoButton.setToolTip(LassoCreator.getHelpText())
        self.ellipseButton = QPushButton("Ellipse")
        self.ellipseButton.setToolTip(EllipseCreator.getHelpText())
        self.paintButton = QPushButton("Paint")
        self.paintButton.setToolTip(RegionalPaintCreator.getHelpText())
        self.lastButton_ = None

        self.buttonGroup = QButtonGroup(self)
        self.buttonGroup.addButton(self.noneButton)
        self.buttonGroup.addButton(self.lassoButton)
        self.buttonGroup.addButton(self.ellipseButton)
        self.buttonGroup.addButton(self.paintButton)
        self.buttonGroup.buttonReleased.connect(self.handleButtons)
        [i.setCheckable(True) for i in self.buttonGroup.buttons()]
        self.noneButton.setChecked(True) #This doesn't seem to trigger handle buttons. we'll do that at the end of the constructor

        def handleAdjustButton(checkstate: bool):
            if self.selector is not None:
                self.selector.adjustable = checkstate

        self.adjustButton = QPushButton("Tune")
        self.adjustButton.setToolTip(PolygonModifier.getHelpText())
        self.adjustButton.setCheckable(True)
        self.adjustButton.setMaximumWidth(50)
        self.adjustButton.toggled.connect(handleAdjustButton)

        def showNextCell():
            idx = self._mdIndex + 1
            if idx >= len(self.metadatas):
                idx = 0
            self._updateDisplayedCell(idx)

        def showPreviousCell():
            idx = self._mdIndex - 1
            if idx < 0:
                idx = len(self.metadatas) - 1
            self._updateDisplayedCell(idx)

        self.previousButton = QPushButton('←')
        self.nextButton = QPushButton('→')
        self.previousButton.released.connect(showPreviousCell)
        self.nextButton.released.connect(showNextCell)

        layout.addWidget(self.noneButton, 0, 0, 1, 1)
        layout.addWidget(self.lassoButton, 0, 1, 1, 1)
        layout.addWidget(self.ellipseButton, 0, 2, 1, 1)
        layout.addWidget(self.paintButton, 0, 3, 1, 1)
        layout.addWidget(self.adjustButton, 0, 4, 1, 1)
        layout.addWidget(self.previousButton, 0, 6, 1, 1)
        layout.addWidget(self.nextButton, 0, 7, 1, 1)
        layout.addWidget(self.anViewer, 1, 0, 8, 8)
        self.setLayout(layout)
        self.selector: AdjustableSelector = AdjustableSelector(self.anViewer.roiPlot.ax, self.anViewer.roiPlot.im, LassoCreator, onfinished=self.finalizeRoi, onPolyTuningCancelled=lambda: self.selector.setActive(True))
        self.handleButtons(self.noneButton)  # Helps initialize state
        self.show()

    def finalizeRoi(self, verts: np.ndarray):
        roiName = self.anViewer.roiPlot.roiFilter.currentText()
        if roiName == '':
            QMessageBox.information(self, 'Wait', 'Please type an ROI name into the box at the top of the screen.')
            self.selector.setActive(True)
            return
        shape = self.anViewer.data.shape
        self.newRoiDlg.show()
        self.newRoiDlg.exec()
        if self.newRoiDlg.result() == QDialog.Accepted:
            md = self.metadatas[self._mdIndex][0]
            self._saveNewRoi(roiName, self.newRoiDlg.number, np.array(verts), shape, md)
        self.selector.setActive(True)  # Start the next roiFile.

    def _saveNewRoi(self, name: str, num: int, verts, datashape, acq: pwsdt.Acquisition):
        roi = pwsdt.Roi.fromVerts(verts, datashape)
        try:
            roiFile = self.roiManager.createRoi(acq, roi, name, num, overwrite=False)
            self.roiCreated.emit(acq, roiFile, False)
        except OSError as ose:
            ans = QMessageBox.question(self.anViewer, 'Overwrite?',
                                       f"Roi {name}:{num} already exists. Overwrite?")
            if ans == QMessageBox.Yes:
                roiFile = self.roiManager.getROI(acq, name, num)
                self.roiManager.updateRoi(roiFile, roi)
                self.roiCreated.emit(acq, roiFile, True)

    def handleButtons(self, button):
        if button is self.lassoButton and self.lastButton_ is not button:
            self.selector.setSelector(LassoCreator)
            self.selector.setActive(True)
            self.anViewer.roiPlot.enableHoverAnnotation(False)
            self.adjustButton.setEnabled(True)
        elif button is self.ellipseButton and self.lastButton_ is not button:
            self.selector.setSelector(EllipseCreator)
            self.selector.setActive(True)
            self.anViewer.roiPlot.enableHoverAnnotation(False)
            self.adjustButton.setEnabled(True)
        elif button is self.paintButton:
            def setSelector(sel):
                self.selector.setSelector(sel)
                self.selector.setActive(True)
                self.anViewer.roiPlot.enableHoverAnnotation(False)
                self.adjustButton.setEnabled(True)

            menu = QMenu(self)
            regionalAction = QAction("Regional")
            regionalAction.triggered.connect(lambda: setSelector(RegionalPaintCreator))
            menu.addAction(regionalAction)
            fullAction = QAction("Full Image")
            fullAction.triggered.connect(lambda: setSelector(FullImPaintCreator))
            menu.addAction(fullAction)
            watershedAction = QAction("Watershed")
            watershedAction.triggered.connect(lambda: setSelector(WaterShedPaintCreator))
            menu.addAction(watershedAction)
            menu.exec(self.mapToGlobal(self.paintButton.pos()))

        elif button is self.noneButton and self.lastButton_ is not button:
            if self.selector is not None:
                self.selector.setActive(False)
            self.anViewer.roiPlot.enableHoverAnnotation(True)
            self.adjustButton.setEnabled(False)
        self.lastButton_ = button

    def _updateDisplayedCell(self, idx: int):
        currRoi = self.anViewer.roiPlot.roiFilter.currentText()  # Since the next cell we look at will likely not have rois of the current name we want to manually force the ROI name to stay the same.
        md, analysis = self.metadatas[idx]
        self.anViewer.setMetadata(md, analysis=analysis)
        self.anViewer.roiPlot.roiFilter.setEditText(currRoi)  # manually force the ROI name to stay the same.
        self.selector.reset()  # Make sure to get rid of all rois
        self.setWindowTitle(f"Roi Drawer - {os.path.split(md.filePath)[-1]}")
        self.metadataChanged.emit(md)
        self._mdIndex = idx

    def setDisplayedAcquisition(self, acq: pwsdt.Acquisition):
        """Switch the image to display images associated with `acq`. If `acq` wasn't passed in to the constructor of this object then
        an IndexError will be raised.

        Args:
            acq: The acquisition to display.
        """
        for i, (mdAcq, analysis) in enumerate(self.metadatas):
            if mdAcq is acq:
                self._updateDisplayedCell(i)
                return
        raise IndexError(f"Acquisition {acq} was not found in the list of available images.")

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        self.selector.setActive(False)  # This cleans up remaining resources of the selector widgets.
        super().closeEvent(a0)


class NewRoiDlg(QDialog):
    def __init__(self, parent: RoiDrawer):
        super().__init__(parent=parent, flags=QtCore.Qt.FramelessWindowHint)
        self.setWindowTitle("ROI #")
        self.parent = parent
        self.setModal(True)
        self.number = None
        l = QGridLayout()
        self.numBox = QSpinBox()
        self.numBox.setMaximum(100000)
        self.numBox.setMinimum(0)
        self.okButton = QPushButton("Ok")
        self.okButton.released.connect(self.accept)
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.released.connect(self.reject)
        l.addWidget(QLabel("ROI #"), 0, 0, 1, 1, alignment=QtCore.Qt.AlignRight)
        l.addWidget(self.numBox, 0, 1, 1, 1)
        l.addWidget(self.okButton, 1, 0, 1, 1)
        l.addWidget(self.cancelButton, 1, 1, 1, 1)
        self.setLayout(l)

    def accept(self) -> None:
        self.number = self.numBox.value()
        self.numBox.setValue(self.numBox.value()+1)  # Increment the value.
        super().accept()

    def reject(self) -> None:
        self.number = None
        super().reject()

    def show(self) -> None:
        if len(self.parent.anViewer.roiPlot.rois) > 0:
            roiParams = self.parent.anViewer.roiPlot.rois
            newNum = max([param.roiFile.number for param in roiParams]) + 1  # Set the box 1 number abox the maximum found
            self.numBox.setValue(newNum)
        else:
            self.numBox.setValue(0)  # start at 0
        super().show()


