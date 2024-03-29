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
import hashlib
import json
import logging
import os, io
from enum import Enum
from glob import glob
from typing import List

import pandas

from pwspy_gui.sharedWidgets.extraReflectionManager.ERIndex import ERIndex, ERIndexCube
from pwspy.dataTypes import ERMetaData
import typing
if typing.TYPE_CHECKING:
    from pwspy_gui.sharedWidgets.extraReflectionManager import ERDownloader
from abc import ABC, abstractmethod

class ERAbstractDirectory(ABC):
    """This class keeps track of the status of a directory that contains our extra reflection subtraction cubes.
    This can be implemented as a local directory on a hard drive or a folder on Google Drive, etc., whatever."""

    class DataStatus(Enum):
        md5Confict = 'Data MD5 mismatch'
        found = 'Found'
        notIndexed = 'Not Indexed'
        missing = 'Data File Missing'

    def __init__(self):
        self.index: ERIndex = None
        self.updateIndex()

    @abstractmethod
    def updateIndex(self):
        """update self.index from the `index.json` file."""
        pass

    @abstractmethod
    def getFileStatus(self) -> pandas.DataFrame:
        """return a dataframe indicating directory status by scanning the files in the directory being managed. Assumes that self.index is
        already up to date. In theory the `index.json` file has all the info we need, this method verifies that the
        `index.json` file is actually accurate."""
        pass


class ERDataDirectory(ERAbstractDirectory):
    """A class representing the locally stored data file directory for ExtraReflectanceCube files."""
    def __init__(self, directory: str):
        self._directory = directory
        super().__init__()

    def getMetadataFromId(self, idTag: str) -> ERMetaData:
        """Given the unique idTag string for an ExtraReflectanceCube this will search the index.json and return the
        ERMetaData file. If it cannot be found then an `IndexError will be raised."""
        try:
            match = [item for item in self.index.cubes if item.idTag == idTag][0]
        except IndexError:
            raise IndexError(f"An ExtraReflectanceCube with idTag {idTag} was not found in the index.json file at {self._directory}.")
        return ERMetaData.fromHdfFile(self._directory, match.name)

    def updateIndex(self):
        indexPath = os.path.join(self._directory, ERIndex.FILENAME)
        if not os.path.exists(indexPath):
            self.index = self._createNewIndexFile()
        else:
            try:
                with open(indexPath, 'r') as f:
                    self.index = ERIndex.load(f)
            except json.JSONDecodeError as e: # For unknown reasons the file sometime becomes corrupt. delete and start fresh
                logging.getLogger(__name__).warning("The ERIndex file was corrupt. Deleted and starting fresh.")
                os.remove(indexPath)
                self.index = self._createNewIndexFile()

    def _createNewIndexFile(self) -> ERIndex:
        index = ERIndex([])
        index.toJson(self._directory)
        return index

    def saveNewIndex(self, index: ERIndex):
        index.toJson(self._directory)
        self.index = index

    def getFileStatus(self, skipMD5: bool = False) -> pandas.DataFrame:
        files = glob(ERMetaData.dirName2Directory(self._directory, '*'))
        files = [(f, ERMetaData.validPath(f)) for f in files]  # validPath returns True/False in awhether the datacube was found.
        files = [(directory, name) for f, (valid, directory, name) in files if valid]  # Get rid of invalid files.
        files = [ERMetaData.fromHdfFile(directory, name) for directory, name in files]
        calculatedIndex = self._buildIndexFromFiles(files, skipMD5=skipMD5)
        d = self._compareIndexes(calculatedIndex, self.index, skipMD5=skipMD5)
        if len(d) == 0:
            #This happens when no files are found
            d = pandas.DataFrame({'idTag': [], 'Local Status': []})
        else:
            d = pandas.DataFrame(d).transpose()
            d.columns.values[1] = 'Local Status'
        return d

    @staticmethod
    def _buildIndexFromFiles(files: List[ERMetaData], skipMD5: bool = False) -> ERIndex:
        """Scan the data files in the directory and construct an ERIndex from the metadata. The `description` field is left blank though.
        Args:
            files (List[ERMetaData]): A list of the all the extra reflectance file objects that we want to construct an index from.
            skipMD5 (bool): If True then don't calculate the md5 hash for the files. This can be quite slow. Defaults to False.
        Returns:
            ERIndex: A new ERIndex representing the state of the extra reflectance files in `files`."""
        cubes = []
        for erCube in files:
            if skipMD5:
                md5 = None
            else:
                md5hash = hashlib.md5()
                with open(erCube.filePath, 'rb') as f:
                    md5hash.update(f.read())
                md5 = md5hash.hexdigest()
            cubes.append(ERIndexCube(erCube.filePath, erCube.inheritedMetadata['description'], erCube.idTag,
                                     erCube.directory2dirName(erCube.filePath)[-1], md5))
        return ERIndex(cubes)

    @staticmethod
    def _compareIndexes(ind1: ERIndex, ind2: ERIndex, skipMD5: bool = False) -> dict:
        """A utility function to compare two `ERIndex` objects and return a `dict` containing the status for each file.
        Args:
            ind1 (ERIndex): One of the ERIndexes to be compared.
            ind2 (ERIndex: The other ERIndex to be compared.
            skipMD5 (bool): If True then don't check if the MD5 hashes between the two indexes match. Sometimes we don't measure the MD5 index because it's slow. Defaults to False.
        Returns:
            pandas.Dataframe: A dataframe showing the results of the comparison for each item contained in at least on of the indexes."""
        foundTags = set([cube.idTag for cube in ind1.cubes])
        indTags = set([cube.idTag for cube in ind2.cubes])
        notIndexed = foundTags - indTags  # Tags in foundTags but not in indTags
        missing = indTags - foundTags  # Tags in in indTags but not in foundTags
        matched = indTags & foundTags  # Tags present in both sets
        dataMismatch = []  # Tags that match but have different md5 hashes
        for ID in matched:
            cube = [cube for cube in ind1.cubes if cube.idTag == ID][0]
            indCube = [cube for cube in ind2.cubes if cube.idTag == ID][0]
            if not skipMD5:
                if cube.md5 != indCube.md5:
                    dataMismatch.append(ID)
        # Construct a dataframe
        d = {}
        for i, tag, in enumerate(foundTags | indTags):
            if tag in missing:
                status = ERDataDirectory.DataStatus.missing.value
            elif tag in notIndexed:
                status = ERDataDirectory.DataStatus.notIndexed.value
            elif tag in dataMismatch:
                status = ERDataDirectory.DataStatus.md5Confict.value
            elif tag in matched:  # it must have been matched.
                status = ERDataDirectory.DataStatus.found.value
            else:
                raise Exception("Programming error.")  # This shouldn't be possible
            d[i] = {'idTag': tag, 'status': status}
        return d


class EROnlineDirectory(ERAbstractDirectory):
    """A class representing the status of the google drive directory"""
    def __init__(self, downloader: ERDownloader):
        self._downloader = downloader
        super().__init__()

    def updateIndex(self):
        with io.BytesIO() as f:
            f = self._downloader.downloadToRam('index.json', f)
            f.seek(0) #Move back to the beginning of the stream for reading.
            self.index = ERIndex.load(f)

    def getFileStatus(self) -> pandas.DataFrame:
        calculatedIndex = self._buildIndexFromOnlineFiles()
        d2 = self._compareIndexes(calculatedIndex, self.index)
        d2 = pandas.DataFrame(d2).transpose()
        d2.columns.values[1] = 'Online Status'
        return d2

    def _buildIndexFromOnlineFiles(self) -> ERIndex:
        """Return an ERIndex object from the HDF5 data files saved on Google Drive. No downloading required, just scanning metadata."""
        files = self._downloader.getFileMetadata()
        files = [f for f in files if ERMetaData.FILESUFFIX in f['name']]  # Select the dictionaries that correspond to a extra reflectance data file
        files = [ERIndexCube(fileName=f['name'], md5=f['md5Checksum'], name=ERMetaData.directory2dirName(f['name'])[-1], description=None, idTag=None) for f in files]
        return ERIndex(files)

    @staticmethod
    def _compareIndexes(calculatedIndex: ERIndex, jsonIndex: ERIndex) -> dict:
        """A utility function to compare two `ERIndex` objects and return a `dict` containing the status for each file.
        In this case we are not able to extract the idTags from the dataFiles without downloading them. use filenames instead"""
        foundNames = set([cube.fileName for cube in calculatedIndex.cubes])
        indNames = set([cube.fileName for cube in jsonIndex.cubes])
        notIndexed = foundNames - indNames  # fileNames in foundNames but not in indNames
        missing = indNames - foundNames  # fileNames in in indNames but not in foundNames
        matched = indNames & foundNames  # fileNames present in both sets
        dataMismatch = []  # fileNames that match but have different md5 hashes
        for name in matched:
            cube = [cube for cube in calculatedIndex.cubes if cube.fileName == name][0]
            indCube = [cube for cube in jsonIndex.cubes if cube.fileName == name][0]
            if cube.md5 != indCube.md5:
                dataMismatch.append(name)
        #  Construct a dataframe
        d = {}
        for i, fileName, in enumerate(foundNames | indNames):
            if fileName in missing:
                status = ERDataDirectory.DataStatus.missing.value
            elif fileName in notIndexed:
                status = ERDataDirectory.DataStatus.notIndexed.value
            elif fileName in dataMismatch:
                status = ERDataDirectory.DataStatus.md5Confict.value
            elif fileName in matched:  # it must have been matched.
                status = ERDataDirectory.DataStatus.found.value
            else:
                raise Exception("Programming error.")  # This shouldn't be possible
            d[i] = {'idTag': [ind.idTag for ind in jsonIndex.cubes if ind.fileName == fileName][0], 'status': status}

        return d
