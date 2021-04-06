from PyQt5.QtWidgets import QWidget
from pwspy_gui.PWSAnalysisApp.componentInterfaces import CellSelector
from pwspy_gui.PWSAnalysisApp.pluginInterfaces import CellSelectorPlugin
import typing as t_
import pwspy.dataTypes as pwsdt
from pwspy_gui.PWSAnalysisApp.plugins.backgroundAutoROI.drawBackgroundROIs import BGROIDialog, BGRoiDrawer


class BackgroundAutoROIPlugin(CellSelectorPlugin):
    def __init__(self):
        self._selector: CellSelector = None
        self._parentWidget = None

    def setContext(self, selector: CellSelector, parent: QWidget):
        """set the CellSelector that this plugin is associated to."""
        self._selector = selector
        self._parentWidget = parent

    def onCellsSelected(self, cells: t_.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that it has had new cells selected."""
        pass

    def onReferenceSelected(self, cell: pwsdt.AcqDir):
        """This method will be called when the CellSelector indicates that it has had a new reference selected."""
        pass

    def onNewCellsLoaded(self, cells: t_.List[pwsdt.AcqDir]):
        """This method will be called when the CellSelector indicates that new cells have been loaded to the selector."""
        pass

    def getName(self) -> str:
        """The name to refer to this plugin by."""
        return "Auto Background ROI"

    def onPluginSelected(self):
        """This method will be called when the plugin is activated."""
        drawer = BGRoiDrawer(parent=self._parentWidget, roiManager=self._selector.getRoiManager())
        drawer.run(self._selector.getSelectedCellMetas())

    def additionalColumnNames(self) -> t_.Sequence[str]:
        """The header names for each column."""
        return tuple()

    def getTableWidgets(self, acq: pwsdt.AcqDir) -> t_.Sequence[QWidget]:
        """provide a widget for each additional column to represent `acq`"""
        return tuple()
