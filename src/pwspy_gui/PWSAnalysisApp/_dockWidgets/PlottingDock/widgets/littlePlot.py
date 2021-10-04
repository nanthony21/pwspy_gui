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

import os

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QMenu, QAction, QWidget, QLabel, QVBoxLayout, QApplication
from pwspy_gui.PWSAnalysisApp.utilities.conglomeratedAnalysis import ConglomerateAnalysisResults
from pwspy.dataTypes import Acquisition, PwsCube
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting._widgets import AnalysisPlotter
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting._analysisViewer import AnalysisViewer
from mpl_qt_viz.visualizers import PlotNd


class LittlePlot(AnalysisPlotter, QWidget):
    def __init__(self, acquisition: Acquisition, analysis: ConglomerateAnalysisResults, title: str, text: str = None,
                 initialField=AnalysisPlotter.PlotFields.Thumbnail):
        assert analysis is not None #The member of the conglomerateAnalysisResults can be None but the way this class is written requires that the object itself exists.
        AnalysisPlotter.__init__(self, acquisition, analysis)
        QWidget.__init__(self)
        self.setLayout(QVBoxLayout())
        self.titleLabel = QLabel(title, self)
        self.titleLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.imLabel = QLabel(self)
        self.imLabel.setScaledContents(True)
        self.layout().addWidget(self.titleLabel)
        if text is not None:
            self.textLabel = QLabel(self)
            self.textLabel.setStyleSheet("QLabel {color: #b40000}") #This isn't working for some reason
            self.textLabel.setText(text)
            self.textLabel.setAlignment(QtCore.Qt.AlignCenter)
            self.layout().addWidget(self.textLabel)
        self.layout().addWidget(self.imLabel)
        self.title = title
        self.setMinimumWidth(20)
        self.changeData(initialField)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.plotnd = None #Just a reference to a plotND class instance so it isn't deleted.

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            mainWindow = QApplication.instance().window
            viewer = AnalysisViewer(metadata=self.acq, analysisLoader=self.analysis, title=self.title, roiManager=QApplication.instance().roiManager, parent=mainWindow, initialField=self.analysisField, flags=QtCore.Qt.Window)
            viewer.show()

    def changeData(self, field: AnalysisPlotter.PlotFields):
        AnalysisPlotter.changeData(self, field)
        data = self.data
        data = data - np.percentile(data, 0.1)
        data = (data / np.percentile(data, 99.9) * 255)
        data[data < 0] = 0
        data[data > 255] = 255
        data = data.astype(np.uint8)
        p = QPixmap.fromImage(QImage(data.data, data.shape[1], data.shape[0], data.strides[0], QImage.Format_Grayscale8))
        self.imLabel.setPixmap(p)

    def showContextMenu(self, point: QPoint):
        menu = QMenu("ContextMenu", self)
        menu.setToolTipsVisible(True)
        if self.analysis.pws is not None:
            anPlotAction = QAction("Plot PWS Analyzed Reflectance", self)
            anPlotAction.triggered.connect(self.plotAn3d)
            menu.addAction(anPlotAction)
            if 'reflectance' in self.analysis.pws.file.keys():
                opdAction = QAction("Plot OPD", self)
                opdAction.triggered.connect(self.plotOpd3d)
                menu.addAction(opdAction)
                rmsDepthAction = QAction("Plot RMS-by-OPD", self)
                rmsDepthAction.triggered.connect(self.plotRMSOpd3d)
                rmsDepthAction.setToolTip(self.plotRMSOpd3d.__doc__)
                menu.addAction(rmsDepthAction)
        if self.acq.pws is not None:
            rawPlotAction = QAction("Plot PWS Raw Data", self)
            rawPlotAction.triggered.connect(self.plotRaw3d)
            menu.addAction(rawPlotAction)
        if self.analysis.dyn is not None:
            dynAnPlotAction = QAction("Plot DYN Analyzed Reflectance", self)
            dynAnPlotAction.triggered.connect(self.plotDynAn3d)
            menu.addAction(dynAnPlotAction)
        if self.acq.dynamics is not None:
            dynRawPlotAction = QAction("Plot DYN Raw Data", self)
            dynRawPlotAction.triggered.connect(self.plotDynRaw3d)
            menu.addAction(dynRawPlotAction)
        menu.exec(self.mapToGlobal(point))

    def plotAn3d(self):
        refl = self.analysis.pws.reflectance
        refl += self.analysis.pws.meanReflectance[:, :, None]  # The `reflectance has had the mean subtracted. add it back in.
        self.plotnd = PlotNd(refl.data, title=os.path.split(self.acq.filePath)[-1], names=('y', 'x', 'k (rad/um)'),
                             indices=[range(refl.data.shape[0]), range(refl.data.shape[1]), refl.wavenumbers], parent=self)

    def plotRaw3d(self):
        im = PwsCube.fromMetadata(self.acq.pws)
        self.plotnd = PlotNd(im.data, title=os.path.split(self.acq.filePath)[-1], names=('y', 'x', 'lambda'),
                             indices=[range(im.data.shape[0]), range(im.data.shape[1]), im.wavelengths], parent=self)

    def plotOpd3d(self):
        opd, opdIndex = self.analysis.pws.opd
        self.plotnd = PlotNd(opd, names=('y', 'x', 'um'), title=os.path.split(self.acq.filePath)[-1],
                             indices=[range(opd.shape[0]), range(opd.shape[1]), opdIndex], parent=self)

    def plotRMSOpd3d(self):
        """
        Square root of cumulative sum of OPD^2. Important note: The units are in terms of OPD not depth. Since the light makes a round trip -> depth = OPD / (2 * RI of cell)
        """
        opd: np.ndarray
        opd, opdIndx = self.analysis.pws.opd

        opdSquaredSum = np.cumsum(opd**2, axis=2)  # Parseval's theorem tells us that this is equivalent to the sum of the squares of our original signal. Cumulative sum from 0 up to a given OPD
        opdSquaredSum *= len(self.analysis.pws.reflectance.wavenumbers) / opd.shape[2]  # If the original data and opd were of the same length then the above line would be correct. Since the fft may have been upsampled. we need to normalize.
        rmsByOPD = np.sqrt(opdSquaredSum)

        self.plotnd = PlotNd(rmsByOPD, names=('y', 'x', 'um'), title=os.path.split(self.acq.filePath)[-1],
                             indices=[range(opd.shape[0]), range(opd.shape[1]), opdIndx], parent=self)

    def plotDynAn3d(self):
        refl = self.analysis.dyn.reflectance
        self.plotnd = PlotNd(refl.data, title=os.path.split(self.acq.filePath)[-1],
                             names=('y', 'x', 't'),
                             indices=[range(refl.data.shape[0]), range(refl.data.shape[1]), refl.times], parent=self)

    def plotDynRaw3d(self):
        im = self.acq.dynamics.toDataClass()
        self.plotnd = PlotNd(im.data, title=os.path.split(self.acq.filePath)[-1], names=('y', 'x', 't'),
                             indices=[range(im.data.shape[0]), range(im.data.shape[1]), im.times], parent=self)