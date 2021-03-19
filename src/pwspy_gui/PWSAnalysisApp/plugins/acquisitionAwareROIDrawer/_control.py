import typing as t_

import numpy as np
from PyQt5.QtCore import QObject
from pwspy.utility.acquisition import SequencerStep, SeqAcqDir, PositionsStep, TimeStep
import pwspy.dataTypes as pwsdt


class Options(t_.NamedTuple):
    copyAlongTime: bool
    trackMovement: bool

# TODO Doesn't detect ROI modification from right click menu. Make a "ROI modification handler" so that the actuall saving can be easily swappable
# TODO remove "Tracking" option for now.
# TODO key bindings for quick modification.
class SequenceController:
    """A utility class to help with selected acquisitions from a sequence that includes a multiple position and time series. both are optional"""
    def __init__(self, sequence: SequencerStep, acqs: t_.Sequence[SeqAcqDir]):
        self.sequence = sequence
        self.acqs = acqs
        posSteps = [step for step in sequence.iterateChildren() if isinstance(step, PositionsStep)]
        assert not len(posSteps) > 1, "Sequences with more than one `MultiplePositionsStep` are not currently supported"
        timeSteps = [step for step in sequence.iterateChildren() if isinstance(step, TimeStep)]
        assert not len(timeSteps) > 1, "Sequences with more than one `TimeSeriesStep` are not currently supported"

        self.timeStep = timeSteps[0] if len(timeSteps) > 0 else None
        self.posStep = posSteps[0] if len(posSteps) > 0 else None
        self._iterSteps = (self.timeStep, self.posStep)

        self._tIndex = None
        self._pIndex = None

    def getTimeNames(self) -> t_.Optional[t_.Sequence[str]]:
        if self.timeStep is None:
            return None
        else:
            return tuple([self.timeStep.getIterationName(i) for i in range(self.timeStep.stepIterations())])

    def getPositionNames(self) -> t_.Optional[t_.Sequence[str]]:
        if self.posStep is None:
            return None
        else:
            return tuple([self.posStep.getIterationName(i) for i in range(self.posStep.stepIterations())])

    def setCoordinates(self, posIndex: t_.Optional[int], tIndex: t_.Optional[int]) -> SeqAcqDir:
        acq = self.getAcquisitionForIndices(tIndex, posIndex)
        self._tIndex = tIndex
        self._pIndex = posIndex
        return acq

    def getIndicesForAcquisition(self, acq: t_.Union[SeqAcqDir, pwsdt.AcqDir]) -> t_.Tuple[int, int]:
        """Returns the iteration indices of the given acquisition in the form (timeIdx, posIdx)"""
        sacq = acq if isinstance(acq, SeqAcqDir) else self.getSequencerAcqforAcq(acq)
        coord = sacq.sequencerCoordinate
        tIdx = coord.getStepIteration(self.timeStep) if self.timeStep is not None else None
        pIdx = coord.getStepIteration(self.posStep) if self.posStep is not None else None
        return tIdx, pIdx

    def getAcquisitionForIndices(self, tIndex: int, pIndex: int) -> SeqAcqDir:
        step: SequencerStep = self._iterSteps[np.argmax([len(i.getTreePath()) if i is not None else 0 for i in self._iterSteps])]  # The step that is furthest down the tree path
        coordRange = step.getCoordinate()
        if self.timeStep is not None:
            coordRange.setAcceptedIterations(self.timeStep.id, [tIndex])
        if self.posStep is not None:
            coordRange.setAcceptedIterations(self.posStep.id, [pIndex])
        for acq in self.acqs:
            coord = acq.sequencerCoordinate
            if coord in coordRange:
                return acq
        raise ValueError(f"No acquisition was found to match Position index: {posIndex}, Time index: {tIndex}") # If we got this far then no matching acquisition was found.


    def getSequencerAcqforAcq(self, acq: pwsdt.AcqDir) -> SeqAcqDir:
        for sacq in self.acqs:
            if sacq.acquisition is acq:
                return sacq
        raise ValueError(f"No Sequencer acquisition was found to match standard acquistion: {acq}")

    def getCurrentIndices(self) -> t_.Tuple[int, int]:
        """Of the form (tIndex, pIndex)"""
        return self._tIndex, self._pIndex


class RoiController(QObject):
    def __init__(self, seqController: SequenceController, initialOptions: Options, parent: QObject = None):
        super().__init__(parent=parent)
        self._seqController = seqController
        self._options = initialOptions

    def setOptions(self, options: Options):
        self._options = options

    def getOptions(self) -> Options:
        return self._options

    def setRoiChanged(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi, overwrite: bool):
        if not self._options.copyAlongTime:
            return
        tIdx, pIdx = self._seqController.getIndicesForAcquisition(acq)
        if tIdx is None:
            return
        for i in range(tIdx+1, self._seqController.timeStep.stepIterations()):
            sacq = self._seqController.getAcquisitionForIndices(i, pIdx)
            roiSpecs = [(roiName, roiNum) for roiName, roiNum, fformat in sacq.acquisition.getRois()]
            sacq.acquisition.saveRoi(roi, overwrite=True)

    def deleteRoi(self, acq: pwsdt.AcqDir, roi: pwsdt.Roi):
        if not self._options.copyAlongTime:
            return
        tIdx, pIdx = self._seqController.getIndicesForAcquisition(acq)
        if tIdx is None:
            return
        for i in range(tIdx+1, self._seqController.timeStep.stepIterations()):
            sacq = self._seqController.getAcquisitionForIndices(i, pIdx)
            roiSpecs = [(roiName, roiNum) for roiName, roiNum, fformat in sacq.acquisition.getRois()]
            if (roi.name, roi.number) in roiSpecs:
                sacq.acquisition.deleteRoi(roi.name, roi.number)