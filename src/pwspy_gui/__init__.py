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

"""
GUI applications related to PWS.

PWSAnalysisApp
----------------

The main application used for the analysis of PWS and related data.

ExtraReflectanceCreator
-------------------------

This application is used to generate `ExtraReflectanceCube` calibration files and upload them to google drive.

"""
import logging
try:
    from . import version
    _versionStr = version.version
except ImportError:  # When running from source the version.py file won't have been created by setuptools_scm
    logging.getLogger(__name__).info("Failed to import `version.py`. Trying to import setuptools_scm")
    try:
        import setuptools_scm
        _versionStr = setuptools_scm.get_version(root='../..', relative_to=__file__)
    except ImportError:  # setuptools_scm
        logging.getLogger(__name__).info("Failed to import setuptools_scm. Using fallback version string.")
        _versionStr = "x.x.x-dev"

__author__ = "Nick Anthony"
__version__ = _versionStr

__all__ = ['resources', 'appPath']
import os

resources = os.path.join(os.path.split(__file__)[0], '_resources')

appPath = os.path.expanduser('~/PwspyApps') # Create a directory to store all application data
if not os.path.exists(appPath):
    os.mkdir(appPath)
