"""Is keyboard focus in something that accepts text? (UI Automation, works for browsers too)"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_uia = None
_U = None
EDITABLE_TYPES = {50004, 50030}  # Edit, Document


def _client():
    global _uia, _U
    if _uia is None:
        import comtypes.client

        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient as U

        _U = U
        _uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    return _uia, _U


def focus_is_editable() -> bool | None:
    """True/False when we can tell, None when UI Automation fails (treat as editable)."""
    try:
        uia, U = _client()
        el = uia.GetFocusedElement()
        if el is None:
            return False
        if el.CurrentControlType in EDITABLE_TYPES:
            return True
        value = el.GetCurrentPattern(U.UIA_ValuePatternId)
        if value:
            value = value.QueryInterface(U.IUIAutomationValuePattern)
            return not value.CurrentIsReadOnly
        return bool(el.GetCurrentPattern(U.UIA_TextEditPatternId))
    except Exception:
        log.debug("UI Automation focus check failed", exc_info=True)
        return None
