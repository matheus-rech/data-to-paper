import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from data_to_paper.env import CHOSEN_APP
from .base_app import BaseApp


IS_APP_INITIALIZED = False
THE_APP: Optional[BaseApp] = None


def get_or_create_app() -> Optional[BaseApp]:
    global IS_APP_INITIALIZED, THE_APP
    if IS_APP_INITIALIZED:
        return THE_APP

    IS_APP_INITIALIZED = True

    if CHOSEN_APP == None:  # noqa  (Mutable)
        THE_APP = None
    elif CHOSEN_APP == 'pyside':
        from .research_step_window import ResearchStepApp
        q_application = QApplication(sys.argv)
        THE_APP = ResearchStepApp.get_instance()
        THE_APP.q_application = q_application
        THE_APP.initialize()
    elif CHOSEN_APP == 'console':
        from .base_app import ConsoleApp
        THE_APP = ConsoleApp.get_instance()
        THE_APP.initialize()
    else:
        raise ValueError(f"Unknown app type: {CHOSEN_APP}")

    return THE_APP
