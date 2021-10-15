import typing as t_
import pwspy.dataTypes as pwsdt
from pwspy.analysis.pws import LegacyPWSAnalysisResults

class Modernizer:
    def __init__(self, acqs: t_.List[pwsdt.AcqDir], analysisName: str):
        for acq in acqs:
            legacy = LegacyPWSAnalysisResults.load(acq.filePath, analysisName)

