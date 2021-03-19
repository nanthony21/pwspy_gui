import typing as t_

import numpy as np
from pwspy.utility.acquisition import SequencerStep, SeqAcqDir, PositionsStep, TimeStep
import pwspy.dataTypes as pwsdt

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

    def getAcquisition(self, posIndex: t_.Optional[int], tIndex: t_.Optional[int]) -> SeqAcqDir:
        step: SequencerStep = self._iterSteps[np.argmax([len(i.getTreePath()) if i is not None else 0 for i in self._iterSteps])]  # The step that is furthest down the tree path
        coordRange = step.getCoordinate()
        if self.timeStep is not None:
            coordRange.setAcceptedIterations(self.timeStep.id, [tIndex])
        if self.posStep is not None:
            coordRange.setAcceptedIterations(self.posStep.id, [posIndex])
        for acq in self.acqs:
            coord = acq.sequencerCoordinate
            if coord in coordRange:
                return acq
        raise ValueError(f"No acquisition was found to match Position index: {posIndex}, Time index: {tIndex}") # If we got this far then no matching acquisition was found.

    def getIndices(self, acq: t_.Union[SeqAcqDir, pwsdt.AcqDir]) -> t_.Tuple[int, int]:
        """Returns the iteration indices of the given acquisition in the form (timeIdx, posIdx)"""
        sacq = acq if isinstance(acq, SeqAcqDir) else self.getSequencerAcqforAcq(acq)
        coord = sacq.sequencerCoordinate
        tIdx = coord.getStepIteration(self.timeStep) if self.timeStep is not None else None
        pIdx = coord.getStepIteration(self.posStep) if self.posStep is not None else None
        return tIdx, pIdx


    def getSequencerAcqforAcq(self, acq: pwsdt.AcqDir) -> SeqAcqDir:
        for sacq in self.acqs:
            if sacq.acquisition is acq:
                return sacq
        raise ValueError(f"No Sequencer acquisition was found to match standard acquistion: {acq}")