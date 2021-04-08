import typing as t_

import numpy as np
from PyQt5.QtCore import QObject
from pwspy.utility.acquisition import SequencerStep, SeqAcqDir, PositionsStep, TimeStep, SequencerCoordinate, IterableSequencerStep
import pwspy.dataTypes as pwsdt
from pwspy_gui.PWSAnalysisApp._roiManager import ROIManager


class Options(t_.NamedTuple):
    copyAlong: bool
    trackMovement: bool


class SequenceController:
    """A utility class to help with selected acquisitions from a sequence that includes a multiple position and time series. both are optional"""
    def __init__(self, sequence: SequencerStep, acqs: t_.Sequence[SeqAcqDir]):
        self.sequence = sequence
        self.coordMap: t_.Dict[pwsdt.AcqDir, SequencerCoordinate] = {acq.acquisition: acq.sequencerCoordinate for acq in acqs}  # A dictionary of the sequence coords keyed by tha acquisition

        self.iterSteps: t_.Tuple[IterableSequencerStep] = tuple((step for step in sequence.iterateChildren() if isinstance(step, IterableSequencerStep)))
        self._indices = tuple(0 for step in self.iterSteps)

    def getIterationNames(self, idx: int) -> t_.Sequence[str]:
        return tuple((self.iterSteps[idx].getIterationName(i) for i in range(self.iterSteps[idx].stepIterations())))

    def setCoordinates(self, *idxs: t_.Sequence[int]) -> pwsdt.AcqDir:
        acq = self.getAcquisitionForIndices(*idxs)
        self._indices = idxs
        return acq

    def getIndicesForAcquisition(self, acq: t_.Union[SeqAcqDir, pwsdt.AcqDir]) -> t_.Tuple[int, ...]:
        """Returns the iteration indices of the given acquisition in the form (timeIdx, posIdx)"""
        coord: SequencerCoordinate = acq.sequencerCoordinate if isinstance(acq, SeqAcqDir) else self.coordMap[acq]
        idxs = []
        for step in self.iterSteps:
            idxs.append(coord.getStepIteration(step))
        return tuple(idxs)

    def getAcquisitionForIndices(self, *idxs: int) -> pwsdt.AcqDir:
        step: SequencerStep = self.iterSteps[np.argmax([len(i.getTreePath()) if i is not None else 0 for i in self.iterSteps])]  # The step that is furthest down the tree path
        coordRange = step.getCoordinate()
        for idx, step in zip(idxs, self.iterSteps):
            coordRange.setAcceptedIterations(step.id, [idx])
        for acq, coord in self.coordMap.items():
            if coord in coordRange:
                return acq
        raise ValueError(f"No acquisition was found to match indices: {idxs}")  # If we got this far then no matching acquisition was found.

    def getCurrentIndices(self) -> t_.Tuple[int, ...]:
        return self._indices


class RoiController(QObject):
    """Handles applying ROI changes across axes.

    """
    def __init__(self, seqController: SequenceController, initialOptions: Options, roiManager: ROIManager, parent: QObject = None):
        super().__init__(parent=parent)
        self._seqController = seqController
        self._options = list(initialOptions for a in seqController.iterSteps)  # One open for each axis.
        self._roiManager = roiManager

    def setOptions(self, axis: int, options: Options):
        self._options[axis] = options

    def getOptions(self, axis: int) -> Options:
        return self._options[axis]

    def setRoiChanged(self, acq: pwsdt.AcqDir, roiFile: pwsdt.RoiFile, overwrite: bool):
        idxs = self._seqController.getIndicesForAcquisition(acq)
        for i, (step, option, idx) in enumerate(zip(self._seqController.iterSteps, self._options, idxs)):
            if not option.copyAlong:
                continue
            for ii in range(idx+1, step.stepIterations()):
                newIdxs = idxs[:i] + (ii,) + idxs[i+1:]
                acq = self._seqController.getAcquisitionForIndices(*newIdxs)
                self._roiManager.createRoi(acq, roiFile.getRoi(), roiFile.name, roiFile.number, overwrite=overwrite)

    def deleteRoi(self, acq: pwsdt.AcqDir, roiFile: pwsdt.RoiFile):
        idxs = self._seqController.getIndicesForAcquisition(acq)

        for i, (step, option, idx) in enumerate(zip(self._seqController.iterSteps, self._options, idxs)):
            if not option.copyAlong:
                continue
            for ii in range(idx+1, step.stepIterations()):
                newIdxs = idxs[:i] + (ii,) + idxs[i+1:]
                acq = self._seqController.getAcquisitionForIndices(*newIdxs)
                roiSpecs = [(roiName, roiNum) for roiName, roiNum, fformat in acq.getRois()]
                if (roiFile.name, roiFile.number) in roiSpecs:
                    self._roiManager.removeRoi(self._roiManager.getROI(acq, roiFile.name, roiFile.number))
