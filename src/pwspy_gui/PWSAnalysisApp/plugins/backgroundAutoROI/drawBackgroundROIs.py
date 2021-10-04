import logging
import re
import typing as t_

from PyQt5 import QtCore
from PyQt5.QtCore import QThread
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QWidget, QPushButton, QLabel, QGridLayout, QLineEdit, QApplication, QFormLayout, \
    QHBoxLayout, QMessageBox

from pwspy_gui.PWSAnalysisApp.componentInterfaces import ROIManager
from pwspy_gui.sharedWidgets.dialogs import BusyDialog
from skimage import filters, morphology, measure
import matplotlib.pyplot as plt
import pwspy.dataTypes as pwsdt
import numpy as np

DESCRIPTION = \
    """
    This action will draw an ROI named (`bg`, 0) on all 
    selected cells which have a PWS analysis matching the 
    name you provide.
    
    Warning: Any existing ROIs saved as ("bg", 0) will be overwritten.
    """


class BGRoiDrawer:
    """
    Opens a dialog box to get information to begin automatic ROI drawing and then runs the process in a separate thread. A message
    box appears at the end giving some useful information.

    Args:
         parent: The QWidget to serve as the `parent` to the dialog boxes.
         roiManager: An object that manages saving and loading of rois within a context. If None is supplied then the ROI operations will be performed directly
    """
    def __init__(self, parent: QWidget = None, roiManager: ROIManager = None):
        self._parent = parent
        self._roiManager = roiManager
        self._processingThread = QThread(self._parent)

    def run(self, acqs: t_.Sequence[pwsdt.Acquisition]):
        analysisname = self._showDialog()
        if analysisname is None:
            return
        else:
            self._threadException = None
            def runInThread(acqList=acqs, anName=analysisname):
                try:
                    self.drawBackgroundROIs(acqList, anName)
                except Exception as e:
                    logging.getLogger(__name__).exception(e)
                    self._threadException = e

            def onFinished():
                if self._threadException is not None:
                    QMessageBox.information(self._parent, "Error!", str(self._threadException))
                else:
                    QMessageBox.information(self._parent, "Finished!", "Automatic background detection is completed.")

            self._processingThread.run = runInThread
            self._processingThread.finished.connect(onFinished)
            self._processingThread.start()
            QMessageBox.information(self._parent, "Be patient", 'A notification will appear when automatic background detection is complete.')

    def _showDialog(self) -> str:
        dlg = BGROIDialog(self._parent)
        accepted = dlg.exec() == QDialog.Accepted
        if accepted:
            return dlg.getAnalysisName()
        else:
            return None

    def drawBackgroundROIs(self, acqs: t_.Iterable[pwsdt.Acquisition], analysisNamePattern: str):
        """

        Args:
            acqs: A list of Acquisition object to run.
            analysisNamePattern: A regex pattern of the analysis file to use for detecting background
        """
        logger = logging.getLogger(__name__)
        skipped = 0
        for i, acq in enumerate(acqs):
            try:
                anNames = acq.pws.getAnalyses()
                anName = [name for name in anNames if re.match(analysisNamePattern, name)][0]  # Select the first analysis name that matches the regex pattern
                rms = acq.pws.loadAnalysis(anName).rms
            except IndexError:
                logger.info(f"Skipping {acq.filePath}. No PWS analysis matching {analysisNamePattern} found.")
                skipped += 1
                continue
            logger.info(f"Auto-Drawing background ROI for acquisition {i+1} of {len(acqs)}")
            thresh = filters.threshold_otsu(rms)
            bgMask = rms < thresh  # Our background should be everything below the threshold.
            bgMask = morphology.binary_erosion(bgMask, morphology.disk(15))
            smthDisk = morphology.disk(15)
            bgMask = morphology.binary_closing(morphology.binary_opening(bgMask, smthDisk), smthDisk)  # Smoothing
            label = measure.label(bgMask)  # Identify and label connected components
            try:
                largestLabel = np.argmax(np.bincount(label.flat)[1:]) + 1  # The number of the largest labeled region (We exclude the 0th item and then add 1 to avoid including the negative region (labeled 0))
            except ValueError: # If there are no labeled regions then we will get `attempt to get argmax of an empty sequence here.                logger.info(f"Skipping {acq.filePath}. No PWS analysis matching {analysisNamePattern} found.")
                logger.info(f"Skipping {acq.filePath}. No background region found.")
                skipped += 1
                continue
            mask = label == largestLabel  # Our background region should be the largest non-zero region
            roi = pwsdt.Roi.fromMask(mask=mask)
            if self._roiManager is None:
                acq.saveRoi('bg', 0, roi, overwrite=True)
            else:
                self._roiManager.createRoi(acq, roi, 'bg', 0, True)
        logger.info(f"Skipped {skipped} of {len(acqs)} acquisitions")


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
        form.addRow("Analysis Name (regex):", self.analysisName)
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
