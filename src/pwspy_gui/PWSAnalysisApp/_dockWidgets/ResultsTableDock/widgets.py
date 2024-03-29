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

from typing import Optional, Tuple, Dict

from PyQt5 import QtCore
from PyQt5.QtWidgets import QTableWidgetItem, QPushButton, QApplication
import matplotlib.pyplot as plt


from pwspy.analysis.compilation import (DynamicsCompilerSettings, GenericCompilerSettings, PWSCompilerSettings, AbstractCompilerSettings)
from pwspy_gui.PWSAnalysisApp.utilities.conglomeratedAnalysis import ConglomerateCompilerResults
from pwspy_gui.PWSAnalysisApp.sharedWidgets.tables import CopyableTable, NumberTableWidgetItem
from pwspy.dataTypes import Acquisition
import os


class ResultsTableItem:
    """This class embodies the results from a single ROI in Qt widget form. This is shown as a single row in the results table widget.

    Args:
        results: The object containing the results for all analysis types
        acq: A reference to the directory storing the data files.

    """
    def __init__(self, results: ConglomerateCompilerResults, acq: Acquisition):
        self.results = results
        self.acq = acq
        cellPath = os.path.split(acq.filePath)[0][len(QApplication.instance().workingDirectory) + 1:]
        cellNumber = int(acq.filePath.split('Cell')[-1])
        self.cellPathLabel = QTableWidgetItem(cellPath)
        self.cellNumLabel = NumberTableWidgetItem(cellNumber)
        # Generic results
        self.roiNameLabel = QTableWidgetItem(results.generic.roiFile.name)
        self.roiNumLabel = NumberTableWidgetItem(results.generic.roiFile.number)
        self.roiAreaLabel = NumberTableWidgetItem(results.generic.roiArea)
        # PWS related results
        pws = results.pws
        if pws is not None:
            self.pwsAnalysisNameLabel = QTableWidgetItem(pws.analysisName)
            self.rmsLabel = NumberTableWidgetItem(pws.rms)
            self.reflectanceLabel = NumberTableWidgetItem(pws.reflectance)
            self.polynomialRmsLabel = NumberTableWidgetItem(pws.polynomialRms)
            self.autoCorrelationSlopeLabel = NumberTableWidgetItem(pws.autoCorrelationSlope)
            self.rSquaredLabel = NumberTableWidgetItem(pws.rSquared)
            self.ldLabel = NumberTableWidgetItem(pws.ld)
            self.opdButton = QPushButton("OPD")
            self.opdButton.released.connect(self._plotOpd)
            if pws.opd is None:
                self.opdButton.setEnabled(False)
            self.meanSigmaRatioLabel = NumberTableWidgetItem(pws.varRatio)
        else:
            self.pwsAnalysisNameLabel = QTableWidgetItem()
            self.rmsLabel, self.reflectanceLabel, self.polynomialRmsLabel, self.autoCorrelationSlopeLabel, self.rSquaredLabel, self.ldLabel, self.meanSigmaRatioLabel = (NumberTableWidgetItem() for i in range(7))
            self.opdButton = QPushButton("OPD")
            self.opdButton.setEnabled(False)
        # Dynamics related results
        dyn = results.dyn
        if dyn is not None:
            self.dynamicsAnalysisNameLabel = QTableWidgetItem(dyn.analysisName)
            self.rms_tLabel = NumberTableWidgetItem(dyn.rms_t_squared)
            self.dynamicsReflectanceLabel = NumberTableWidgetItem(dyn.reflectance)
            self.diffusionLabel = NumberTableWidgetItem(dyn.diffusion)
        else:
            self.rms_tLabel, self.dynamicsReflectanceLabel, self.diffusionLabel = (NumberTableWidgetItem() for i in range(3))
            self.dynamicsAnalysisNameLabel = QTableWidgetItem()

    def _plotOpd(self):
        fig, ax = plt.subplots()
        ax.plot(self.results.pws.opdIndex, self.results.pws.opd)
        fig.suptitle(f"{self.cellPathLabel.text()}/Cell{self.cellNumLabel.text()}")
        ax.set_ylabel("Amplitude")
        ax.set_xlabel("OPD (um)")
        fig.show()


class ResultsTable(CopyableTable):
    """
    This widget is a subclass of QTableWidget which displays all the results. It  can be copied from in CSV form.
    """
    itemsCleared = QtCore.pyqtSignal()  # this appears to be unused. Delete?

    # Columns. In the form {`name`: (`defaultVisible`, `analysisFieldName`, `compilerSettingsClass, `tooltip`)}
    columns: Dict[str, Tuple[bool, Optional[str], Optional[AbstractCompilerSettings], Optional[str]]]
    columns = {
        "Path": (False, None, None, None),
        'Cell#': (True, None, None, None),
        "PWS Analysis": (False, None, None, None),
        'ROI Name': (True, None, None, None),
        'ROI#': (True, None, None, None),
        "RMS": (True, 'rms', PWSCompilerSettings, "Primary analysis result indicating nanoscopic RI heterogeneity of sample in ROI. Defined as StdDev of the spectra"),
        'Reflectance': (True, 'reflectance', PWSCompilerSettings, "Sample reflectance averaged over the spectrum. Calculated by dividing the acquired image cube by a reference cube and then multiplying by the expected reflectance of the reference. The expected reflectance is determined by the user's choice of reference material in the analysis settings."),
        'ld': (False, 'ld', PWSCompilerSettings, "Referred to as Disorder Strength. This is proportional to RMS / AutoCorr Slope. Due to the noisiness of AutoCorr Slope this is also not very useful."),
        "AutoCorr Slope": (False, 'autoCorrelationSlope', PWSCompilerSettings, "Slope of the natural logarithm of the autocorrelation of the spectra, This is very susceptible to noise, not very useful."),
        'R^2': (False, 'rSquared', PWSCompilerSettings, "A measure the linearity of the slope of the natural logarithm of the autocorrelation function. If this is low then the AutoCorr Slope value should not be trusted."),
        'OPD': (False, 'opd', PWSCompilerSettings, "This is the Fourier transform of the spectrum. In theory this should indicate how much of the signal is contributed to by different optical path differences (OPD). Fun fact, RMS is equal to the integral of the OPD over wavenumber (k), if you are interested only in the RMS due to a specific range of OPD you can get this from summing over the appropriate range of the OPD. This is useful for removing unwanted contributions to RMS from thin films."),
        "Mean Spectra Ratio": (False, 'meanSigmaRatio', PWSCompilerSettings, "The spectral variations that we are interested in are expected to have a short spatial correlation length (neighboring pixels should not have the same spectra. However if we look at the average spectra over a cell nucleus we find that there is an overarching spectra common to the whole region. This is a measure of how much this `mean spectra` contributes to the RMS of the ROI."),
        "Poly RMS": (False, 'polynomialRms', PWSCompilerSettings, "In order to remove spectral features that are not due to interference (fluorescence, absorbance, etc.) we sometimes subtract a polynomial fit from the data before analysis. This indicates the StdDev of the polynomial fit. It's not clear how this is useful"),
        "Roi Area": (False, 'roiArea', GenericCompilerSettings, "The area of the ROI given in units of pixels. This can be converted to microns if you know the size in object space of a single pixel"),
        "Dynamics Analysis": (False, None, None, None),
        "RMS_t^2": (False, 'rms_t_squared', DynamicsCompilerSettings, "This is the primary analysis result for `Dynamics`. It is the standard deviation of the signal over time when looking at just a single wavelength."),
        "Dynamics Reflectance": (False, 'meanReflectance', DynamicsCompilerSettings, "This is the average reflectance of the ROI for the `Dynamics` measurement."),
        "Diffusion": (False, 'diffusion', DynamicsCompilerSettings, "Diffusion is calculated as the slope of the log of the autocorrelation function of a `Dynamics` measurement.")
    }

    def __init__(self):
        super().__init__()
        self.setRowCount(0)
        self.setColumnCount(len(self.columns.keys()))
        self.setHorizontalHeaderLabels(self.columns.keys())
        for i, (default, settingsName, compilerClass, tooltip) in enumerate(self.columns.values()):
            self.setColumnHidden(i, not default)
            self.horizontalHeaderItem(i).setToolTip(tooltip)
        self.verticalHeader().hide()
        self.setSortingEnabled(True)
        self._items = []

    def addItem(self, item: ResultsTableItem) -> None:
        row = len(self._items)
        self.setSortingEnabled(False)  # The fact that we are adding items assuming its the last row is a problem if sorting is on.
        self.setRowCount(row + 1)

        self.setItem(row, 0, item.cellPathLabel)
        self.setItem(row, 1, item.cellNumLabel)
        self.setItem(row, 2, item.pwsAnalysisNameLabel)
        self.setItem(row, 3, item.roiNameLabel)
        self.setItem(row, 4, item.roiNumLabel)
        self.setItem(row, 5, item.rmsLabel)
        self.setItem(row, 6, item.reflectanceLabel)
        self.setItem(row, 7, item.ldLabel)
        self.setItem(row, 8, item.autoCorrelationSlopeLabel)
        self.setItem(row, 9, item.rSquaredLabel)
        self.setCellWidget(row, 10, item.opdButton)
        self.setItem(row, 11, item.meanSigmaRatioLabel)
        self.setItem(row, 12, item.polynomialRmsLabel)
        self.setItem(row, 13, item.roiAreaLabel)
        self.setItem(row, 14, item.dynamicsAnalysisNameLabel)
        self.setItem(row, 15, item.rms_tLabel)
        self.setItem(row, 16, item.dynamicsReflectanceLabel)
        self.setItem(row, 17, item.diffusionLabel)

        self.setSortingEnabled(True)
        self._items.append(item)

    def clearCellItems(self) -> None:
        self.clearContents()
        self.setRowCount(0)
        self._items = []
        self.itemsCleared.emit()


