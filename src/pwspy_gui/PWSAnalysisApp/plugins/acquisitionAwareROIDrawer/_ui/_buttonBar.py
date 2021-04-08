import typing as t_

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFrame, QButtonGroup, QHBoxLayout, QPushButton, QScrollArea, QWidget, QSizePolicy


class ButtonBar(QFrame):
    buttonClicked = pyqtSignal(str, int)  # Indicates the iteration number and iteration name of the button that was clicked

    def __init__(self, items: t_.Sequence[str], parent=None):
        super().__init__(parent=parent)
        # self.setFrameStyle(QFrame.Panel)
        self._bGroup = QButtonGroup(self)
        l = QHBoxLayout(self)
        for i, itemName in enumerate(items):
            b = QPushButton(itemName, parent=self)
            b.setCheckable(True)  # Toggleable
            self._bGroup.addButton(b, id=i)
            l.addWidget(b)
        self._selectedButtonId = self._bGroup.id(self._bGroup.buttons()[0])
        self._bGroup.buttons()[0].click()  # Make sure at least one button is selected.
        self._bGroup.buttonClicked.connect(self._buttonSelected)
        l.setSpacing(1)  # Move buttons close together
        l.setContentsMargins(0, 0, 0, 0)
        w = QFrame(self)
        w.setFrameStyle(QFrame.Box)
        w.setLayout(l)
        scrollArea = QScrollArea(parent=self)
        scrollArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scrollArea.setStyleSheet("""QScrollBar:horizontal {
             height:10px;     
         }""")
        scrollArea.setWidget(w)
        scrollArea.setFixedHeight(10 + w.height())
        ll = QHBoxLayout()
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(scrollArea)
        self.setLayout(ll)


    def _buttonSelected(self, btn):
        self._selectedButtonId = self._bGroup.id(btn)
        self.buttonClicked.emit(btn.text(), self._bGroup.id(btn))

    def getSelectedButtonId(self):
        return self._selectedButtonId

    def selectNextButton(self):
        id = self._selectedButtonId + 1
        if id >= len(self._bGroup.buttons()):
            id = 0
        self.setButtonSelected(id)

    def setButtonSelected(self, ID: int):
        btn = self._bGroup.button(ID)
        btn.click()