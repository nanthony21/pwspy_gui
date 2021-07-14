import os
import traceback
from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QListWidgetItem
from matplotlib import pyplot as plt

from pwspy_gui import appPath
from pwspy_gui.ExtraReflectanceCreator.ERWorkFlow import ERWorkFlow
from pwspy_gui.ExtraReflectanceCreator.widgets.mainWindow import MainWindow
from pwspy_gui.sharedWidgets.extraReflectionManager import ERManager


class ERApp(QApplication):
    """
    An application for generating the "ExtraReflectance" calibration files from a set of reference reflectance measurements.
    """
    def __init__(self, args):
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        super().__init__(args)
        plt.interactive(True)
        settings = QtCore.QSettings("BackmanLab", "ERCreator")
        try:
            initialDir = settings.value('workingDirectory')
        except TypeError: #Setting not found
            initialDir = None
        wDir = QFileDialog.getExistingDirectory(caption='Select the root `ExtraReflection` directory', directory=initialDir)
        settings.setValue("workingDirectory", wDir)
        self.checkDataDir()

        try:
            self.workflow = ERWorkFlow(wDir, self.gDriveDir)
            self.erManager = ERManager(self.gDriveDir)
            self.window = MainWindow(self.erManager)
            self.connectWindowToWorkflow()
        except Exception as e:
            QMessageBox.warning(None, "Error", repr(e))
            raise e

    def connectWindowToWorkflow(self):
        for k, v in self.workflow.fileStruct.items():
            self.window.listWidg.addItem(k)
        self.window.listWidg.currentItemChanged.connect(self.selectionChanged)
        self.window.deleteFigsButton.released.connect(self.workflow.deleteFigures)
        self.window.saveButton.released.connect(
            self._cb(
                lambda: self.workflow.save(
                    self.window.checkedSettings,
                    self.window.binning,
                    self.window.parallelProcessing,
                    self.window.numericalAperture.value(),
                    self.window)))
        self.window.selListWidg.itemChanged.connect(self.workflow.invalidateCubes)
        self.window.binningCombo.currentIndexChanged.connect(self.workflow.invalidateCubes)
        self.window.compareDatesButton.released.connect(
            self._cb(
                lambda: self.workflow.compareDates(
                    self.window.checkedSettings,
                    self.window.binning,
                    self.window.parallelProcessing)))
        self.window.plotButton.released.connect(
            self._cb(
                lambda: self.workflow.plot(
                    self.window.checkedSettings,
                    self.window.binning,
                    self.window.parallelProcessing,
                    self.window.numericalAperture.value(),
                    saveToPdf=True,
                    saveDir=self.figsDir)))

    def checkDataDir(self):
        self.homeDir = os.path.join(appPath, 'ExtraReflectanceCreatorData')
        if not os.path.exists(self.homeDir):
            os.mkdir(self.homeDir)
        self.gDriveDir = os.path.join(self.homeDir, 'GoogleDriveData')
        if not os.path.exists(self.gDriveDir):
            os.mkdir(self.gDriveDir)
        self.figsDir = os.path.join(self.homeDir, 'Plots')
        if not os.path.exists(self.figsDir):
            os.mkdir(self.figsDir)

    def _cb(self, func):
        """Return a wrapped function with extra gui stuff."""
        def newfunc():
            """Toggle button enabled state. load new data if selection has changed. run the callback."""
            try:
                self.window.setEnabled(False)
                func()
            except:
                traceback.print_exc()
                msg = QMessageBox.warning(self.window, "Don't panic", "An error occurred. Please see the console for details.")
            finally:
                self.window.setEnabled(True)
        return newfunc

    def selectionChanged(self, item: QListWidgetItem, oldItem: QListWidgetItem):
        settings = self.workflow.directoryChanged(item.text())
        self.window.selListWidg.clear()

        _, settings = zip(*sorted(zip([datetime.strptime(sett, "%m_%d_%Y") for sett in settings], settings)))
        for sett in settings:
            _ = QListWidgetItem(sett)
            _.setFlags(_.flags() | QtCore.Qt.ItemIsUserCheckable)
            _.setCheckState(QtCore.Qt.Unchecked)
            self.window.selListWidg.addItem(_)