import abc
import os
from PyQt5.QtCore import QObject
from cachetools.decorators import cachedmethod
from cachetools.lru import LRUCache
from pwspy import dataTypes as pwsdt
from pwspy_gui.PWSAnalysisApp.componentInterfaces import ROIManager


class _DefaultROIManager(ROIManager, QObject):
    def __init__(self, parent: QObject = None):
        super().__init__(parent=parent)
        self._cache = LRUCache(maxsize=2048)  # Store this many ROIs at once

    @staticmethod
    def _getCacheKey(roiFile: pwsdt.RoiFile):
        return os.path.split(roiFile.filePath)[0], roiFile.name, roiFile.number

    def removeRoi(self, roiFile: pwsdt.RoiFile):
        self._cache.pop(self._getCacheKey(roiFile))
        roiFile.delete()
        self.roiRemoved.emit(roiFile)

    def updateRoi(self, roiFile: pwsdt.RoiFile, roi: pwsdt.Roi):
        roiFile.update(roi)
        self._cache[self._getCacheKey(roiFile)] = roiFile
        self.roiUpdated.emit(roiFile)

    def createRoi(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi, roiName: str, roiNumber: int, overwrite: bool = False) -> pwsdt.RoiFile:
        roiFile = acq.saveRoi(roiName, roiNumber, roi, overwrite=overwrite)
        self._cache[self._getCacheKey(roiFile)] = roiFile
        self.roiCreated.emit(roiFile, overwrite)
        return roiFile

    @cachedmethod(lambda self: self._cache, key=lambda acq, roiName, roiNum: (acq.filePath, roiName, roiNum))  # Cache results
    def getROI(self, acq: pwsdt.AcqDir, roiName: str, roiNum: int) -> pwsdt.RoiFile:
        return acq.loadRoi(roiName, roiNum)

    def close(self):
        self._cache.clear()
