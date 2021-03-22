from __future__ import annotations
import typing
import warnings
import logging
from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget, QApplication

from pwspy_gui.PWSAnalysisApp.pluginInterfaces import CellSelectorPlugin
import os

from ._ui.widget import SequenceViewer
from pwspy.utility.acquisition.sequencerCoordinate import SequencerCoordinateRange, SeqAcqDir
from pwspy.utility.acquisition.steps import SequencerStep
from pwspy.utility.acquisition import RuntimeSequenceSettings
from pwspy.dataTypes import AcqDir
if typing.TYPE_CHECKING:
    from pwspy_gui.PWSAnalysisApp.componentInterfaces import CellSelector


def requirePluginActive(method):
    """A decorator that only runs the decorated function if the plugin UI is open"""
    def newMethod(self, *args, **kwargs):
        if self._ui.isVisible():  # If the ui isn't visible then we consider the plugin to be off.
            method(self, *args, **kwargs)
    return newMethod


class AcquisitionSequencerPlugin(CellSelectorPlugin):
    def __init__(self):
        self._selector: CellSelector = None
        self._sequence: SequencerStep = None
        self._cells: typing.List[SeqAcqDir] = None
        self._ui = SequenceViewer()
        self._ui.newCoordSelected.connect(self._updateSelectorSelection)

    def setContext(self, selector: CellSelector, parent: QWidget):
        """set the CellSelector that this plugin is associated to."""
        self._selector = selector
        self._ui.setParent(parent)
        self._ui.setWindowFlags(QtCore.Qt.Window)  # Without this is just gets added to the main window in a weird way.

    @requirePluginActive
    def onCellsSelected(self, cells: typing.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that it has had new cells selected."""
        pass

    @requirePluginActive
    def onReferenceSelected(self, cell: pwsdt.AcqDir):
        """This method will be called when the CellSelector indicates that it has had a new reference selected."""
        pass

    @requirePluginActive
    def onNewCellsLoaded(self, cells: typing.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that new cells have been loaded to the selector."""
        sequence, acqs = self._loadNewSequence(cells)
        self._sequence = sequence
        self._cells = acqs
        if sequence is not None:
            self._ui.setSequenceStepRoot(self._sequence)


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

    def _updateSelectorSelection(self, coordRange: SequencerCoordinateRange):
        select: typing.List[AcqDir] = []
        for cell in self._cells:
            if cell.sequencerCoordinate in coordRange:
                select.append(cell.acquisition)
        self._selector.setSelectedCells(select)

    def _loadNewSequence(self, cells: typing.Sequence[pwsdt.AcqDir]) -> typing.Tuple[SequencerStep, typing.Sequence[SeqAcqDir]]:
        if len(cells) == 0:  # This causes a crash
            return None, None
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
            foundAcqs = [acq for acq in foundAcqs if acq.acquisition.filePath in cellFilePaths]  # TODo what is the purpose of this
            sequence = sequenceRoot.rootStep
            return sequence, foundAcqs
        return None, None  # Nothing was found

if __name__ == '__main__':
    from pwspy_gui.PWSAnalysisApp.plugins.acquisitionSequencer._ui.TreeView import MyTreeView

    with open(r'C:\Users\nicke\Desktop\data\toast2\sequence.pwsseq') as f:
        s = SequencerStep.fromJson(f.read())
    import sys
    from pwspy import dataTypes as pwsdt
    from glob import glob

    acqs = [pwsdt.AcqDir(i) for i in glob(r"C:\Users\nicke\Desktop\data\toast2\Cell*")]
    sacqs = [SeqAcqDir(acq) for acq in acqs]

    import sys

    app = QApplication(sys.argv)


    view = MyTreeView()
    view.setRoot(s)

    view.setWindowTitle("Simple Tree Model")
    view.show()
    sys.exit(app.exec_())


    app = QApplication(sys.argv)

    W = QWidget()
    W.setLayout(QHBoxLayout())

    w = QTreeWidget()
    w.setColumnCount(2)
    w.addTopLevelItem(s)
    w.setIndentation(10)

    w2 = DictTreeView()
    w2.setColumnCount(2)
    w2.setIndentation(10)


    w.itemClicked.connect(lambda item, column: w2.setDict(item.settings))

    W.layout().addWidget(w)
    W.layout().addWidget(w2)


    W.show()
    app.exec()
    a = 1
