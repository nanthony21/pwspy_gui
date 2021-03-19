from __future__ import annotations
import typing as t_
import warnings
import logging
from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget, QApplication, QInputDialog

from pwspy_gui.PWSAnalysisApp.pluginInterfaces import CellSelectorPlugin
import os

from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._control import SequenceController

from ._ui import SeqRoiDrawer
from pwspy.utility.acquisition.sequencerCoordinate import SequencerCoordinateRange, SeqAcqDir
from pwspy.utility.acquisition.steps import SequencerStep
from pwspy.utility.acquisition import RuntimeSequenceSettings, loadDirectory
from pwspy.dataTypes import AcqDir
if typing.TYPE_CHECKING:
    from pwspy_gui.PWSAnalysisApp.componentInterfaces import CellSelector


class AcquisitionAwareRoiDrawerPlugin(CellSelectorPlugin):
    def __init__(self):
        self._selector: CellSelector = None
        self._sequence: SequencerStep = None
        self._cells: typing.List[SeqAcqDir] = None
        self._ui = None

    def setContext(self, selector: CellSelector, parent: QWidget):
        """set the CellSelector that this plugin is associated to."""
        self._selector = selector
        anName = QInputDialog.getText(parent=parent, title='Analysis Name', label='Please input the analysis name', text='p0')
        acqs = selector.getSelectedCellMetas()

        loadDirectory()
        controller = SequenceController()
        self._ui = SeqRoiDrawer()
        self._ui.setParent(parent)
        self._ui.setWindowFlags(QtCore.Qt.Window)  # Without this is just gets added to the main window in a weird way.

    def onCellsSelected(self, cells: typing.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that it has had new cells selected."""
        pass

    def onReferenceSelected(self, cell: pwsdt.AcqDir):
        """This method will be called when the CellSelector indicates that it has had a new reference selected."""
        pass

    def onNewCellsLoaded(self, cells: typing.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that new cells have been loaded to the selector."""
        if len(cells) == 0:  # This causes a crash
            return
        cellFilePaths = [acq.filePath for acq in cells]

        #Search the parent directory for a `sequence.pwsseq` file containing the sequence information.
        paths = [i.filePath for i in cells]
        commonPath = os.path.commonpath(paths)
        logger = logging.getLogger(__name__)
        logger.debug(f"New cells loaded at common path: {commonPath}")
        # We will search up to 3 parent directories for a sequence file
        for i in range(3):
            try:
                sequenceRoot = RuntimeSequenceSettings.fromJsonFile(commonPath)
                if sequenceRoot.uuid is None:
                    warnings.warn("Old acquisition sequence file must have been loaded. No UUID found. Acquisitions returned by this function may not actually belong to this sequence.")
            except FileNotFoundError:
                commonPath = os.path.split(commonPath)[0]  # Go up one directory
                logger.debug(f"No sequence file found. Trying again at: {commonPath}")
                continue

            foundAcqs = []
            for f in cells:
                try:
                    foundAcqs.append(SeqAcqDir(f))
                except FileNotFoundError:
                    pass  # There may be "Cell" folders that don't contain a sequencer coordinate.
            foundAcqs = [acq for acq in foundAcqs if acq.sequencerCoordinate.uuid == sequenceRoot.uuid]  # Filter out acquisitions that don't have a matching UUID to the sequence file.
            logger.debug(f"Successfully loaded {len(foundAcqs)} sequenced acquisitions.")
            self._cells = [acq for acq in foundAcqs if acq.acquisition.filePath in cellFilePaths]
            self._sequence = sequenceRoot.rootStep
            self._ui.setSequenceStepRoot(self._sequence)
            return
        # We only get this far if the sequence file search fails.
        self._sequence = None
        self._cells = None

    def getName(self) -> str:
        """The name to refer to this plugin by."""
        return "Acquisition Sequence Selector"

    def onPluginSelected(self):
        """This method will be called when the plugin is activated."""
        self._ui.show()  # We use ui visibility to determine if the plugin is active or not.
        self.onNewCellsLoaded(self._selector.getAllCellMetas())  # Make sure we're all up to date

    def additionalColumnNames(self) -> typing.Sequence[str]:
        """The header names for each column."""
        return tuple() #return "Coord. Type", "Coord. Value" # We used to add new columns, but it was confusing, better not to.

    def getTableWidgets(self, acq: pwsdt.AcqDir) -> typing.Sequence[QWidget]:  #TODO this gets called before the sequence has been loaded. Make it so this isn't required for constructor of cell table widgets.
        """provide a widget for each additional column to represent `acq`"""
        return tuple()
        # typeNames = {SequencerStepTypes.POS.name: "Position", SequencerStepTypes.TIME.name: "Time", SequencerStepTypes.ZSTACK.name: "Z Stack"}
        # try:
        #     acq = SeqAcqDir(acq)
        # except:
        #     return tuple((QTableWidgetItem(), QTableWidgetItem()))
        # coord = acq.sequencerCoordinate
        # idx, iteration = [(i, iteration) for i, iteration in enumerate(coord.iterations) if iteration is not None][-1]
        # for step in self._sequence.iterateChildren():
        #     if step.id == coord.ids[idx]:
        #         step: CoordSequencerStep
        #         val = QTableWidgetItem(step.getIterationName(iteration))
        #         t = QTableWidgetItem(typeNames[step.stepType])
        #         return tuple((t, val))
        # return tuple((QTableWidgetItem(), QTableWidgetItem()))  # This will happen if the acquisition has a coords file but the coord isn't actually found in the sequence file.
        #

    def _loadFromAcqs(self, acqs: t_.Sequence[pwsdt.AcqDir]):
        commonpath = os.path.commonpath([acq.filePath for acq in acqs])
        logger = logging.getLogger(__name__)
        logger.debug(f"New cells loaded at common path: {commonPath}")
        for i in range(3):  # Look up to 3 parent directories for a valid sequence file.
            try:
                sequenceRoot = RuntimeSequenceSettings.fromJsonFile(commonPath)
                logger.debug(f"Loaded sequence file at {commonpath}")
                if sequenceRoot.uuid is None:
                    warnings.warn(
                        "Old acquisition sequence file must have been loaded. No UUID found. Acquisitions returned by this function may not actually belong to this sequence.")
            except FileNotFoundError:
                commonPath = os.path.split(commonPath)[0]  # Go up one directory
                logger.debug(f"No sequence file found. Trying again at: {commonPath}")
                continue

            foundAcqs = []  # We only get here
            for f in cells:
                try:
                    foundAcqs.append(SeqAcqDir(f))
                except FileNotFoundError:
                    pass  # There may be "Cell" folders that don't contain a sequencer coordinate.

