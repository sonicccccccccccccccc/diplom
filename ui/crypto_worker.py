from PySide6.QtCore import QThread, Signal

class CryptoWorker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, task, *args):
        super().__init__()
        self.task = task
        self.args = args

    def run(self):
        try:
            result = self.task(*self.args)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))