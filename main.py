import os
#os.environ["QT_SCALE_FACTOR"] = "1"
#os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
#os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from src.ui.windows.main_window import run_gui

import src.ui.resources_rc  # type: ignore


if __name__ == '__main__':
    run_gui()
