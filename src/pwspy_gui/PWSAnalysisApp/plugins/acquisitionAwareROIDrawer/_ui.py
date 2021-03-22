from __future__ import annotations

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QTimer
from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._control import SequenceController, Options, RoiController

from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiDrawer
from PyQt5.QtWidgets import QWidget, QButtonGroup, QPushButton, QHBoxLayout, QVBoxLayout, QCheckBox, QLabel, QFrame
import typing as t_

if t_.TYPE_CHECKING:
    from pwspy.analysis.pws import PWSAnalysisResults
    from pwspy.analysis.dynamics import DynamicsAnalysisResults
    from pwspy.utility.acquisition import SeqAcqDir
    import pwspy.dataTypes as pwsdt

    AnalysisResultsComboType = t_.Tuple[
            t_.Optional[PWSAnalysisResults],
            t_.Optional[DynamicsAnalysisResults]]


class SeqRoiDrawer(QWidget):
    def __init__(self, controller: SequenceController, metadatas: t_.List[t_.Tuple[SeqAcqDir, t_.Optional[AnalysisResultsComboType]]], parent: QWidget = None, flags=QtCore.Qt.Window):
        super().__init__(parent=parent, flags=flags)
        self.setWindowTitle("Sequence-Aware ROI Drawer")
        self._seqController = controller
        self._roiController = RoiController(self._seqController, initialOptions=Options(False, False), parent=self)

        self._drawer = RoiDrawer(metadatas=[(seqAcq.acquisition, anResults) for seqAcq, anResults in metadatas], parent=self, flags=QtCore.Qt.Widget)  # Override the default behavior of showing as it's own window.
        self._drawer.metadataChanged.connect(self._drawMetaDataChangeUnprompted)
        self._drawer.roiCreated.connect(lambda acq, roi, overwrite: self._roiController.setRoiChanged(acq, roi, overwrite))
        self._drawer.roiDeleted.connect(self._roiController.deleteRoi)
        self._drawer.roiModified.connect(lambda acq, roi: self._roiController.setRoiChanged(acq, roi, True))
        self._ignoreDrawerSignals = False

        self._optionsPanel = OptionsPanel(parent=self, initialOptions=self._roiController.getOptions())
        self._optionsPanel.animateTimerFired.connect(self._handleAnimationEvent)
        self._optionsPanel.optionsChanged.connect(self._roiController.setOptions)


        l = QVBoxLayout()

        self._positionsBar: ButtonBar
        if controller.getPositionNames() is not None:
            self._positionsBar = ButtonBar(controller.getPositionNames(), self)
            self._positionsBar.buttonClicked.connect(self.setAcquisition)
            l.addWidget(self._positionsBar)
        else:
            self._positionsBar = None

        self._timesBar: ButtonBar
        if controller.getTimeNames() is not None:
            self._timesBar = ButtonBar(controller.getTimeNames(), self)
            self._timesBar.buttonClicked.connect(self.setAcquisition)
            l.addWidget(self._timesBar)
        else:
            self._timesBar = None

        ll = QHBoxLayout()
        ll.addWidget(self._drawer, stretch=1)  # Hog as much space as possible.
        ll.addWidget(self._optionsPanel)

        lll = QVBoxLayout(self)
        lll.addLayout(ll, stretch=1)
        lll.addLayout(l)
        self.setLayout(lll)

        self._buttonBars = (self._positionsBar, self._timesBar)

    def setAcquisition(self):
        posIndex = self._positionsBar.getSelectedButtonId() if self._positionsBar is not None else None
        timeIndex = self._timesBar.getSelectedButtonId() if self._timesBar is not None else None
        acq = self._seqController.setCoordinates(posIndex, timeIndex)
        self._ignoreDrawerSignals = True
        self._drawer.setDisplayedAcquisition(acq.acquisition)
        self._ignoreDrawerSignals = False

    def _handleAnimationEvent(self):
        if self._timesBar is None:
            return
        self._timesBar.selectNextButton()

    def _drawMetaDataChangeUnprompted(self, acq: pwsdt.AcDir):
        if not self._ignoreDrawerSignals:
            tIdx, pIdx = self._seqController.getIndicesForAcquisition(acq)
            if self._positionsBar is not None:
                self._positionsBar.setButtonSelected(pIdx)
            if self._timesBar is not None:
                self._timesBar.setButtonSelected(tIdx)


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

    def selectNextButton(self):
        id = self._selectedButtonId + 1
        if id >= len(self._bGroup.buttons()):
            id = 0
        self.setButtonSelected(id)

    def setButtonSelected(self, ID: int):
        btn = self._bGroup.button(ID)
        btn.click()


class OptionsPanel(QFrame):
    animateTimerFired = pyqtSignal()
    optionsChanged = pyqtSignal(Options)

    def __init__(self, parent: QWidget = None, initialOptions: Options = None):
        super().__init__(parent=parent)
        self._copyTimeCB = QCheckBox("Copy ROI changes along Time axis", parent=self)
        self._copyTimeCB.stateChanged.connect(lambda: self.optionsChanged.emit(self.getOptions()))
        # self._trackImCB = QCheckBox("Track cell movement", parent=self)
        # self._trackImCB.stateChanged.connect(lambda: self.optionsChanged.emit(self.getOptions()))
        self._animateBtn = QPushButton("Animate Time axis", parent=self)
        self._animateBtn.setCheckable(True)

        self._animateBtn.toggled.connect(self._handleAnimateCheck)
        self._animateTimer = QTimer(self)
        self._animateTimer.setInterval(100)
        self._animateTimer.setSingleShot(False)
        self._animateTimer.timeout.connect(self.animateTimerFired.emit)

        l = QVBoxLayout()
        label = QLabel("Options:")
        f = label.font()
        f.setBold(True)
        label.setFont(f)
        l.addWidget(label)
        l.addWidget(self._copyTimeCB)
        # l.addWidget(self._trackImCB)
        l.addWidget(self._animateBtn)
        l.addWidget(QWidget(self), stretch=1)  # This pushes everything up to the top.
        self.setLayout(l)
        self.setFrameStyle(QFrame.Box)

        if initialOptions is not None:
            self.setOptions(initialOptions)

    def _handleAnimateCheck(self, checked: bool):
        if checked:
            self._animateTimer.start()
        else:
            self._animateTimer.stop()

    def getOptions(self) -> Options:
        return Options(
            copyAlongTime=self._copyTimeCB.isChecked(),
            trackMovement=False)  # self._trackImCB.isChecked())

    def setOptions(self, options: Options):
        self._copyTimeCB.setChecked(options.copyAlongTime)
        # self._trackImCB.setChecked(options.trackMovement)


if __name__ == '__main__':
    from pwspy.utility.acquisition import loadDirectory
    from PyQt5.QtWidgets import QApplication
    import sys
    # d = r'\\BackmanLabNAS\home\Year3\KuriosBandwidth\data' # Positions only experiment
    d = r'\\BackmanLabNAS\Public\surbhi_nick_share\MCF10A D-Ala media auto' # Time series and positions
    sequence, acqs = loadDirectory(d)
    cont = SequenceController(sequence, acqs)

    app = QApplication(sys.argv)
    drawer = SeqRoiDrawer(cont, [(acq, (None, None)) for acq in acqs])
    drawer.show()
    app.exec()
    a = 1