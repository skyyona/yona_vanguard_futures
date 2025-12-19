import logging
from typing import Optional
from PySide6.QtWidgets import QMessageBox

_suppress_popups = False

def set_suppress_popups(value: bool):
    global _suppress_popups
    _suppress_popups = bool(value)

def is_suppressed() -> bool:
    return _suppress_popups

def show_confirmation(parent, title: str, text: str, detailed: Optional[str] = None,
                      buttons = QMessageBox.Cancel | QMessageBox.Ok, default = QMessageBox.Ok):
    """Show a confirmation dialog; if suppressed, log and return the default button immediately."""
    logger = logging.getLogger(__name__)
    if _suppress_popups:
        logger.info("Popup suppressed (confirmation): %s - %s", title, text)
        return default

    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    if detailed:
        msg.setDetailedText(detailed)
    msg.setStandardButtons(buttons)
    msg.setDefaultButton(default)
    return msg.exec()

def show_warning(parent, title: str, text: str):
    logger = logging.getLogger(__name__)
    if _suppress_popups:
        logger.warning("Popup suppressed (warning): %s - %s", title, text)
        return None
    return QMessageBox.warning(parent, title, text)
