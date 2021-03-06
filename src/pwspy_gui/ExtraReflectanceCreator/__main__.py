# Copyright 2018-2020 Nick Anthony, Backman Biophotonics Lab, Northwestern University
#
# This file is part of PWSpy.
#
# PWSpy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PWSpy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PWSpy.  If not, see <https://www.gnu.org/licenses/>.

import logging
import os
from datetime import datetime

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QFileDialog, QListWidgetItem, QMessageBox

from pwspy import dateTimeFormat
from pwspy_gui.ExtraReflectanceCreator.ERWorkFlow import ERWorkFlow
import matplotlib.pyplot as plt

from pwspy_gui.ExtraReflectanceCreator.widgets.mainWindow import MainWindow
from pwspy_gui import appPath
from pwspy_gui.sharedWidgets.extraReflectionManager import ERManager
import traceback


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

        self.workflow = ERWorkFlow(wDir, self.gDriveDir)
        self.erManager = ERManager(self.gDriveDir)
        self.window = MainWindow(self.erManager)
        self.connectWindowToWorkflow()

    def connectWindowToWorkflow(self):
        for k, v in self.workflow.fileStruct.items():
            self.window.listWidg.addItem(k)
        self.window.listWidg.currentItemChanged.connect(self.selectionChanged)
        self.window.deleteFigsButton.released.connect(self.workflow.deleteFigures)
        self.window.saveButton.released.connect(self._cb(lambda: self.workflow.save(self.window.numericalAperture.value())))
        self.window.selListWidg.itemChanged.connect(self.workflow.invalidateCubes)
        self.window.binningCombo.currentIndexChanged.connect(self.workflow.invalidateCubes)
        self.window.compareDatesButton.released.connect(self._cb(self.workflow.compareDates))
        self.window.plotButton.released.connect(
            self._cb(lambda: self.workflow.plot(self.window.numericalAperture.value(), saveToPdf=True, saveDir=self.figsDir)))

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

    def loadIfNeeded(self):
        if self.workflow.cubes is None:
            self.workflow.loadCubes(self.window.checkedSettings, self.window.binning, self.window.parallelProcessing)

    def _cb(self, func):
        """Return a wrapped function with extra gui stuff."""
        def newfunc():
            """Toggle button enabled state. load new data if selection has changed. run the callback."""
            try:
                self.window.setEnabled(False)
                self.loadIfNeeded()
                func()
            except:
                traceback.print_exc()
                msg = QMessageBox.warning(self.window, "Don't panic", "An error occurred. Please see the console for details.")
            finally:
                self.window.setEnabled(True)
        return newfunc

    def selectionChanged(self, item: QListWidgetItem, oldItem: QListWidgetItem):
        self.workflow.directoryChanged(item.text())
        self.window.selListWidg.clear()
        settings = set(self.workflow.df['setting'])
        _, settings = zip(*sorted(zip([datetime.strptime(sett, "%m_%d_%Y") for sett in settings], settings)))
        for sett in settings:
            _ = QListWidgetItem(sett)
            _.setFlags(_.flags() | QtCore.Qt.ItemIsUserCheckable)
            _.setCheckState(QtCore.Qt.Unchecked)
            self.window.selListWidg.addItem(_)

def isIpython():
    try:
        return __IPYTHON__
    except:
        return False


def main():
    import sys

    # This prevents errors from happening silently.
    sys.excepthook_backup = sys.excepthook
    def exception_hook(exctype, value, tb):
        print(exctype, value, tb)
        sys.excepthook_backup(exctype, value, tb)
        sys.exit(1)
    sys.excepthook = exception_hook

    logger = logging.getLogger()  # We use the root logger so that all loggers in pwspy will be captured.
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    appDataPath = os.path.join(appPath, 'ExtraReflectanceCreatorData')
    if not os.path.exists(appDataPath):
        os.mkdir(appDataPath)
    fHandler = logging.FileHandler(os.path.join(appDataPath, f'log{datetime.now().strftime("%d%m%Y%H%M%S")}.txt'))
    fHandler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s %(name)s.%(funcName)s(%(lineno)d) - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(fHandler)

    if isIpython():
        app = ERApp(sys.argv)
    else:
        app = ERApp(sys.argv)
        sys.exit(app.exec_())


if __name__ == '__main__':
    main()