from PySide6 import QtWidgets


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        # This is just a placeholder
        # TODO: construct main window here
        self.layout = QtWidgets.QVBoxLayout(self)

        # Create the splitter
        self.splitter = QtWidgets.QSplitter()
        self.splitter.setHandleWidth(20)
        self.splitter.setChildrenCollapsible(False)
        self.layout.addWidget(self.splitter)

        # Add labels to the splitter
        self.left_label = QtWidgets.QLabel("This is just a placeholde")
        self.right_label = QtWidgets.QLabel("with a splitter...")
        self.splitter.addWidget(self.left_label)
        self.splitter.addWidget(self.right_label)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)


# TODO: This section is here just for testing, it will be moved to the main python file later
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    
    window = MainWindow()
    window.resize(1024, 978)
    window.show()

    import sys
    sys.exit(app.exec())
