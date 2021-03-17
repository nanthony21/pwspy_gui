from __future__ import annotations

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal
from pwspy.utility.acquisition.steps import PositionsStep, TimeStep

from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiDrawer
from PyQt5.QtWidgets import QWidget, QButtonGroup, QPushButton, QHBoxLayout, QVBoxLayout
import typing as t_
import pwspy.dataTypes as pwsdt
import numpy as np
if t_.TYPE_CHECKING:
    from pwspy.analysis.pws import PWSAnalysisResults
    from pwspy.analysis.dynamics import DynamicsAnalysisResults
    from pwspy.utility.acquisition import SeqAcqDir, SequencerStep

    AnalysisResultsComboType = t_.Tuple[
            t_.Optional[PWSAnalysisResults],
            t_.Optional[DynamicsAnalysisResults]]


class SeqRoiDrawer(QWidget):
    def __init__(self, controller: SequenceController, metadatas: t_.List[t_.Tuple[SeqAcqDir, t_.Optional[AnalysisResultsComboType]]], parent: QWidget = None):
        super().__init__(parent=parent)
        self._controller = controller

        self._drawer = RoiDrawer(metadatas=[(seqAcq.acquisition, anResults) for seqAcq, anResults in metadatas], parent=self, flags=QtCore.Qt.Widget)  # Override the default behavior of showing as it's own window.

        l = QVBoxLayout(self)
        l.addWidget(self._drawer)

        if controller.getPositionNames() is not None:
            self._positionsBar = ButtonBar(controller.getPositionNames(), self)
            self._positionsBar.buttonClicked.connect(self.setAcquisition)
            l.addWidget(self._positionsBar)
        else:
            self._positionsBar = None

        if controller.getTimeNames() is not None:
            self._timesBar = ButtonBar(controller.getTimeNames(), self)
            self._timesBar.buttonClicked.connect(self.setAcquisition)
            l.addWidget(self._timesBar)
        else:
            self._timesBar = None

        self._buttonBars = (self._positionsBar, self._timesBar)
        self.setLayout(l)

    def setAcquisition(self):
        posIndex = self._positionsBar.getSelectedButtonId() if self._positionsBar is not None else None
        timeIndex = self._timesBar.getSelectedButtonId() if self._timesBar is not None else None
        acq = self._controller.getAcquisition(posIndex, timeIndex)
        self._drawer.setDisplayedAcquisition(acq.acquisition)


class ButtonBar(QWidget):
    buttonClicked = pyqtSignal(str, int)  # Indicates the iteration number and iteration name of the button that was clicked

    def __init__(self, items: t_.Sequence[str], parent=None):
        super().__init__(parent=parent)
        self._bGroup = QButtonGroup(self)
        l = QHBoxLayout(self)
        for i, itemName in enumerate(items):
            b = QPushButton(itemName, parent=self)
            b.setCheckable(True)  # Toggleable
            self._bGroup.addButton(b, id=i)
            l.addWidget(b)
        self._selectedButtonId = self._bGroup.id(self._bGroup.buttons()[0])
        self._bGroup.buttons()[0].click()  # Make sure at least one button is selected.
        self._bGroup.buttonClicked.connect(self._buttonSelected)
        self.setLayout(l)

    def _buttonSelected(self, btn):
        self._selectedButtonId = self._bGroup.id(btn)
        self.buttonClicked.emit(btn.text(), self._bGroup.id(btn))

    def getSelectedButtonId(self):
        return self._selectedButtonId


class SequenceController:
    """A utility class to help with selected acquisitions from a sequence that includes a multiple position and time series. both are optional"""
    def __init__(self, sequence: SequencerStep, acqs: t_.Sequence[SeqAcqDir]):
        self.sequence = sequence
        self.acqs = acqs
        posSteps = [step for step in sequence.iterateChildren() if isinstance(step, PositionsStep)]
        assert not len(posSteps) > 1, "Sequences with more than one `MultiplePositionsStep` are not currently supported"
        timeSteps = [step for step in sequence.iterateChildren() if isinstance(step, TimeStep)]
        assert not len(timeSteps) > 1, "Sequences with more than one `TimeSeriesStep` are not currently supported"

        self.timeStep = timeSteps[0] if len(timeSteps) > 0 else None
        self.posStep = posSteps[0] if len(posSteps) > 0 else None
        self._iterSteps = (self.timeStep, self.posStep)

    def getTimeNames(self) -> t_.Optional[t_.Sequence[str]]:
        if self.timeStep is None:
            return None
        else:
            return tuple([self.timeStep.getIterationName(i) for i in range(self.timeStep.stepIterations())])

    def getPositionNames(self) -> t_.Optional[t_.Sequence[str]]:
        if self.posStep is None:
            return None
        else:
            return tuple([self.posStep.getIterationName(i) for i in range(self.posStep.stepIterations())])

    def getAcquisition(self, posIndex: t_.Optional[int], tIndex: t_.Optional[int]) -> SeqAcqDir:
        step: SequencerStep = self._iterSteps[np.argmax([len(i.getTreePath()) if i is not None else 0 for i in self._iterSteps])]  # The step that is furthest down the tree path
        coordRange = step.getCoordinate()
        if self.timeStep is not None:
            coordRange.setAcceptedIterations(self.timeStep.id, [tIndex])
        if self.posStep is not None:
            coordRange.setAcceptedIterations(self.posStep.id, [posIndex])
        for acq in self.acqs:
            coord = acq.sequencerCoordinate
            if coord in coordRange:
                return acq

        raise ValueError(f"No acquisition was found to match Position index: {posIndex}, Time index: {tIndex}") # If we got this far then no matching acquisition was found.

if __name__ == '__main__':
    from pwspy.utility.acquisition import loadDirectory
    from PyQt5.QtWidgets import QApplication
    import sys
    d = r'\\BackmanLabNAS\home\Year3\KuriosBandwidth\data'
    sequence, acqs = loadDirectory(d)
    cont = SequenceController(sequence, acqs)

    app = QApplication(sys.argv)
    drawer = SeqRoiDrawer(cont, [(acq, (None, None)) for acq in acqs])
    drawer.show()
    app.exec()
    a = 1