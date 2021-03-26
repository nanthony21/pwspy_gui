import abc
import os

from cachetools.decorators import cachedmethod
from cachetools.lru import LRUCache

from pwspy import dataTypes as pwsdt


class ROIManager(abc.ABC):
    """Handles the actual file saving and retrieval. Any code using this should only modify ROI files through this manager."""
    @abc.abstractmethod
    def removeRoi(self, roiFile: pwsdt.RoiFile):
        pass

    @abc.abstractmethod
    def updateRoi(self, roiFile: pwsdt.RoiFile, roi: pwsdt.Roi):
        pass

    @abc.abstractmethod
    def createRoi(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi, roiName: str, roiNumber: int) -> pwsdt.RoiFile:
        pass

    @abc.abstractmethod
    def getROI(self, acq: pwsdt.AcqDir, roiName: str, roiNum: int) -> pwsdt.RoiFile:
        pass

    @abc.abstractmethod
    def close(self):
        """Make sure all files are wrapped up"""
        pass


class _DefaultROIManager(ROIManager):  # TODO LRU cache
    def __init__(self):
        self._cache = LRUCache(maxsize=2048)  # Store this many ROIs at once

    @staticmethod
    def _getCacheKey(roiFile: pwsdt.RoiFile):
        return os.path.split(roiFile.filePath)[0], roiFile.name, roiFile.number

    def removeRoi(self, roiFile: pwsdt.RoiFile):
        self._cache.pop(self._getCacheKey(roiFile))
        roiFile.delete()

    def updateRoi(self, roiFile: pwsdt.RoiFile, roi: pwsdt.Roi):
        roiFile.update(roi)
        self._cache[self._getCacheKey(roiFile)] = roiFile

    def createRoi(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi, roiName: str, roiNumber: int) -> pwsdt.RoiFile:
        roiFile = acq.saveRoi(roiName, roiNumber, roi)
        self._cache[self._getCacheKey(roiFile)] = roiFile
        return roiFile

    @cachedmethod(lambda self: self._cache, key=lambda acq, roiName, roiNum: (acq.filePath, roiName, roiNum))  # Cache results # TODO update cache when roi is saved, created, etc.
    def getROI(self, acq: pwsdt.AcqDir, roiName: str, roiNum: int) -> pwsdt.RoiFile:
        return acq.loadRoi(roiName, roiNum)

    def close(self):
        self._cache.clear()