# Copyright 2018-2021 Nick Anthony, Backman Biophotonics Lab, Northwestern University
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

import hashlib
import os
from datetime import datetime
from glob import glob
import json
import typing as t_
from PyQt5.QtWidgets import QWidget
from matplotlib import animation

from pwspy.dataTypes import CameraCorrection, Acquisition, ICMetaData, PwsCube
from pwspy_gui.ExtraReflectanceCreator.widgets.dialog import IndexInfoForm
from pwspy.dataTypes import Roi
from pwspy import dateTimeFormat
from pwspy.utility.reflection import Material
from pwspy.utility.fileIO import loadAndProcess
import pwspy.utility.reflection.extraReflectance as er
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import logging
from mpl_qt_viz.visualizers import PlotNd, DockablePlotWindow
import pathlib as pl


class Directory:
    def __init__(self, df: pd.DataFrame, camCorr: CameraCorrection):
        self.dataframe = df
        self.cameraCorrection = camCorr


def scanDirectory(directory: str) -> Directory:
    """
    Scan a folder for data in the format expected by this application. We expect multiple layers of subfolders.
    Layer 1: Folders named by date.
    Layer 2: Folders named by material imaged. Must be supported by pwspy.utility.reflectance.reflectanceHelper and in the `matMap` variable.
    Layer 3: "Cell{x}" folders each containing a single acquisition.

    Args:
        directory: The file path to be scanned.

    Returns:
        A `Directory` object for the scanned directory.
    """
    try:
        cam = CameraCorrection.fromJsonFile(os.path.join(directory, 'cameraCorrection.json'))
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(e)
        raise Exception(f"Could not load a camera correction at {directory}. Please add a `cameraCorrection.json` file to describe how to correct for dark counts and nonlinearity.")
    files = glob(os.path.join(directory, '*', '*', 'Cell*'))
    rows = []
    matMap = {'air': Material.Air, 'water': Material.Water, 'ipa': Material.Ipa, 'ethanol': Material.Ethanol, 'glass': Material.Glass,
              'methanol': Material.Methanol}
    for file in files:
        filelist = pl.Path(file).parts  # Split file into components.
        s = filelist[-3]
        m = matMap[filelist[-2]]
        file = Acquisition(file).pws.filePath  # old pws is saved directly in the "Cell{X}" folder. new pws is saved in "Cell{x}/PWS" the Acquisition class helps us abstract that out and be compatible with both.
        rows.append({'setting': s, 'material': m, 'cube': file})
    df = pd.DataFrame(rows)
    return Directory(df, cam)


class DataProvider:
    def __init__(self, df: pd.DataFrame, camCorr: CameraCorrection):
        self._df = df
        self._cameraCorrection = camCorr
        self._cubes = None

    def getCubes(self):
        return self._cubes

    def getDataFrame(self):
        return self._df

    def loadCubes(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool):
        df = self._df[self._df['setting'].isin(includeSettings)]
        if binning is None:
            args = {'correction': None, 'binning': None}
            for cube in df['cube']:
                md = ICMetaData.loadAny(cube)
                if md.binning is None:
                    raise Exception("No binning metadata found. Please specify a binning setting.")
                elif md.cameraCorrection is None:
                    raise Exception(
                        "No camera correction metadata found. Please specify a binning setting, in this case the application will use the camera correction stored in the cameraCorrection.json file of the calibration folder")
        else:
            args = {'correction': self._cameraCorrection, 'binning': binning}
        self._cubes = loadAndProcess(df, self._processIm, parallel=parallelProcessing, procArgs=[args])
        self._cubes['material'] = self._cubes['material'].astype('category')

    def _processIm(self, im: PwsCube, kwargs) -> PwsCube:
        """
        This processor function may be run in parallel to pre-process each raw image.

        Args:
            im: The `PwsCube` to be preprocessed.
            kwargs: These keyword arguments are passed to `PwsCube.correctCameraEffects`

        Returns:
            The same PwsCube that was provided as input.
        """
        im.correctCameraEffects(**kwargs)
        im.normalizeByExposure()
        try:
            im.filterDust(0.8)  # in microns
        except ValueError:
            logger = logging.getLogger(__name__)
            logger.warning("No pixel size metadata found. assuming a gaussian filter radius of 6 pixels = 1 sigma.")
            im.filterDust(6, pixelSize=1)  # Do the filtering in units of pixels if no auto pixelsize was found
        return im


class ERWorkFlow:
    """
    This class serves as an adapter between the complicated operations available in the pwspy.utility.relfection.extraReflectance
    module and the UI of the ERCreator app.

    Args:
        workingDir: The folder to scan for images. Each subfolder of workingDir should be named by the corresponding system / configuration.
            The contents of each subfolder should align with the description in `scanDirectory`
        homeDir: TODO
    """
    def __init__(self, workingDir: str, homeDir: str):
        self.fileStruct = self.df = self.cameraCorrection = self.currDir = self.plotnds = self.anims = None
        self.figs = []
        self.dataprovider = None
        self.homeDir = homeDir
        folders = [i for i in glob(os.path.join(workingDir, '*')) if os.path.isdir(i)]
        settings = [os.path.split(i)[-1] for i in folders]
        self.fileStruct = {}
        for f, s in zip(folders, settings):
            self.fileStruct[s] = scanDirectory(f)

    def loadIfNeeded(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool):
        if self.dataprovider.getCubes() is None:
            self.loadCubes(includeSettings, binning, parallelProcessing)

    def invalidateCubes(self):
        """Clear the cached data requiring that data is reloaded from file."""
        self.dataprovider._cubes = None

    def deleteFigures(self):
        for fig in self.figs:
            if isinstance(fig, plt.Figure):
                plt.close(fig)
            elif isinstance(fig, QWidget):
                fig.close()
            else:
                raise TypeError(f"Type {type(fig)} shouldn't be here, what's going on?")
        self.figs = []

    def loadCubes(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool):
        self.dataprovider.loadCubes(includeSettings, binning, parallelProcessing)

    def plot(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool, numericalAperture: float, saveToPdf: bool = False, saveDir: str = None):
        self.loadIfNeeded(includeSettings, binning, parallelProcessing)
        cubes = self.dataprovider.getCubes()
        materials = set(cubes['material'])
        theoryR = er.getTheoreticalReflectances(materials,
                                                cubes['cube'].iloc[0].wavelengths, numericalAperture)  # Theoretical reflectances
        matCombos = er.generateMaterialCombos(materials)

        print("Select an ROI")
        roi = cubes['cube'].sample(n=1).iloc[0].selectLassoROI()  # Select an ROI to analyze
        cubeDict = cubes.groupby('setting').apply(lambda df: df.groupby('material')['cube'].apply(list).to_dict()).to_dict()  # Transform data frame to a dict of dicts of lists for input to `plot`
        self.figs.extend(er.plotExtraReflection(cubeDict, theoryR, matCombos, numericalAperture, roi))
        if saveToPdf:
            with PdfPages(os.path.join(saveDir, f"fig_{datetime.strftime(datetime.now(), '%d-%m-%Y %HH%MM%SS')}.pdf")) as pp:
                for i in plt.get_fignums():
                    f = plt.figure(i)
                    f.set_size_inches(9, 9)
                    pp.savefig(f)

    def save(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool, numericalAperture: float, parentWidget: QWidget):
        self.loadIfNeeded(includeSettings, binning, parallelProcessing)
        cubes = self.dataprovider.getCubes()
        settings = set(cubes['setting'])
        for setting in settings:
            sCubes = cubes[cubes['setting'] == setting]
            materials = set(sCubes['material'])
            theoryR = er.getTheoreticalReflectances(materials,
                                                    sCubes['cube'].iloc[0].wavelengths, numericalAperture)  # Theoretical reflectances
            matCombos = er.generateMaterialCombos(materials)
            matCubes = sCubes.groupby('material')['cube'].apply(list).to_dict()
            combos = er.getAllCubeCombos(matCombos, matCubes)
            erCube, rExtraDict = er.generateRExtraCubes(combos, theoryR, numericalAperture)
            dock = DockablePlotWindow(title=setting)
            dock.addWidget(
                PlotNd(erCube.data, title='Mean',
                       indices=[range(erCube.data.shape[0]), range(erCube.data.shape[1]),
                                erCube.wavelengths]),
                title='Mean'
            )
            for matCombo, rExtraArr in rExtraDict.items():
                dock.addWidget(
                    PlotNd(rExtraArr, title=matCombo,
                           indices=[range(erCube.data.shape[0]), range(erCube.data.shape[1]),
                                    erCube.wavelengths]),
                    title=str(matCombo)
                )
            logger = logging.getLogger(__name__)
            logger.info(f"Final data max is {erCube.data.max()}")
            logger.info(f"Final data min is {erCube.data.min()}")
            self.figs.append(dock)  # keep track of opened figures.
            saveName = f'{self.currDir}-{setting}'
            dialog = IndexInfoForm(f'{self.currDir}-{setting}', erCube.metadata.idTag, parent=parentWidget)

            def accepted(dialog, erCube, saveName):
                erCube.metadata.inheritedMetadata['description'] = dialog.description
                erCube.toHdfFile(self.homeDir, saveName)
                self.updateIndex(saveName, erCube.metadata.idTag, dialog.description, erCube.metadata.dirName2Directory('', saveName))

            dialog.accepted.connect(lambda dlg=dialog, ercube=erCube, savename=saveName: accepted(dlg, ercube, savename))
            dialog.show()

    def updateIndex(self, saveName: str, idTag: str, description: str, filePath: str):
        with open(os.path.join(self.homeDir, 'index.json'), 'r') as f:
            index = json.load(f)
        md5hash = hashlib.md5()
        with open(os.path.join(self.homeDir, filePath), 'rb') as f:
            md5hash.update(f.read())
        md5 = md5hash.hexdigest() #The md5 checksum as a string of hex.
        cubes = index['reflectanceCubes']
        newEntry = {'fileName': filePath,
                    'description': description,
                    'idTag': idTag,
                    'name': saveName,
                    'md5': md5}
        cubes.append(newEntry)
        index['reflectanceCubes'] = cubes
        index['creationDate'] = datetime.strftime(datetime.now(), dateTimeFormat)
        with open(os.path.join(self.homeDir, 'index.json'), 'w') as f:
            json.dump(index, f, indent=4)

    def compareDates(self, includeSettings: t_.List[str], binning: int, parallelProcessing: bool):
        self.loadIfNeeded(includeSettings, binning, parallelProcessing)
        anis = []
        figs = []  # These lists just maintain references to matplotlib figures to keep them responsive.
        cubes = self.dataprovider.getCubes()
        verts = cubes['cube'].sample(n=1).iloc[0].selectLassoROI()  # Select a random of the selected cubes and use it to prompt the user for an analysis ROI
        mask = Roi.fromVerts(verts=verts, dataShape=cubes['cube'].sample(n=1).iloc[0].data.shape[:-1])
        for mat in set(cubes['material']):
            c = cubes[cubes['material'] == mat]
            fig, ax = plt.subplots()
            fig.suptitle(mat.name)
            ax.set_xlabel("Wavelength (nm)")
            ax.set_ylabel("Counts/ms")
            fig2, ax2 = plt.subplots()
            fig2.suptitle(mat.name)
            figs.extend([fig, fig2])
            anims = []
            for i, row in c.iterrows():
                im = row['cube']
                spectra = im.getMeanSpectra(mask)[0]
                ax.plot(im.wavelengths, spectra, label=row['setting'])
                anims.append((ax2.imshow(im.data.mean(axis=2), animated=True,
                                         clim=[np.percentile(im.data, .5), np.percentile(im.data, 99.5)]),
                              ax2.text(40, 40, row['setting'])))
            ax.legend()
            anis.append(animation.ArtistAnimation(fig2, anims, interval=1000, blit=False))
        self.anims = anis

        self.figs.extend(figs) #Keep track of opened figures.

    def directoryChanged(self, directory: str) -> t_.Set[str]:
        """
        Args:
            directory:

        Returns:
            A list of the `settings` found in the new directory.
        """
        self.currDir = directory
        directory = self.fileStruct[directory]
        self.dataprovider = DataProvider(directory.dataframe, directory.cameraCorrection)
        return set(self.dataprovider.getDataFrame()['setting'])
