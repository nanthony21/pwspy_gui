from __future__ import annotations
import typing as t_
from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from pwspy import dataTypes as pwsdt
from pwspy.utility.acquisition import SeqAcqDir

from pwspy_gui.PWSAnalysisApp._roiManager import _DefaultROIManager
from pwspy_gui.PWSAnalysisApp.componentInterfaces import ROIManager
from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._control import SequenceController, RoiController, Options
from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._ui._buttonBar import ButtonBar
from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._ui._optionsPanel import OptionsPanel
from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiDrawer

if t_.TYPE_CHECKING:
    from pwspy.analysis.dynamics import DynamicsAnalysisResults
    from pwspy.analysis.pws import PWSAnalysisResults
    AnalysisResultsComboType = t_.Tuple[
        t_.Optional[PWSAnalysisResults],
        t_.Optional[DynamicsAnalysisResults]]


class SeqRoiDrawer(QWidget):
    def __init__(self, controller: SequenceController, metadatas: t_.List[t_.Tuple[SeqAcqDir, t_.Optional[AnalysisResultsComboType]]], roiManager: ROIManager, parent: QWidget = None, flags=QtCore.Qt.Window):
        super().__init__(parent=parent, flags=flags)
        self.setWindowTitle("Sequence-Aware ROI Drawer")
        self._seqController = controller

        self._drawer = RoiDrawer(metadatas=[(seqAcq.acquisition, anResults) for seqAcq, anResults in metadatas], roiManager=roiManager, parent=self, flags=QtCore.Qt.Widget)  # Override the default behavior of showing as it's own window.
        self._roiController = RoiController(self._seqController, initialOptions=Options(False, False), roiManager=roiManager, parent=self)

        self._drawer.metadataChanged.connect(self._drawMetaDataChangeUnprompted)
        self._drawer.roiCreated.connect(lambda acq, roi, overwrite: self._roiController.setRoiChanged(acq, roi, overwrite))
        self._drawer.roiDeleted.connect(self._roiController.deleteRoi)
        self._drawer.roiModified.connect(lambda acq, roi: self._roiController.setRoiChanged(acq, roi, True))
        self._ignoreDrawerSignals = False

        self._optionsPanel = OptionsPanel(parent=self, initialOptions=[self._roiController.getOptions(i) for i in range(len(controller.iterSteps))])
        self._optionsPanel.animateTimerFired.connect(self._handleAnimationEvent)
        self._optionsPanel.optionsChanged.connect(self._roiController.setOptions)

        l = QVBoxLayout()

        self._buttonBars = []
        for step in controller.iterSteps:
            bBar = ButtonBar([step.getIterationName(i) for i in range(step.stepIterations())], self)
            bBar.buttonClicked.connect(self.setAcquisition)
            self._buttonBars.append(bBar)
            l.addWidget(bBar)

        ll = QHBoxLayout()
        ll.addWidget(self._drawer, stretch=1)  # Hog as much space as possible.
        ll.addWidget(self._optionsPanel)

        lll = QVBoxLayout(self)
        lll.addLayout(ll, stretch=1)
        lll.addLayout(l)
        self.setLayout(lll)

    def setAcquisition(self):
        idxs = tuple(bBar.getSelectedButtonId() for bBar in self._buttonBars)
        acq = self._seqController.setCoordinates(*idxs)
        self._ignoreDrawerSignals = True
        self._drawer.setDisplayedAcquisition(acq)
        self._ignoreDrawerSignals = False

    def _handleAnimationEvent(self, axis: int):
        self._buttonBars[axis].selectNextButton()

    def _drawMetaDataChangeUnprompted(self, acq: pwsdt.AcqDir):
        if not self._ignoreDrawerSignals:
            idxs = self._seqController.getIndicesForAcquisition(acq)
            for idx, bBar in zip(idxs, self._buttonBars):
                bBar.setButtonSelected(idx)


if __name__ == '__main__':
    from pwspy.utility.acquisition import loadDirectory
    from PyQt5.QtWidgets import QApplication
    import sys
    # d = r'\\BackmanLabNAS\home\Year3\KuriosBandwidth\data' # Positions only experiment
    d = r'\\BackmanLabNAS\Public\surbhi_nick_share\MCF10A D-Ala media auto'  # Time series and positions
    sequence, acqs = loadDirectory(d)
    cont = SequenceController(sequence, acqs)

    app = QApplication(sys.argv)
    roiManager = _DefaultROIManager()
    drawer = SeqRoiDrawer(cont, [(acq, (None, None)) for acq in acqs], roiManager=roiManager)
    drawer.show()
    app.exec()
    a = 1
