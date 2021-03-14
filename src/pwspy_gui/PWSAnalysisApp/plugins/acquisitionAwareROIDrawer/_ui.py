from pwspy_gui.PWSAnalysisApp.sharedWidgets.plotting import RoiDrawer
from PyQt5.QtWidgets import QWidget

class SeqRoiDrawer(QWidget):
    def __init__(self):
        self._drawer = RoiDrawer()
