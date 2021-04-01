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
from typing import List, Tuple, Optional
from pwspy.analysis import warnings
from pwspy.analysis.dynamics import DynamicsAnalysisResults
from pwspy.analysis.pws import PWSAnalysisResults
from pwspy.dataTypes import Roi
from pwspy.analysis.compilation import (DynamicsRoiCompiler, DynamicsCompilerSettings, DynamicsRoiCompilationResults,
                                        PWSRoiCompiler, PWSCompilerSettings, PWSRoiCompilationResults,
                                        GenericRoiCompiler, GenericCompilerSettings, GenericRoiCompilationResults)
from typing import NamedTuple
"""These utility classes are used to conveniently treat analysis objects of different types that belong together as a single object."""


class ConglomerateCompilerSettings(NamedTuple):
    pws: PWSCompilerSettings
    dyn: DynamicsCompilerSettings
    generic: GenericCompilerSettings


class ConglomerateCompilerResults(NamedTuple):
    pws: PWSRoiCompilationResults
    dyn: DynamicsRoiCompilationResults
    generic: GenericRoiCompilationResults


class ConglomerateAnalysisResults(NamedTuple):
    pws: Optional[PWSAnalysisResults]
    dyn: Optional[DynamicsAnalysisResults]


class ConglomerateCompiler:
    """
    This convenience class combines the actions of the compilers defined in `pwspy.analysis.compilation` into a single object.
    """
    def __init__(self, settings: ConglomerateCompilerSettings):
        self.settings = settings
        self.pws = PWSRoiCompiler(self.settings.pws)
        self.dyn = DynamicsRoiCompiler(self.settings.dyn)
        self.generic = GenericRoiCompiler(self.settings.generic)

    def run(self, results: ConglomerateAnalysisResults, roiFile: RoiFile) -> Tuple[ConglomerateCompilerResults, List[warnings.AnalysisWarning]]:
        if results.pws is not None:
            pwsResults, pwsWarnings = self.pws.run(results.pws, roiFile)
        else:
            pwsResults, pwsWarnings = None, []
        if results.dyn is not None:
            dynResults, dynWarnings = self.dyn.run(results.dyn, roiFile)
        else:
            dynResults, dynWarnings = None, []
        genResults = self.generic.run(roiFile)
        return ConglomerateCompilerResults(pwsResults, dynResults, genResults), pwsWarnings + dynWarnings
