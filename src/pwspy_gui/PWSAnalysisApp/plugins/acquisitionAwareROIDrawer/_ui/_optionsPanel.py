from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtWidgets import QFrame, QWidget, QCheckBox, QPushButton, QVBoxLayout, QLabel
from pwspy_gui.PWSAnalysisApp.plugins.acquisitionAwareROIDrawer._control import Options
import typing as t_


class OptionsPanel(QWidget):
    animateTimerFired = pyqtSignal(int)
    optionsChanged = pyqtSignal(int, Options)

    def __init__(self, initialOptions: t_.Sequence[Options], parent: QWidget = None):
        super().__init__(parent=parent)
        l = QVBoxLayout()
        self._subPanels = []
        for i, option in enumerate(initialOptions):
            w = _SingleOptionPanel(self, option)
            w.optionsChanged.connect(lambda option, ii=i: self.optionsChanged.emit(ii, option))
            w.animateTimerFired.connect(lambda ii=i: self.animateTimerFired.emit(ii))
            self._subPanels.append(w)
            l.addWidget(w)
        l.addWidget(QWidget(parent=self), stretch=1)  # This widget just pushes the others upwards.
        self.setLayout(l)

    def getOptions(self, axis: int) -> Options:
        return self._subPanels[axis].getOptions()

    def setOptions(self, axis: int, options: Options):
        self._subPanels[axis].setOptions(options)


class _SingleOptionPanel(QFrame):
    animateTimerFired = pyqtSignal()
    optionsChanged = pyqtSignal(Options)

    def __init__(self, parent: QWidget = None, initialOptions: Options = None):
        super().__init__(parent=parent)
        self._copyTimeCB = QCheckBox("Copy ROI changes along axis", parent=self)
        self._copyTimeCB.stateChanged.connect(lambda: self.optionsChanged.emit(self.getOptions()))
        # self._trackImCB = QCheckBox("Track cell movement", parent=self)
        # self._trackImCB.stateChanged.connect(lambda: self.optionsChanged.emit(self.getOptions()))
        self._animateBtn = QPushButton("Animate axis", parent=self)
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
            copyAlong=self._copyTimeCB.isChecked(),
            trackMovement=False)  # self._trackImCB.isChecked())

    def setOptions(self, options: Options):
        self._copyTimeCB.setChecked(options.copyAlong)
        # self._trackImCB.setChecked(options.trackMovement)