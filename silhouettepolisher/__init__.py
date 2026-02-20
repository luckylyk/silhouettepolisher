
try:
    from PySide2 import QtWidgets
except ImportError:
    from PySide6 import QtWidgets
from silhouettepolisher.ui import SilhouettePolisherWindow


_silhouette_polisher_window = None


def get_maya_main_window():
    '''Return Maya's main window'''
    for obj in QtWidgets.QApplication.topLevelWidgets():
        if obj.objectName() == 'MayaWindow':
            return obj
    raise RuntimeError('Could not find MayaWindow instance')


def launch():
    global _silhouette_polisher_window
    if _silhouette_polisher_window is None:
        parent = get_maya_main_window()
        _silhouette_polisher_window = SilhouettePolisherWindow(parent)
    _silhouette_polisher_window.show()
    _silhouette_polisher_window.raise_()
