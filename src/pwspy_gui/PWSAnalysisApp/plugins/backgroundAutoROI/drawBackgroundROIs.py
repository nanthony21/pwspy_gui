import logging
import typing as t_

from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QWidget, QPushButton, QLabel, QGridLayout, QLineEdit, QApplication, QFormLayout, \
    QHBoxLayout, QMessageBox
from pwspy_gui.sharedWidgets.dialogs import BusyDialog
from skimage import filters, morphology, measure
import matplotlib.pyplot as plt
import pwspy.dataTypes as pwsdt

DESCRIPTION = \
    """
    This action will draw an ROI named (`bg`, 0) on all 
    selected cells which have a PWS analysis matching the 
    name you provide.
    
    Warning: Any existing ROIs saved as ("bg", 0) will be overwritten.
    """


class BGRoiDrawer:
    def __init__(self, parent: QWidget = None):
        self._parent = parent
        self._processingThread = QThread(self._parent)

    def run(self, acqs: t_.Sequence[pwsdt.AcqDir]):
        analysisname = self._showDialog()
        if analysisname is None:
            return
        else:
            def runInThread(acqList=acqs, anName=analysisname):
                drawBackgroundROIs(acqList, anName)

            def onFinished():
                QMessageBox.information(self._parent, "Finished!", "Automatic background detection is completed.")

            self._processingThread.run = runInThread
            self._processingThread.finished.connect(onFinished)
            self._processingThread.start()


    def _showDialog(self) -> str:
        dlg = BGROIDialog(self._parent)
        accepted = dlg.exec() == QDialog.Accepted
        if accepted:
            return dlg.getAnalysisName()
        else:
            return None


def drawBackgroundROIs(acqs: t_.Iterable[pwsdt.AcqDir], analysisName: str):
    logger = logging.getLogger(__name__)

    for i, acq in enumerate(acqs):
        try:
            rms = acq.pws.loadAnalysis(analysisName).rms
        except OSError:
            logger.info(f"Skipping {acq.filePath}. No PWS analysis file found.")
            continue
        logger.info(f"Auto-Drawing background ROI for acquisition {i} of {len(acqs)}")
        thresh = filters.threshold_otsu(rms)
        bgMask = rms < thresh  # Our background should be everything below the threshold.
        bgMask = morphology.binary_erosion(bgMask, morphology.disk(15))
        smthDisk = morphology.disk(15)
        bgMask = morphology.binary_closing(morphology.binary_opening(bgMask, smthDisk), smthDisk)  # Smoothing
        label = measure.label(bgMask)  # Identify and label connected components
        mask = label == 1  # Our background region should be the largest non-zero region
        roi = pwsdt.Roi.fromMask(mask=mask)
        acq.saveRoi('bg', 0, roi, overwrite=True)


class BGROIDialog(QDialog):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent=parent)
        self.setWindowTitle("Automatic Background Detection")

        self.description = QLabel(DESCRIPTION)
        font = self.description.font()
        font.setBold(True)
        self.description.setFont(font)

        self.analysisName = QLineEdit()

        self.okButton = QPushButton("Ok")
        self.okButton.released.connect(self.accept)

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.released.connect(self.reject)

        grid = QGridLayout()
        grid.addWidget(self.description, 0, 0)
        form = QFormLayout()
        form.addRow("Analysis Name:", self.analysisName)
        grid.addLayout(form, 1, 0)
        ll = QHBoxLayout()
        ll.addWidget(self.okButton)
        ll.addWidget(self.cancelButton)
        grid.addLayout(ll, 2, 0)
        self.setLayout(grid)

    def getAnalysisName(self) -> str:
        return self.analysisName.text()


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    g = BGRoiDrawer()
    g.run()
    a = 1
