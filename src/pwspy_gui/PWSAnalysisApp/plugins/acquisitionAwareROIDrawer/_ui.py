from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiDrawer
from PyQt5.QtWidgets import QWidget, QButtonGroup, QPushButton, QHBoxLayout, QVBoxLayout
import typing as t_
import pwspy.dataTypes as pwsdt
if t_.TYPE_CHECKING:
    from pwspy.analysis.pws import PWSAnalysisResults
    from pwspy.analysis.dynamics import DynamicsAnalysisResults
    from pwspy.utility.acquisition import SeqAcqDir

AnalysisResultsComboType = t_.Tuple[
        t_.Optional[PWSAnalysisResults],
        t_.Optional[DynamicsAnalysisResults]]


class SeqRoiDrawer(QWidget):
    def __init__(self, metadatas: t_.List[t_.Tuple[SeqAcqDir, t_.Optional[AnalysisResultsComboType]]], parent: QWidget = None):
        super().__init__(parent=parent)
        

        self._drawer = RoiDrawer(metadatas=[(seqAcq.acquisition, anResults) for seqAcq, anResults in metadatas], parent=self)
        self._positionsBar = ButtonBar(, self)
        self._timesBar = ButtonBar(, self)

        l = QVBoxLayout(self)
        l.addWidget(self._drawer)
        l.addWidget(self._positionsBar)
        l.addWidget(self._timesBar)
        self.setLayout(l)

class ButtonBar(QWidget):
    def __init__(self, items: t_.Sequence[str], parent=None):
        super().__init__(parent=parent)
        self._bGroup = QButtonGroup(self)
        l = QHBoxLayout(self)
        for itemName in items:
            b = QPushButton(itemName, parent=self)
            b.setCheckable(True)  # Toggleable
            self._bGroup.addButton(b)
            l.addWidget(b)
        self.setLayout(l)
