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

# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 13:26:58 2019

@author: Nick Anthony
"""
from __future__ import annotations

import logging
import os
import psutil
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from pwspy_gui import __version__ as version
from pwspy_gui.PWSAnalysisApp._roiManager import _DefaultROIManager, ROIManager
from pwspy_gui.PWSAnalysisApp.utilities import BlinderDialog, RoiConverter
from .dialogs import AnalysisSummaryDisplay
from ._taskManagers.analysisManager import AnalysisManager
from .mainWindow import PWSWindow
from . import applicationVars
from . import resources
from pwspy_gui.sharedWidgets.extraReflectionManager import ERManager
from typing import List
import typing
import pwspy.dataTypes as pwsdt


class PWSApp(QApplication):
    def __init__(self, args):
        logger = logging.getLogger(__name__)
        logger.debug("About to call PWSApp superclass constructor")
        super().__init__(args)
        logger.debug("PWSApp superclass constructor is finished")

        self.roiManager: ROIManager = _DefaultROIManager()

        self.setApplicationName(f"PWS Analysis v{version.split('-')[0]}")
        splash = QSplashScreen(QPixmap(os.path.join(resources, 'pwsLogo.png')))
        splash.show()
        logger.debug("Initialize ERManager")
        self.ERManager = ERManager(applicationVars.extraReflectionDirectory)
        logger.debug("Finish constructing ERManager")
        self.window = PWSWindow(self.ERManager, self.roiManager)
        splash.finish(self.window)
        logger.debug("Finish constructing window")
        self.anMan = AnalysisManager(self)
        self.window.runAction.connect(self.anMan.runList)
        availableRamGigs = psutil.virtual_memory().available / 1024**3
        if availableRamGigs > 16:  # Default to parallel analysis if we have more than 16 Gb of ram available.
            self.parallelProcessing = True  # Determines if analysis and compilation should be run in parallel or not.
        else:
            self.parallelProcessing = False  # Determines if analysis and compilation should be run in parallel or not.
        self.window.parallelAction.setChecked(self.parallelProcessing)
        self.window.parallelAction.toggled.connect(lambda checked: setattr(self, 'parallelProcessing', checked))
        logger.info(f"Initializing with useParallel set to {self.parallelProcessing}.")
        self.anMan.analysisDone.connect(lambda name, settings, warningList: AnalysisSummaryDisplay(self.window, warningList, name, settings))
        self.window.fileDialog.directoryChanged.connect(self.changeDirectory)
        self.window.blindAction.triggered.connect(self.openBlindingDialog)
        self.window.roiConvertAction.triggered.connect(self.convertRois)
        self.workingDirectory = None

        # import qdarkstyle  # This looks bad
        # dark_stylesheet = qdarkstyle.load_stylesheet_pyqt5()
        # self.setStyleSheet(dark_stylesheet)

        self.window.show()

    ### API
    def changeDirectory(self, directory: str, recursive: bool):
        from glob import glob
        pattern = [os.path.join('**', 'Cell[0-9]*')] if recursive else ['Cell[0-9]*']
        files = []
        for patt in pattern:
            files.extend(glob(os.path.join(directory, patt), recursive=recursive))
        if len(files) == 0:
            QMessageBox.information(self.window, "Hmm", "No PWS files were found.")
            return
        nums = []
        newFiles = []
        for f in files:
            try:
                nums.append(int(os.path.split(f)[-1].split('Cell')[-1]))
                newFiles.append(f)
            except ValueError:
                pass
        nums, files = zip(*sorted(zip(nums, newFiles)))
        files = list(files)
        # Load Cells
        self.window.cellSelector.loadNewCells(files, directory)
        self.workingDirectory = directory
        #Change title
        self.window.setWindowTitle(f'{QApplication.instance().applicationName()} - {directory}')
        self.workingDirectory = directory

    def openBlindingDialog(self):
        metas = self.window.cellSelector.getSelectedCellMetas()
        if len(metas) == 0:
            QMessageBox.information(self.window, "No Cells Selected", "Please select cells to act upon.")
            return
        dialog = BlinderDialog(self.window, self.workingDirectory, metas)
        dialog.exec()

    def convertRois(self):
        metas = self.window.cellSelector.getSelectedCellMetas()
        if len(metas) == 0:
            QMessageBox.information(self.window, "No Cells Selected", "Please select cells to act upon.")
            return
        rc = RoiConverter(metas)
        self.window.cellSelector.refreshCellItems()

    def setSelectedCells(self, acqs: typing.Sequence[pwsdt.Acquisition]):
        self.window.cellSelector.setSelectedCells(acqs)

    def getSelectedCells(self) -> typing.Sequence[pwsdt.Acquisition]:
        return self.window.cellSelector.getSelectedCellMetas()

    def getLoadedCells(self) -> typing.Sequence[pwsdt.Acquisition]:
        return self.window.cellSelector.getAllCellMetas()

    def plotSelectedCells(self, analysisName: str = None):
        if analysisName is None:
            analysisName = ''
        self.window.plots.setAnalysisName(analysisName)
        self.window.plots.refreshPlots()

    def __del__(self):
        try:
            self.roiManager.close()
        except AttributeError:  # If an error occured in the constructor the attribute may have never been created.
            pass
