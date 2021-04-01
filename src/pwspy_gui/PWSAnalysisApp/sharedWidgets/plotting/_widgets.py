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
import numpy as np
import typing as t_
from pwspy_gui.PWSAnalysisApp.utilities.conglomeratedAnalysis import ConglomerateAnalysisResults
from pwspy.dataTypes import AcqDir, FluorescenceImage
from enum import Enum
from pwspy.analysis.pws import PWSAnalysisResults
from pwspy.analysis.dynamics import DynamicsAnalysisResults


class _AnalysisTypes(Enum):
    """An Enumeration of the possible analysis types."""
    PWS = "pws"
    DYN = "dyn"


class _PlotFields(Enum):
    """An enumerator of the possible images that can be displayed.
    The first item of each tuple indicates which analysis must be available for the image to be displayed.
    The second item of each tuple is a string value matching the attribute name of the associated analysisResults class."""
    Thumbnail = (None, 'thumbnail')
    Fluorescence0 = (None, 'fluorescence0')
    Fluorescence1 = (None, 'fluorescence1')
    Fluorescence2 = (None, 'fluorescence2')
    Fluorescence3 = (None, 'fluorescence3')
    Fluorescence4 = (None, 'fluorescence4')
    Fluorescence5 = (None, 'fluorescence5')
    Fluorescence6 = (None, 'fluorescence6')
    Fluorescence7 = (None, 'fluorescence7')
    Fluorescence8 = (None, 'fluorescence8')
    Fluorescence9 = (None, 'fluorescence9')  # Hopefully we never need nearly this many.
    # PWS specific
    OpdPeak = (_AnalysisTypes.PWS, 'opdPeak')  # Even though this isn't really a name of an analysis field we need something unique for this enum value.
    SingleWavelength = (_AnalysisTypes.PWS, 'singleWavelength')
    MeanReflectance = (_AnalysisTypes.PWS, 'meanReflectance')
    RMS = (_AnalysisTypes.PWS, 'rms')
    AutoCorrelationSlope = (_AnalysisTypes.PWS, 'autoCorrelationSlope')
    RSquared = (_AnalysisTypes.PWS, 'rSquared')
    Ld = (_AnalysisTypes.PWS, 'ld')
    # Dynamics specific
    RMS_t_squared = (_AnalysisTypes.DYN, 'rms_t_squared')
    Diffusion = (_AnalysisTypes.DYN, 'diffusion')
    DynamicsReflectance = (_AnalysisTypes.DYN, 'meanReflectance')


_FluorescencePlotFields = [_PlotFields.Fluorescence0, _PlotFields.Fluorescence1, _PlotFields.Fluorescence2,
                           _PlotFields.Fluorescence3, _PlotFields.Fluorescence4, _PlotFields.Fluorescence5,
                           _PlotFields.Fluorescence6, _PlotFields.Fluorescence7, _PlotFields.Fluorescence8,
                           _PlotFields.Fluorescence9, ]


class AnalysisPlotter:
    PlotFields = _PlotFields
    _fluorescencePlotFields = _FluorescencePlotFields

    AnalysisResultsComboType = t_.Union[
        ConglomerateAnalysisResults,  # Internally we will use the ConglomerateAnalysisResults but we accept a regular tuple as well.
        t_.Tuple[
            t_.Optional[PWSAnalysisResults],
            t_.Optional[DynamicsAnalysisResults]
        ]]

    def __init__(self, acq: AcqDir, analysis: AnalysisResultsComboType = None, initialField=PlotFields.Thumbnail):
        self._analysisField: AnalysisPlotter.PlotFields = initialField
        self._analysis: ConglomerateAnalysisResults = ConglomerateAnalysisResults(*analysis)
        self._acq: AcqDir = acq
        self._data: np.ndarray = None

    @property
    def analysis(self) -> ConglomerateAnalysisResults:
        return self._analysis

    @property
    def acq(self) -> AcqDir:
        return self._acq

    @property
    def data(self) -> np.ndarray:
        return self._data

    @property
    def analysisField(self) -> AnalysisPlotter.PlotFields:
        return self._analysisField

    def changeData(self, field: _PlotFields):
        assert isinstance(field, AnalysisPlotter.PlotFields)
        self._analysisField = field
        if field is _PlotFields.Thumbnail:  # Load the thumbnail from the ICMetadata object
            self._data = self._acq.getThumbnail()
        elif field in _FluorescencePlotFields:  # Open the fluorescence image.
            idx = _FluorescencePlotFields.index(field)  # Get the number for the fluorescence image that has been selected.
            self._data = FluorescenceImage.fromMetadata(self._acq.fluorescence[idx]).data
        else:
            anType, paramName = field.value
            if anType == _AnalysisTypes.PWS:
                analysis = self._analysis.pws
            elif anType == _AnalysisTypes.DYN:
                analysis = self._analysis.dyn
            else:
                raise TypeError("Unidentified analysis type")
            if analysis is None:
                raise ValueError(f"Analysis Plotter for {self._acq.filePath} does not have an analysis file.")
            if field is _PlotFields.OpdPeak:  # Return the index corresponding to the max of that pixel's opd funtion.
                opd, opdIndex = self._analysis.pws.opd
                self._data = opdIndex[np.argmax(opd, axis=2)]
            elif field is _PlotFields.SingleWavelength:  # Return the image of the middle wavelength reflectance.
                _ = self._analysis.pws.reflectance.data
                self._data = _[:, :, _.shape[2]//2] # + self.analysis.pws.meanReflectance # It actually looks better without the meanReflectance added
            else:
                self._data = getattr(analysis, paramName)
        assert len(self._data.shape) == 2

    def setMetadata(self, md: AcqDir, analysis: t_.Optional[AnalysisResultsComboType] = None):
        self._analysis = ConglomerateAnalysisResults(*analysis) if not isinstance(analysis, ConglomerateAnalysisResults) else analysis # In case this was a regular tuple, convert to our convenience class
        self._acq = md
        self.changeData(self._analysisField)

