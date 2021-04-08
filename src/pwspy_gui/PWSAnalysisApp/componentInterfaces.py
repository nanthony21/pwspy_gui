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
This module contains Abstract classes used to define the methods that should be implemented by various objects that are central to the PWSAnalysisApp.

@author: Nick Anthony
"""
from __future__ import annotations
import abc
import typing
from typing import List, Optional
import sip
from PyQt5.QtCore import pyqtSignal
from pwspy import dataTypes as pwsdt
from pwspy.dataTypes import RoiFile
from pwspy_gui.PWSAnalysisApp.utilities.conglomeratedAnalysis import ConglomerateCompilerResults, \
    ConglomerateCompilerSettings
if typing.TYPE_CHECKING:
    from pwspy_gui.PWSAnalysisApp._dockWidgets.AnalysisSettingsDock import AbstractRuntimeAnalysisSettings


class QABCMeta(sip.wrappertype, abc.ABCMeta):
    """This metaclass allows us to use abstract classes alongside Qt"""
    pass


class CellSelector(metaclass=QABCMeta):
    @abc.abstractmethod
    def loadNewCells(self, fileNames: List[str], workingDir: str): pass

    @abc.abstractmethod
    def getSelectedCellMetas(self) -> List[pwsdt.AcqDir]: pass

    @abc.abstractmethod
    def getAllCellMetas(self) -> List[pwsdt.AcqDir]: pass

    @abc.abstractmethod
    def getSelectedReferenceMeta(self) -> Optional[pwsdt.AcqDir]: pass

    @abc.abstractmethod
    def setSelectedCells(self, cells: List[pwsdt.AcqDir]): pass

    @abc.abstractmethod
    def setSelectedReference(self, ref: pwsdt.AcqDir): pass

    @abc.abstractmethod
    def setHighlightedCells(self, cells: List[pwsdt.AcqDir]): pass

    @abc.abstractmethod
    def setHighlightedReference(self, ref: pwsdt.AcqDir): pass

    @abc.abstractmethod
    def refreshCellItems(self, cells: List[pwsdt.AcqDir] = None):
        """`Cells` indicates which cells need refreshing. If cells is None then all cells will be refreshed."""
        pass

    @abc.abstractmethod
    def close(self): pass

    @abc.abstractmethod
    def getRoiManager(self) -> ROIManager:
        """Return the ROI manager that manages the saving and loading of ROIs"""
        pass


class ResultsTableController(metaclass=QABCMeta):
    @abc.abstractmethod
    def addCompilationResult(self, result: ConglomerateCompilerResults, acquisition: pwsdt.AcqDir): pass

    @abc.abstractmethod
    def clearCompilationResults(self): pass

    @abc.abstractmethod
    def getSettings(self) -> ConglomerateCompilerSettings: pass

    @abc.abstractmethod
    def getRoiName(self) -> str: pass

    @abc.abstractmethod
    def getAnalysisName(self) -> str: pass


class AnalysisSettingsCreator(metaclass=QABCMeta):
    @abc.abstractmethod
    def getListedAnalyses(self) -> typing.List[AbstractRuntimeAnalysisSettings]: pass


class ROIManager(metaclass=QABCMeta):
    """Handles the actual file saving and retrieval. Any code using this should only modify ROI files through this manager."""

    # Implementation should fire these events afer the deed is done.
    roiRemoved = pyqtSignal(RoiFile)
    roiUpdated = pyqtSignal(RoiFile)
    roiCreated = pyqtSignal(RoiFile, bool)  # bool: May have been an overwrite

    @abc.abstractmethod
    def removeRoi(self, roiFile: pwsdt.RoiFile):
        pass

    @abc.abstractmethod
    def updateRoi(self, roiFile: pwsdt.RoiFile, roi: pwsdt.Roi):
        pass

    @abc.abstractmethod
    def createRoi(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi, roiName: str, roiNumber: int, overwrite: bool = False) -> pwsdt.RoiFile:
        pass

    @abc.abstractmethod
    def getROI(self, acq: pwsdt.AcqDir, roiName: str, roiNum: int) -> pwsdt.RoiFile:
        pass

    @abc.abstractmethod
    def close(self):
        """Make sure all files are wrapped up"""
        pass