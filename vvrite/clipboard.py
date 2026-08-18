"""Clipboard swap pattern: backup, write, paste, restore."""

import time
from AppKit import NSPasteboard, NSPasteboardItem, NSData, NSPasteboardTypeString
from Quartz import (
    CGEventSourceCreate,
    CGEventCreateKeyboardEvent,
    CGEventSetFlags,
    CGEventPost,
    kCGEventSourceStateHIDSystemState,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

from vvrite.preferences import CLIPBOARD_RESTORE_DELAY

kVK_ANSI_V = 0x09
kVK_Delete = 0x33


def backup() -> list:
    """Back up all clipboard items (preserves images, rich text, etc.)."""
    pb = NSPasteboard.generalPasteboard()
    items = pb.pasteboardItems()
    if not items:
        return []

    saved = []
    for item in items:
        item_data = {}
        for ptype in item.types():
            data = item.dataForType_(ptype)
            if data is not None:
                item_data[ptype] = NSData.dataWithData_(data)
        saved.append(item_data)
    return saved


def restore(saved: list):
    """Restore clipboard contents from a backup."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if not saved:
        return

    new_items = []
    for item_data in saved:
        pb_item = NSPasteboardItem.alloc().init()
        for ptype, data in item_data.items():
            pb_item.setData_forType_(data, ptype)
        new_items.append(pb_item)
    pb.writeObjects_(new_items)


def _set_text(text: str):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)


def _post_keypress(keycode: int, flags: int = 0):
    source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
    down = CGEventCreateKeyboardEvent(source, keycode, True)
    up = CGEventCreateKeyboardEvent(source, keycode, False)
    CGEventSetFlags(down, flags)
    CGEventSetFlags(up, flags)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def _simulate_cmd_v():
    _post_keypress(kVK_ANSI_V, kCGEventFlagMaskCommand)


def _simulate_delete_backward(repeat_count: int):
    for _ in range(max(0, repeat_count)):
        _post_keypress(kVK_Delete)


def _wait_for_write(pasteboard, previous_count, timeout=0.05):
    """Block until the pasteboard reports our write, or give up.

    Replaces a flat 50ms sleep before Cmd-V. changeCount increments as soon as the
    write lands, which measured immediate — the sleep was paying for a wait that
    had already happened, on every dictation, in front of the user.
    """
    deadline = time.monotonic() + timeout
    while pasteboard.changeCount() == previous_count and time.monotonic() < deadline:
        time.sleep(0.001)


def paste_and_restore(text: str, on_pasted=None):
    """Write text to clipboard, paste via Cmd-V, then restore original clipboard.

    on_pasted fires the moment the paste is sent, before the restore delay. That
    delay exists so the target app finishes reading the pasteboard before we put
    the old contents back, and nothing the user sees depends on it — holding the
    overlay up for it just made every dictation look 200ms longer than it was.
    """
    pasteboard = NSPasteboard.generalPasteboard()
    saved = backup()
    previous_count = pasteboard.changeCount()
    _set_text(text)
    _wait_for_write(pasteboard, previous_count)
    _simulate_cmd_v()
    if on_pasted is not None:
        on_pasted()
    time.sleep(CLIPBOARD_RESTORE_DELAY)
    restore(saved)


def retract_text(text: str) -> bool:
    """Delete a previously inserted text block by sending Delete keypresses."""
    if not text:
        return False

    _simulate_delete_backward(len(text))
    return True
