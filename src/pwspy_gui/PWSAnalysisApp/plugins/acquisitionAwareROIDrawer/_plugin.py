from __future__ import annotations
import typing as t_
import warnings
import logging
from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget, QApplication, QInputDialog, QMessageBox
from pwspy_gui.PWSAnalysisApp.App import PWSApp

from pwspy_gui.PWSAnalysisApp.pluginInterfaces import CellSelectorPlugin
import os

from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._control import SequenceController

from ._ui import SeqRoiDrawer
from pwspy.utility.acquisition.sequencerCoordinate import SequencerCoordinateRange, SeqAcqDir
from pwspy.utility.acquisition.steps import SequencerStep
from pwspy.utility.acquisition import RuntimeSequenceSettings
import pwspy.dataTypes as pwsdt
if t_.TYPE_CHECKING:
    from pwspy_gui.PWSAnalysisApp.componentInterfaces import CellSelector


class AcquisitionAwareRoiDrawerPlugin(CellSelectorPlugin):
    def __init__(self):
        self._selector: CellSelector = None
        self._parentWidget: QWidget = None
        self._ui: SeqRoiDrawer = None

    def setContext(self, selector: CellSelector, parent: QWidget):
        """set the CellSelector that this plugin is associated to."""
        self._selector = selector
        self._parentWidget = parent

    def onCellsSelected(self, cells: t_.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that it has had new cells selected."""
        pass

    def onReferenceSelected(self, cell: pwsdt.AcqDir):
        """This method will be called when the CellSelector indicates that it has had a new reference selected."""
        pass

    def onNewCellsLoaded(self, cells: t_.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that new cells have been loaded to the selector."""
        pass

    def getName(self) -> str:
        """The name to refer to this plugin by."""
        return "Sequence ROI Drawing"

    def onPluginSelected(self):
        """This method will be called when the plugin is activated."""
        cells = self._selector.getAllCellMetas()
        if len(cells) == 0:
            QMessageBox.information(self._parentWidget, "Hmm", "No images are loaded.")
            return
        sequence, acqs = self._loadFromAcqs(cells)

        anName, ok = QInputDialog.getText(self._parentWidget, 'Analysis Name', 'Please input the analysis name', text='p0')
        if not ok:  # Must have been cancelled.
            return
        controller = SequenceController(sequence, acqs)
        mds = []
        for sacq in acqs:
            acq = sacq.acquisition
            pwsAn = None
            dynAn = None
            if acq.pws is not None:
                if anName in acq.pws.getAnalyses():
                    pwsAn = acq.pws.loadAnalysis(anName)
            if acq.dynamics is not None:
                if anName in acq.dynamics.getAnalyses():
                    dynAn = acq.dynamics.loadAnalysis(anName)
            mds.append((sacq, (pwsAn, dynAn)))
        self._ui = SeqRoiDrawer(controller, mds, roiManager=PWSApp.instance().roiManager, parent=self._parentWidget)
        self._ui.show()

    def additionalColumnNames(self) -> t_.Sequence[str]:
        """The header names for each column."""
        return tuple()

    def getTableWidgets(self, acq: pwsdt.AcqDir) -> t_.Sequence[QWidget]:
        """provide a widget for each additional column to represent `acq`"""
        return tuple()


    def _loadFromAcqs(self, acqs: t_.Sequence[pwsdt.AcqDir]) -> t_.Tuple[SequencerStep, t_.Tuple[SeqAcqDir, ...]]:
        commonPath = os.path.commonpath([acq.filePath for acq in acqs])
        logger = logging.getLogger(__name__)
        logger.debug(f"New cells loaded at common path: {commonPath}")
        for i in range(3):  # Look up to 3 parent directories for a valid sequence file.
            try:
                sequenceRoot = RuntimeSequenceSettings.fromJsonFile(commonPath)
                logger.debug(f"Loaded sequence file at {commonPath}")
                if sequenceRoot.uuid is None:
                    warnings.warn(
                        "Old acquisition sequence file must have been loaded. No UUID found. Acquisitions returned by this function may not actually belong to this sequence.")
            except FileNotFoundError:
                commonPath = os.path.split(commonPath)[0]  # Go up one directory
                logger.debug(f"No sequence file found. Trying again at: {commonPath}")
                continue

            foundAcqs = []  # We only get here if a sequence file was found.
            for f in acqs:
                try:
                    foundAcqs.append(SeqAcqDir(f))
                except FileNotFoundError:
                    pass  # There may be "Cell" folders that don't contain a sequencer coordinate.
            foundAcqs = [acq for acq in foundAcqs if acq.sequencerCoordinate.uuid == sequenceRoot.uuid]  # Filter out acquisitions that don't have a matching UUID to the sequence file.
            logger.debug(f"Successfully loaded {len(foundAcqs)} sequenced acquisitions.")
            return sequenceRoot.rootStep, tuple(foundAcqs)
