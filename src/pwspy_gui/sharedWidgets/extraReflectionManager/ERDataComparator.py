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

from __future__ import annotations

from typing import Optional

import pandas
import typing
if typing.TYPE_CHECKING:
    from pwspy_gui.sharedWidgets.extraReflectionManager import ERDownloader
from pwspy_gui.sharedWidgets.extraReflectionManager._ERDataDirectory import ERDataDirectory, EROnlineDirectory, ERAbstractDirectory
from enum import Enum


class ERDataComparator:
    """A class to compare the local directory to the online directory.
    Args:
        online: Handles communication with GoogleDrive, if operating in offline mode this should be None
        directory: The file path where the files are stored locally.
    """

    class ComparisonStatus(Enum):
        LocalOnly = "Local Only"
        OnlineOnly = "Online Only"
        Md5Mismatch = 'MD5 Mismatch'
        Match = "Match"  # This is what we hope to see.

    def __init__(self, online: EROnlineDirectory, directory: ERDataDirectory):
        self.local: ERDataDirectory = directory
        self.online: EROnlineDirectory = online

    def updateIndexes(self):
        self.local.updateIndex()
        if self.online is not None:
            self.online.updateIndex()

    def compare(self) -> pandas.DataFrame:
        """Scans local and online files to put together an idea of the status."""
        localStatus = self.local.getFileStatus()
        if self.online is not None:
            onlineStatus = self.online.getFileStatus()
            status = pandas.merge(localStatus, onlineStatus, how='outer', on='idTag')
            status['Index Comparison'] = status.apply(lambda row: self._dataFrameCompare(row), axis=1)
            status = status[['idTag', 'Local Status', 'Online Status', 'Index Comparison']]  # Set the column order
        else:
            status = localStatus
            status['Index Comparison'] = self.ComparisonStatus.LocalOnly.value
            status = status[['idTag', 'Local Status', 'Index Comparison']]  # Set the column order
        return status

    def _dataFrameCompare(self, row) -> str:
        try:
            self.local.index.getItemFromIdTag(row['idTag'])
        except:
            return self.ComparisonStatus.OnlineOnly.value
        try:
            self.online.index.getItemFromIdTag(row['idTag'])
        except:
            return self.ComparisonStatus.LocalOnly.value
        if self.local.index.getItemFromIdTag(row['idTag']).md5 != self.online.index.getItemFromIdTag(row['idTag']).md5:
            return self.ComparisonStatus.Md5Mismatch.value
        else:
            return self.ComparisonStatus.Match.value
