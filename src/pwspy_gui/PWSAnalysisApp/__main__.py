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
import shutil
from glob import glob
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5 import QtCore
from pwspy_gui.PWSAnalysisApp.App import PWSApp
from pwspy_gui.PWSAnalysisApp import applicationVars
from datetime import datetime
from pwspy_gui.PWSAnalysisApp import resources
from pwspy.analysis import defaultSettingsPath


def _setupDataDirectories():
    if not os.path.exists(applicationVars.dataDirectory):
        os.mkdir(applicationVars.dataDirectory)
    if not os.path.exists(applicationVars.analysisSettingsDirectory):
        os.mkdir(applicationVars.analysisSettingsDirectory)
    settingsFiles = glob(os.path.join(defaultSettingsPath, '*.json'))
    if len(settingsFiles) == 0:
        raise Exception("Warning: Could not find any analysis settings presets.")
    for f in settingsFiles:  # This will overwrite any existing preset files in the application directory with the defaults in the source code.
        shutil.copyfile(f, os.path.join(applicationVars.analysisSettingsDirectory, os.path.split(f)[-1]))
    if not os.path.exists(applicationVars.extraReflectionDirectory):
        os.mkdir(applicationVars.extraReflectionDirectory)
        with open(os.path.join(applicationVars.extraReflectionDirectory, 'readme.txt'), 'w') as f:
            f.write("""Extra reflection `data cubes` and an index file are stored on the Backman Lab google drive account.
            Download the index file and any data cube you plan to use to this folder.""")
    if not os.path.exists(applicationVars.googleDriveAuthPath):
        os.mkdir(applicationVars.googleDriveAuthPath)
        shutil.copyfile(os.path.join(resources, 'credentials.json'),
                        os.path.join(applicationVars.googleDriveAuthPath, 'credentials.json'))


def main():
    import sys
    import getopt

    debugMode = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['debug'])
        if len(opts) > 0:  # If any arguments were found
            optNames, optVals = zip(*opts)
            if '--debug' in optNames:
                debugMode = True
    except getopt.GetoptError as e:
        print(e)
        sys.exit(1)

    def isIpython():
        try:
            return __IPYTHON__  # Only defined if we are running within ipython
        except NameError:
            return False

    _setupDataDirectories()  # this must happen before the logger can be instantiated
    logger = logging.getLogger()  # We use the root logger so that all loggers in pwspy will be captured.

    # This prevents errors from happening silently. Found on stack overflow.
    sys.excepthook_backup = sys.excepthook
    def exception_hook(exctype, value, traceBack):
        logger.exception("Unhandled Exception! :", exc_info=value, stack_info=True)
        sys.excepthook_backup(exctype, value, traceBack)  # Run the error through the default exception hook
        sys.exit(1)
    sys.excepthook = exception_hook

    logger.addHandler(logging.StreamHandler(sys.stdout))
    fHandler = logging.FileHandler(os.path.join(applicationVars.dataDirectory, f'log{datetime.now().strftime("%d%m%Y%H%M%S")}.txt'))
    fHandler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s %(name)s.%(funcName)s(%(lineno)d) - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(fHandler)
    logger.setLevel(logging.INFO)
    if debugMode:
        logging.getLogger("pwspy_gui").setLevel(logging.DEBUG)
        logging.getLogger("pwspy").setLevel(logging.DEBUG)
        logger.info("Logger set to debug mode.")

    try:
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"  # TODO replace these options with proper high dpi handling. no pixel specific widths.
        QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        logger.debug("About to construct `PWSApp`")
        app = PWSApp(sys.argv)
        logger.debug("Finished constructing `PWSApp`")

        #Testing script
        # app.changeDirectory(r'\\backmanlabnas.myqnapcloud.com\home\Year3\zstack_focusSensitivity\again', False)
        # app.setSelectedCells(app.getLoadedCells()[:3])
        # app.plotSelectedCells()
        # app.window.plots._startRoiDrawing()

        if not isIpython():  # IPython runs its own QApplication so we handle things slightly different.
            sys.exit(app.exec_())
    except Exception as e:  # Save error to text file.
        logger.exception(e)
        msg = f"Error Occurred. Please check the log in: {applicationVars.dataDirectory}"
        msgBox = QMessageBox.information(None, 'Crash!', msg)
        raise e


if __name__ == '__main__':
    main()
