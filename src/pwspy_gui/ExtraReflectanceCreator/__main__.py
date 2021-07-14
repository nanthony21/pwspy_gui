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

from pwspy_gui.ExtraReflectanceCreator.app import ERApp
from pwspy_gui import appPath


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
    logger.setLevel(logging.INFO)
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
