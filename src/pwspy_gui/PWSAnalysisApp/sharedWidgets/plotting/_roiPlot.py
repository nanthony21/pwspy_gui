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

import logging
import pickle
import re
import typing
from dataclasses import dataclass
from PyQt5.QtCore import pyqtSignal, Qt, QMimeData
from shapely.geometry import Polygon as shapelyPolygon
from matplotlib.backend_bases import KeyEvent, MouseEvent
from matplotlib.patches import PathPatch
import numpy as np
from PyQt5.QtGui import QCursor, QValidator
from PyQt5.QtWidgets import QMenu, QAction, QComboBox, QLabel, QPushButton, QHBoxLayout, QWidget, QVBoxLayout, QApplication, QMessageBox
from PyQt5 import QtCore
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting._bigPlot import BigPlot
from mpl_qt_viz.roiSelection import PolygonModifier, MovingModifier
import pwspy.dataTypes as pwsdt
from pwspy_gui.PWSAnalysisApp._roiManager import _DefaultROIManager, ROIManager
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting._sinCityExporter import SinCityDlg
import descartes
import os


@dataclass
class RoiParams:
    roiFile: pwsdt.RoiFile
    polygon: PathPatch
    selected: bool


class RoiPlot(QWidget):
    """Adds GUI handling for ROIs."""
    roiDeleted = pyqtSignal(pwsdt.AcqDir, pwsdt.RoiFile)  # Indicates that an ROI deletion was initiated by this widget.
    roiModified = pyqtSignal(pwsdt.AcqDir, pwsdt.RoiFile)  # Indicates that an ROI modification was initiated by this widget.
    roiCreated = pyqtSignal(pwsdt.AcqDir, pwsdt.RoiFile)  # Indicates that an ROI modification was created by this widget.

    def __init__(self, acqDir: pwsdt.AcqDir, data: np.ndarray, roiManager: ROIManager, parent=None, flags: QtCore.Qt.WindowFlags = None):
        if flags is not None:
            super().__init__(parent, flags=flags)
        else:
            super().__init__(parent=parent)
        self._plotWidget = BigPlot(data, self)
        self.im = self._plotWidget.im
        self.ax = self._plotWidget.ax

        self.rois: typing.List[RoiParams] = []  # This list holds information about the ROIs that are currently displayed.

        self.roiFilter = QComboBox(self)
        self.roiFilter.setEditable(True)
        self.roiFilter.setValidator(WhiteSpaceValidator())

        self.exportButton = QPushButton("Export")
        self.exportButton.released.connect(self._exportAction)

        layout = QVBoxLayout()
        l = QHBoxLayout()
        l.addWidget(QLabel("Roi"), alignment=QtCore.Qt.AlignRight)
        l.addWidget(self.roiFilter)
        l.addWidget(self.exportButton)
        layout.addLayout(l)
        layout.addWidget(self._plotWidget)
        self.setLayout(layout)

        self.metadata: pwsdt.AcqDir = None
        self.setMetadata(acqDir)

        self.annot = self._plotWidget.ax.annotate("", xy=(0, 0), xytext=(20, 20), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w"),
                            arrowprops=dict(arrowstyle="->"))

        self._toggleCids = None
        self.enableHoverAnnotation(True)

        self._roiManager = roiManager
        self._roiManager.roiRemoved.connect(self._onRoiRemoved)
        self._roiManager.roiUpdated.connect(self._onRoiUpdated)
        self._roiManager.roiCreated.connect(self._onRoiCreated)

    def getImageData(self) -> np.ndarray:
        return self._plotWidget.data

    def setImageData(self, data: np.ndarray):
        self._plotWidget.setImageData(data)

    def setMetadata(self, metadata: pwsdt.AcqDir):
        """Refresh the ROIs based on a new metadata. Also needs to be provided with the data for the image to display."""
        self.metadata = metadata
        self._clearRois()
        currentSel = self.roiFilter.currentText()
        # updateFilter
        try:
            self.roiFilter.currentIndexChanged.disconnect()  # Without this line the roiFilter.clear() line is very slow.
        except Exception:
            pass  # if the signal hasn't yet been connected we'll get an error. ignore it.
        self.roiFilter.clear()
        self.roiFilter.addItem(' ')
        self.roiFilter.addItem('.*')
        rois = self.metadata.getRois()
        roiNames = set(list(zip(*rois))[0]) if len(rois) > 0 else []
        self.roiFilter.addItems(roiNames)
        self.roiFilter.currentIndexChanged.connect(self.showRois)
        for i in range(self.roiFilter.count()):
            if currentSel == self.roiFilter.itemText(i):
                self.roiFilter.setCurrentIndex(i)
                break

    def _setRoiSelected(self, roiParam: RoiParams):
        roiParam.selected = True
        roiParam.polygon.set_edgecolor((0, 1, 1, 0.9))  # Highlight selected rois.
        roiParam.polygon.set_linewidth(2)

    def _setAllRoisSelected(self, selected: bool):
        for param in self.rois:
            param.selected = selected
            if selected:
                param.polygon.set_edgecolor((0, 1, 1, 0.9))  # Highlight selected rois.
                param.polygon.set_linewidth(2)
            else:
                param.polygon.set_edgecolor((0, 1, 0, 0.9))
                param.polygon.set_linewidth(1)

    def enableHoverAnnotation(self, enable: bool):
        if enable:
            self._toggleCids = [self._plotWidget.canvas.mpl_connect('motion_notify_event', self._hoverCallback),
                                self._plotWidget.canvas.mpl_connect('button_press_event', self._mouseClickCallback),
                                self._plotWidget.canvas.mpl_connect('key_press_event', self._keyPressCallback),
                                self._plotWidget.canvas.mpl_connect('key_release_event', self._keyReleaseCallback)]
        else:
            if self._toggleCids:
                [self._plotWidget.canvas.mpl_disconnect(cid) for cid in self._toggleCids]

    def showRois(self):
        pattern = self.roiFilter.currentText()
        self._clearRois()
        for name, num, fformat in self.metadata.getRois():
            if re.fullmatch(pattern, name):
                try:
                    self._addPolygonForRoi(self._roiManager.getROI(self.metadata, name, num))
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to load Roi with name: {name}, number: {num}, format: {fformat.name}")
                    logger.exception(e)
        self._plotWidget.canvas.draw_idle()

    # Signal handlers for RoiManager
    def _onRoiRemoved(self, roiFile: pwsdt.RoiFile):  # This is most likely triggered by this widget's own actions, but it could also be external modification of the roiManager
        if self.metadata == roiFile.acquisition:  # ROI belongs to the currently displayed ROI
            self._removePolygonForRoi(roiFile)
            self._plotWidget.canvas.draw_idle()

    def _onRoiUpdated(self, roiFile: pwsdt.RoiFile):
        if self.metadata == roiFile.acquisition:  # ROI belongs to the currently displayed ROI
            self._removePolygonForRoi(roiFile)
            self._addPolygonForRoi(roiFile)
            self._plotWidget.canvas.draw_idle()

    def _onRoiCreated(self, roiFile: pwsdt.RoiFile, mayHaveBeenOverwrite: bool):
        if self.metadata == roiFile.acquisition:  # ROI belongs to the currently displayed ROI
            if mayHaveBeenOverwrite:
                for param in self.rois:
                    if roiFile is param.roiFile:
                        self._removePolygonForRoi(roiFile)
                        break
            self._addPolygonForRoi(roiFile)
            self._plotWidget.canvas.draw_idle()

    def _hoverCallback(self, event):  # Show an annotation about the ROI when the mouse hovers over it.
        def update_annot(roiFile: pwsdt.RoiFile, poly: PathPatch):
            self.annot.xy = poly.get_path().vertices.mean(axis=0)  # Set the location to the center of the polygon.
            text = f"{roiFile.name}, {roiFile.number}"
            if self.metadata.pws:  # A day may come where fluorescence is not taken on the same camera as pws, in this case we will have multiple pixel sizes and ROI handling will need an update. for now just assume we'll use PWS pixel size
                if self.metadata.pws.pixelSizeUm:  # For some systems (nanocytomics) this is None
                    text += f"\n{self.metadata.pws.pixelSizeUm ** 2 * np.sum(roiFile.getRoi().mask):.2f} $μm^2$"
            self.annot.set_text(text)
            self.annot.get_bbox_patch().set_alpha(0.4)

        vis = self.annot.get_visible()  # Is the annotation already being shown?
        if event.inaxes == self._plotWidget.ax:  # The event takes place in the axes of this widget.
            for params in self.rois:
                contained, _ = params.polygon.contains(event)
                if contained:
                    if not vis:  # If we aren't already showing the annotation then show it for the currently hovered ROI.
                        update_annot(params.roiFile, params.polygon)
                        self.annot.set_visible(True)
                        self._plotWidget.canvas.draw_idle()
                    return
            if vis:  # If we got here then no hover actions were found. If an annotation is currently being shown turn off the annotation.
                self.annot.set_visible(False)
                self._plotWidget.canvas.draw_idle()

    def _keyPressCallback(self, event: KeyEvent):
        key = event.key.lower()
        if key == 'a':  # Select/Deselect All
            self._selectAllFunc()
        elif key == 'm':  # Modify ROI
            selected = [param for param in self.rois if param.selected]
            if len(selected) != 1:
                return  # Only can be done for a single selection.
            self._editFunc(selected[0])
        elif key == 's':  # Shift/rotate
            self._moveRoisFunc()

    def _keyReleaseCallback(self, event: KeyEvent):
        pass

    def _mouseClickCallback(self, event: MouseEvent):
        # Determine if a ROI was clicked on
        _ = [param for param in self.rois if param.polygon.contains(event)[0]]
        if len(_) > 0:
            selectedROIParam = _[0]  # There should have only been one roiFile clicked on. select the first one from the list (hopefully only one there anyway)
        else:
            selectedROIParam = None  # No Roi was clicked

        if event.button == 1:  # Left click
            exclusive = not (Qt.ControlModifier & QApplication.keyboardModifiers())  # If control isn't being pressed then change to only select this one ROI. the QApplication method returns a bitmask of Qt.KeyboardModifiers
            if exclusive:
                self._setAllRoisSelected(False)
            if selectedROIParam is not None:  # Didn't click on an ROI
                self._setRoiSelected(selectedROIParam)
            self._plotWidget.canvas.draw_idle()
        if event.button == 3:  # "3" is the right button
            self._showRightClickMenu(selectedROIParam)

    def _addPolygonForRoi(self, roiFile: pwsdt.RoiFile):
        roi = roiFile.getRoi()
        if roi.verts is not None:
            poly: PathPatch = descartes.PolygonPatch(roi.polygon, facecolor=(1, 0, 0, 0.5), linewidth=1, edgecolor=(0, 1, 0, 0.9))
            poly.set_picker(0)  # allow the polygon to trigger a pickevent
            self._plotWidget.ax.add_patch(poly)
            self.rois.append(RoiParams(roiFile, poly, False))

    def _removePolygonForRoi(self, roiFile: pwsdt.RoiFile):
        parm = None
        for param in self.rois:
            if param.roiFile is roiFile:
                param.polygon.remove()
                parm = param
        if parm is None:  # No matching roiParam was found, that ain't right.
            raise ValueError(f"RoiPlot did not find a RoiParam matching RoiFile: {roiFile}")
        else:
            self.rois.remove(parm)

    def _clearRois(self):
        for param in self.rois:
            param.polygon.remove()
        self.rois = []

    def _exportAction(self):
        def showSinCityDlg():
            dlg = SinCityDlg(self, self)
            dlg.show()
        menu = QMenu("Export Menu")
        act = QAction("Colored Nuclei")
        act.triggered.connect(showSinCityDlg)
        menu.addAction(act)
        menu.exec(self.mapToGlobal(self.exportButton.pos()))

    def _showRightClickMenu(self, selectedROIParam: RoiParams):
        """

        Args:
         selectedROIParam: The ROI params associated with the ROI that was clicked on.
        """
        # Actions that can happen even if no ROI was clicked on.
        def deleteFunc():
            for param in tuple(self.rois): # Create a tuple copy of the list since self.rois will be modified as we loop which causes weird behavior.
                if param.selected:
                    self._roiManager.removeRoi(param.roiFile)  # Signals emitted here will causes the necesarry UI updates.
                    self.roiDeleted.emit(self.metadata, param.roiFile)

        def copyFunc():
            d = {}
            for param in self.rois:
                if param.selected:
                    roiFile = param.roiFile
                    d[(roiFile.name, roiFile.number)] = roiFile.getRoi()
            mimeData = QMimeData()
            mimeData.setData('pickleRoi', pickle.dumps(d))
            QApplication.clipboard().setMimeData(mimeData)

        def pasteFunc():
            try:
                b = QApplication.clipboard().mimeData().data('pickleRoi')
                d: dict = pickle.loads(b)
                for k, v in d.items():
                    try:
                        roiFile = self._roiManager.createRoi(self.metadata, v, k[0], k[1], overwrite=False)
                        self.roiCreated.emit(self.metadata, roiFile)
                    except OSError:
                        logging.getLogger(__name__).info(f"Attempting to paste and ROI that already exists. Cannot Overwrite. {v.name}, {v.number}")
            except Exception as e:
                QMessageBox.information(self, "Nope", 'Pasting Failed. See the log.')
                logging.getLogger(__name__).exception(e)

        popMenu = QMenu(self)
        deleteAction = popMenu.addAction("Delete Selected ROIs", deleteFunc)
        moveAction = popMenu.addAction("(S)hift/Rotate Selected ROIs", self._moveRoisFunc)
        selectAllAction = popMenu.addAction("De/Select (A)ll", self._selectAllFunc)
        copyAction = popMenu.addAction("Copy ROIs", copyFunc)
        pasteAction = popMenu.addAction("Paste ROIs", pasteFunc)

        if not any([roiParam.selected for roiParam in self.rois]):  # If no rois are selected then some actions can't be performed
            deleteAction.setEnabled(False)
            moveAction.setEnabled(False)
            copyAction.setEnabled(False)

        moveAction.setToolTip(MovingModifier.getHelpText())
        popMenu.setToolTipsVisible(True)

        if selectedROIParam is not None:
            # Actions that require that a ROI was clicked on.
            popMenu.addSeparator()
            popMenu.addAction("(M)odify", lambda sel=selectedROIParam: self._editFunc(sel))

        cursor = QCursor()
        popMenu.popup(cursor.pos())

    def _moveRoisFunc(self):
        """Callback triggered from right click or key press"""
        coordSet = []
        selectedROIParams = []
        for param in self.rois:
            if param.selected:
                selectedROIParams.append(param)
                coordSet.append(param.roiFile.getRoi().verts)
        if len(selectedROIParams) == 0:  # Nothing to do
            return

        def done(vertsSet, handles):
            self._polyWidg.set_active(False)
            self._polyWidg.set_visible(False)
            for param, verts in zip(selectedROIParams, vertsSet):
                newRoi = pwsdt.Roi.fromVerts(np.array(verts),
                                             param.roiFile.getRoi().mask.shape)
                self._roiManager.updateRoi(param.roiFile, newRoi)
                self.roiModified.emit(self.metadata, param.roiFile)

            self.enableHoverAnnotation(True)

        def cancelled():
            self.enableHoverAnnotation(True)

        self.enableHoverAnnotation(False)  # This should be reenabled when the widget is finished or cancelled.
        self._polyWidg = MovingModifier(self.ax, onselect=done, onCancelled=cancelled)
        self._polyWidg.set_active(True)
        self._polyWidg.initialize(coordSet)

    def _selectAllFunc(self):
        """Callback triggered by right click or key press"""
        sel = not any([param.selected for param in self.rois])  # Determine whether to select or deselect all
        self._setAllRoisSelected(sel)
        self._plotWidget.canvas.draw_idle()

    def _editFunc(self, selectedROIParam: RoiParams):
        """Callback triggered by right click or key press, required a selected Roi"""
        # extract handle points from the polygon
        poly = shapelyPolygon(selectedROIParam.roiFile.getRoi().verts)
        poly = poly.buffer(0)
        poly = poly.simplify(poly.length ** .5 / 5, preserve_topology=False)
        handles = poly.exterior.coords

        def done(verts, handles):
            verts = verts[0]
            newRoi = pwsdt.Roi.fromVerts(np.array(verts), selectedROIParam.roiFile.getRoi().mask.shape)
            self._polyWidg.set_active(False)
            self._polyWidg.set_visible(False)
            self._roiManager.updateRoi(selectedROIParam.roiFile, newRoi)
            self.roiModified.emit(self.metadata, selectedROIParam.roiFile)

            self.enableHoverAnnotation(True)

        def cancelled():
            self.enableHoverAnnotation(True)

        self._polyWidg = PolygonModifier(self.ax, onselect=done, onCancelled=cancelled)
        self._polyWidg.set_active(True)
        self.enableHoverAnnotation(False)
        self._polyWidg.initialize([handles])


class WhiteSpaceValidator(QValidator):
    stateChanged = QtCore.pyqtSignal(QValidator.State)

    def __init__(self):
        super().__init__()
        self.state = QValidator.Acceptable

    def validate(self, inp: str, pos: int):
        oldState = self.state
        inp = self.fixup(inp)
        self.state = QValidator.Acceptable
        if self.state != oldState: self.stateChanged.emit(self.state)
        return self.state, inp, pos

    def fixup(self, a0: str) -> str:
        return a0.strip()

