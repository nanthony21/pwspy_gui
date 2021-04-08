from __future__ import annotations
import matplotlib
from PyQt5 import QtCore
from PyQt5.QtWidgets import QDialog, QWidget, QVBoxLayout, QDoubleSpinBox, QSpinBox, QPushButton, QGridLayout, QLabel, \
    QHBoxLayout, QMessageBox
from matplotlib.backends.backend_qt5 import NavigationToolbar2QT
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import typing as t_
from pwspy.utility.plotting import roiColor
if t_.TYPE_CHECKING:
    from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiPlot


class SinCityDlg(QDialog):
    def __init__(self, parentRoiPlot: RoiPlot, parent: QWidget = None):
        super().__init__(parent=parent)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowMinMaxButtonsHint)
        # self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowTitleHint | QtCore.Qt.CustomizeWindowHint)  # Get rid of the close button. this is handled by the selector widget active status
        self.setWindowTitle("Sin City Image Export")
        self.setModal(False)

        self.parentRoiPlot = parentRoiPlot
        self.cachedImage = None

        self.fig, self.ax = matplotlib.pyplot.subplots()
        c = FigureCanvasQTAgg(self.fig)
        self.plotWidg = QWidget(self)
        self.plotWidg.setLayout(QVBoxLayout())
        self.plotWidg.layout().addWidget(c)
        self.plotWidg.layout().addWidget(NavigationToolbar2QT(c, self))

        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        self.im = self.ax.imshow(self.parentRoiPlot.getImageData())

        self._paintDebounce = QtCore.QTimer()  # This timer prevents the selectionChanged signal from firing too rapidly.
        self._paintDebounce.setInterval(200)
        self._paintDebounce.setSingleShot(True)
        self._paintDebounce.timeout.connect(self.paint)

        self.vmin = QDoubleSpinBox(self)
        self.vmin.setValue(0)
        self.vmin.setDecimals(3)
        self.vmin.setMaximum(10000)
        self.vmin.setSingleStep(0.001)

        def vminChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.vmin.valueChanged.connect(vminChanged)

        self.vmax = QDoubleSpinBox(self)
        self.vmax.setValue(.1)
        self.vmax.setDecimals(3)
        self.vmax.setMaximum(10000)
        self.vmax.setSingleStep(0.001)

        def vmaxChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.vmax.valueChanged.connect(vmaxChanged)

        self.scaleBg = QDoubleSpinBox(self)
        self.scaleBg.setValue(.33)
        self.scaleBg.setMinimum(0)
        self.scaleBg.setDecimals(2)
        self.scaleBg.setMaximum(3)
        self.scaleBg.setSingleStep(0.01)

        def scaleBgChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.scaleBg.valueChanged.connect(scaleBgChanged)

        self.hue = QDoubleSpinBox(self)
        self.hue.setMinimum(0)
        self.hue.setMaximum(1)
        self.hue.setValue(0)
        self.hue.setSingleStep(0.05)

        def hueRangeChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.hue.valueChanged.connect(hueRangeChanged)

        self.exp = QDoubleSpinBox(self)
        self.exp.setMinimum(0.5)
        self.exp.setMaximum(3)
        self.exp.setValue(1)
        self.exp.setSingleStep(0.05)

        def expRangeChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.exp.valueChanged.connect(expRangeChanged)

        self.scaleBar = QSpinBox(self)
        self.scaleBar.setValue(0)
        self.scaleBar.setMaximum(10000)

        def scaleBarChanged(val):
            self.stale = True
            self._paintDebounce.start()
        self.scaleBar.valueChanged.connect(scaleBarChanged)

        self.refreshButton = QPushButton("Refresh", self)

        def refreshAction():
            self.stale = True  # Force a full refresh
            self.paint()

        self.refreshButton.released.connect(refreshAction)

        l = QGridLayout()
        l.addWidget(QLabel("Minimum Value", self), 0, 0)
        l.addWidget(self.vmin, 0, 1)
        l.addWidget(QLabel("Maximum Value", self), 1, 0)
        l.addWidget(self.vmax, 1, 1)
        l.addWidget(QLabel("Scale Background", self), 2, 0)
        l.addWidget(self.scaleBg, 2, 1)
        l.addWidget(QLabel("Hue", self), 3, 0)
        l.addWidget(self.hue, 3, 1)
        l.addWidget(QLabel("Exponent", self), 4, 0)
        l.addWidget(self.exp, 4, 1)
        l.addWidget(QLabel("Scale Bar", self), 5, 0)
        l.addWidget(self.scaleBar, 5, 1)
        l.addWidget(self.refreshButton, 6, 0)
        layout = QHBoxLayout()
        layout.addLayout(l)
        layout.addWidget(self.plotWidg)
        self.setLayout(layout)

        self.stale = True
        self.paint()

    def paint(self):
        """Refresh the recommended regions. If stale is false then just repaint the cached regions without recalculating."""
        if self.parentRoiPlot.getImageData() is not self.cachedImage:  # The image has been changed.
            self.cachedImage = self.parentRoiPlot.getImageData()
            self.stale = True
        if self.stale:
            try:
                rois = [parm.roiFile for parm in self.parentRoiPlot.rois]
                data = roiColor(self.parentRoiPlot.getImageData(), [r.getRoi() for r in rois], self.vmin.value(), self.vmax.value(), self.scaleBg.value(), hue=self.hue.value(), exponent=self.exp.value(), numScaleBarPix=self.scaleBar.value())
                self.im.set_data(data)
                self.fig.canvas.draw_idle()
                self.stale = False
            except Exception as e:
                msg = QMessageBox.information(self, "Error", f"Warning: Sin City export failed with error: {str(e)}")
                return