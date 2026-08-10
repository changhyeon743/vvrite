"""Settings window for hotkey, microphone, permissions, and launch at login."""

import objc
import threading

import ApplicationServices
import AVFoundation
import os

from AppKit import (
    NSObject,
    NSMakeRect,
    NSWindow,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSBackingStoreBuffered,
    NSTextField,
    NSFont,
    NSButton,
    NSButtonTypeSwitch,
    NSPopUpButton,
    NSColor,
    NSApp,
    NSBezelStyleRounded,
    NSAlert,
    NSAlertFirstButtonReturn,
    NSWorkspace,
    NSSlider,
    NSOpenPanel,
    NSMenuItem,
    NSToolbar,
    NSToolbarItem,
    NSTabView,
    NSTabViewItem,
    NSNoTabsNoBorder,
    NSToolbarDisplayModeIconAndLabel,
    NSWindowToolbarStylePreference,
    NSSegmentedControl,
    NSImage,
    NSBox,
    NSBoxSeparator,
    NSView,
)
from Foundation import NSLog, NSURL, NSTimer

from vvrite import launch_at_login, screen, sounds
from vvrite.audio_devices import (
    get_default_input_device,
    list_input_devices,
    resolve_input_device,
)
from vvrite.locales import t, SUPPORTED_LANGUAGES
from vvrite.widgets import ShortcutField, format_shortcut, active_shortcut


# Layout constants for the tabbed settings window.
WIN_W = 480
CONTENT_H = 420
MARGIN = 24
LABEL_W = 120
CTRL_X = MARGIN + LABEL_W + 12  # 156
RIGHT = WIN_W - MARGIN          # 456
CTRL_W = RIGHT - CTRL_X         # 300

_TAB_GENERAL = "general"
_TAB_AUDIO = "audio"
_TAB_LANGUAGE = "language"
_TAB_MODEL = "model"
_TAB_SYSTEM = "system"
_TAB_IDS = [_TAB_GENERAL, _TAB_AUDIO, _TAB_LANGUAGE, _TAB_MODEL, _TAB_SYSTEM]
_TAB_ICONS = {
    _TAB_GENERAL: "gearshape",
    _TAB_AUDIO: "mic",
    _TAB_LANGUAGE: "globe",
    _TAB_MODEL: "waveform",
    _TAB_SYSTEM: "lock.shield",
}


class SettingsWindowController(NSObject):
    def initWithPreferences_(self, prefs):
        self = objc.super(SettingsWindowController, self).init()
        if self is None:
            return None
        self._prefs = prefs
        self._window = None
        self._tab_view = None
        self._permission_timer = None
        self._acc_label = None
        self._mic_label = None
        self._mode_segmented = None
        self._mode_hotkey_label = None
        self._mode_hint = None
        self._shortcut_field = None
        self._ptt_shortcut_field = None
        self._retract_checkbox = None
        self._retract_shortcut_field = None
        self._retract_change_btn = None
        self._mic_popup = None
        self._mic_device_ids = [None]
        self._login_checkbox = None
        self._custom_words_field = None
        self._stt_endpoint_field = None
        self._stt_test_btn = None
        self._stt_hint = None
        self._stt_correction_checkbox = None
        self._stt_correction_hint = None
        self._screen_context_checkbox = None
        self._screen_context_hint = None
        self._llm_endpoint_field = None
        self._llm_model_field = None
        self._llm_context_field = None
        self._start_sound_popup = None
        self._stop_sound_popup = None
        self._start_volume_slider = None
        self._stop_volume_slider = None
        self._start_volume_label = None
        self._stop_volume_label = None
        self._ui_lang_popup = None
        self._asr_lang_popup = None
        self._build_window()
        return self

    def _build_window(self):
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIN_W, CONTENT_H),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_(t("settings.title"))
        self._window.setReleasedWhenClosed_(False)
        self._window.setDelegate_(self)

        # A borderless tab view fills the content area; the toolbar selects tabs.
        self._tab_view = NSTabView.alloc().initWithFrame_(
            NSMakeRect(0, 0, WIN_W, CONTENT_H)
        )
        self._tab_view.setTabViewType_(NSNoTabsNoBorder)
        self._window.setContentView_(self._tab_view)

        builders = {
            _TAB_GENERAL: self._build_general_tab,
            _TAB_AUDIO: self._build_audio_tab,
            _TAB_LANGUAGE: self._build_language_tab,
            _TAB_MODEL: self._build_model_tab,
            _TAB_SYSTEM: self._build_system_tab,
        }
        for tab_id in _TAB_IDS:
            item = NSTabViewItem.alloc().initWithIdentifier_(tab_id)
            item.setLabel_(self._tab_label(tab_id))
            view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, WIN_W, CONTENT_H))
            builders[tab_id](view)
            item.setView_(view)
            self._tab_view.addTabViewItem_(item)

        # Toolbar — System-Settings style (centered icon + label tabs).
        toolbar = NSToolbar.alloc().initWithIdentifier_("vvriteSettingsToolbar")
        toolbar.setDelegate_(self)
        toolbar.setDisplayMode_(NSToolbarDisplayModeIconAndLabel)
        toolbar.setSelectedItemIdentifier_(_TAB_GENERAL)
        self._window.setToolbar_(toolbar)
        try:
            self._window.setToolbarStyle_(NSWindowToolbarStylePreference)
        except Exception:
            pass

        self._tab_view.selectTabViewItemWithIdentifier_(_TAB_GENERAL)
        self._window.setTitle_(self._tab_label(_TAB_GENERAL))
        self._window.center()

        # Initial dynamic states
        self._apply_recording_mode_ui()
        self._update_permissions()
        self._refresh_login_checkbox()
        self._refresh_retract_controls()

    # --- Layout helpers ---

    def _tab_label(self, tab_id):
        return t(f"settings.tabs.{tab_id}")

    def _add_header(self, content, y, text):
        label = NSTextField.labelWithString_(text)
        label.setFrame_(NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 18))
        label.setFont_(NSFont.boldSystemFontOfSize_(13.0))
        content.addSubview_(label)
        box = NSBox.alloc().initWithFrame_(NSMakeRect(MARGIN, y - 7, WIN_W - 2 * MARGIN, 1))
        box.setBoxType_(NSBoxSeparator)
        content.addSubview_(box)

    def _add_field_label(self, content, y, text):
        label = NSTextField.labelWithString_(text)
        label.setFrame_(NSMakeRect(MARGIN, y, LABEL_W, 20))
        label.setAlignment_(2)  # NSTextAlignmentRight
        label.setTextColor_(NSColor.secondaryLabelColor())
        label.setFont_(NSFont.systemFontOfSize_(12.0))
        content.addSubview_(label)
        return label

    def _add_hint(self, content, y, text, x=CTRL_X, w=None):
        if w is None:
            w = WIN_W - x - MARGIN
        hint = NSTextField.labelWithString_(text)
        hint.setFrame_(NSMakeRect(x, y, w, 16))
        hint.setFont_(NSFont.systemFontOfSize_(11.0))
        hint.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(hint)
        return hint

    # --- Tab builders ---

    def _build_general_tab(self, content):
        y = CONTENT_H - 36

        # Recording mode
        self._add_header(content, y, t("settings.recording.title"))
        y -= 36
        self._add_field_label(content, y, t("settings.recording.mode"))
        self._mode_segmented = NSSegmentedControl.alloc().initWithFrame_(
            NSMakeRect(CTRL_X, y - 1, 260, 24)
        )
        self._mode_segmented.setSegmentCount_(2)
        self._mode_segmented.setLabel_forSegment_(t("settings.recording.toggle"), 0)
        self._mode_segmented.setLabel_forSegment_(t("settings.recording.push_to_talk"), 1)
        self._mode_segmented.setWidth_forSegment_(125, 0)
        self._mode_segmented.setWidth_forSegment_(125, 1)
        self._mode_segmented.setSelectedSegment_(
            1 if self._prefs.recording_mode == "hold" else 0
        )
        self._mode_segmented.setTarget_(self)
        self._mode_segmented.setAction_("recordingModeChanged:")
        content.addSubview_(self._mode_segmented)

        y -= 38
        self._mode_hotkey_label = self._add_field_label(
            content, y, t("settings.recording.toggle_shortcut")
        )
        self._shortcut_field = ShortcutField.alloc().initWithFrame_preferences_(
            NSMakeRect(CTRL_X, y, 200, 24), self._prefs
        )
        self._shortcut_field._on_change = self._update_hotkey_display
        content.addSubview_(self._shortcut_field)

        self._ptt_shortcut_field = (
            ShortcutField.alloc()
            .initWithFrame_preferences_keycodeKey_modifiersKey_allowModifierOnly_(
                NSMakeRect(CTRL_X, y, 200, 24),
                self._prefs,
                "ptt_hotkey_keycode",
                "ptt_hotkey_modifiers",
                True,
            )
        )
        self._ptt_shortcut_field._on_change = self._update_hotkey_display
        content.addSubview_(self._ptt_shortcut_field)

        change_btn = NSButton.alloc().initWithFrame_(NSMakeRect(CTRL_X + 208, y, 72, 24))
        change_btn.setTitle_(t("common.change"))
        change_btn.setBezelStyle_(NSBezelStyleRounded)
        change_btn.setTarget_(self)
        change_btn.setAction_("changeShortcut:")
        content.addSubview_(change_btn)

        y -= 26
        self._mode_hint = self._add_hint(content, y, t("settings.recording.toggle_hint"))

        # Correction
        y -= 40
        self._add_header(content, y, t("settings.correction.title"))

        y -= 32
        self._retract_checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20)
        )
        self._retract_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._retract_checkbox.setTitle_(t("settings.correction.enable"))
        self._retract_checkbox.setState_(
            1 if self._prefs.retract_last_dictation_enabled else 0
        )
        self._retract_checkbox.setTarget_(self)
        self._retract_checkbox.setAction_("retractShortcutToggled:")
        content.addSubview_(self._retract_checkbox)

        y -= 32
        self._retract_shortcut_field = (
            ShortcutField.alloc().initWithFrame_preferences_keycodeKey_modifiersKey_(
                NSMakeRect(MARGIN, y, 200, 24),
                self._prefs,
                "retract_hotkey_keycode",
                "retract_hotkey_modifiers",
            )
        )
        content.addSubview_(self._retract_shortcut_field)

        self._retract_change_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN + 208, y, 72, 24)
        )
        self._retract_change_btn.setTitle_(t("common.change"))
        self._retract_change_btn.setBezelStyle_(NSBezelStyleRounded)
        self._retract_change_btn.setTarget_(self)
        self._retract_change_btn.setAction_("changeRetractShortcut:")
        content.addSubview_(self._retract_change_btn)

        y -= 22
        self._add_hint(content, y, t("settings.correction.hint"), x=MARGIN)

    def _build_audio_tab(self, content):
        y = CONTENT_H - 36

        # Microphone
        self._add_header(content, y, t("settings.microphone.title"))
        y -= 36
        self._mic_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 24), False
        )
        self._populate_mics()
        self._mic_popup.setTarget_(self)
        self._mic_popup.setAction_("micChanged:")
        content.addSubview_(self._mic_popup)

        # Sound
        y -= 44
        self._add_header(content, y, t("settings.sound.title"))

        y -= 34
        self._start_sound_popup = self._build_sound_row(
            content, y, t("settings.sound.start"), self._prefs.start_volume,
            "startSoundChanged:", "startVolumeChanged:", "start"
        )

        y -= 34
        self._stop_sound_popup = self._build_sound_row(
            content, y, t("settings.sound.stop"), self._prefs.stop_volume,
            "stopSoundChanged:", "stopVolumeChanged:", "stop"
        )

        y -= 26
        self._add_hint(content, y, t("settings.sound.hint"), x=96)

        self._populate_sounds()

    def _build_sound_row(self, content, y, label_text, volume, sound_action,
                         volume_action, which):
        label = NSTextField.labelWithString_(label_text)
        label.setFrame_(NSMakeRect(MARGIN, y, 60, 20))
        label.setAlignment_(2)  # NSTextAlignmentRight
        label.setTextColor_(NSColor.secondaryLabelColor())
        label.setFont_(NSFont.systemFontOfSize_(12.0))
        content.addSubview_(label)

        popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(96, y, 150, 24), False
        )
        popup.setTarget_(self)
        popup.setAction_(sound_action)
        content.addSubview_(popup)

        slider = NSSlider.alloc().initWithFrame_(NSMakeRect(258, y, 150, 24))
        slider.setMinValue_(0)
        slider.setMaxValue_(100)
        slider.setIntValue_(int(volume * 100))
        slider.setContinuous_(True)
        slider.setTarget_(self)
        slider.setAction_(volume_action)
        content.addSubview_(slider)

        vol_label = NSTextField.labelWithString_(f"{int(volume * 100)}%")
        vol_label.setFrame_(NSMakeRect(416, y, 40, 20))
        vol_label.setTextColor_(NSColor.secondaryLabelColor())
        vol_label.setFont_(NSFont.systemFontOfSize_(11.0))
        content.addSubview_(vol_label)

        if which == "start":
            self._start_volume_slider = slider
            self._start_volume_label = vol_label
        else:
            self._stop_volume_slider = slider
            self._stop_volume_label = vol_label
        return popup

    def _build_language_tab(self, content):
        y = CONTENT_H - 36

        # Language
        self._add_header(content, y, t("settings.language.title"))

        y -= 36
        self._add_field_label(content, y, t("settings.language.ui_language"))
        self._ui_lang_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(CTRL_X, y, CTRL_W, 24), False
        )
        self._ui_lang_popup.addItemWithTitle_(t("common.system_default"))
        for code, native_name in SUPPORTED_LANGUAGES:
            self._ui_lang_popup.addItemWithTitle_(native_name)
        current_ui = self._prefs.ui_language
        if current_ui is None:
            self._ui_lang_popup.selectItemAtIndex_(0)
        else:
            selected = 0
            for i, (code, _) in enumerate(SUPPORTED_LANGUAGES):
                if code == current_ui:
                    selected = i + 1
                    break
            self._ui_lang_popup.selectItemAtIndex_(selected)
        self._ui_lang_popup.setTarget_(self)
        self._ui_lang_popup.setAction_("uiLanguageChanged:")
        content.addSubview_(self._ui_lang_popup)

        y -= 34
        self._add_field_label(content, y, t("settings.language.asr_language"))
        self._asr_lang_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(CTRL_X, y, CTRL_W, 24), False
        )
        self._asr_lang_popup.addItemWithTitle_(t("common.automatic"))
        for code, native_name in SUPPORTED_LANGUAGES:
            self._asr_lang_popup.addItemWithTitle_(native_name)
        current_asr = self._prefs.asr_language
        if current_asr == "auto":
            self._asr_lang_popup.selectItemAtIndex_(0)
        else:
            selected = 0
            for i, (code, _) in enumerate(SUPPORTED_LANGUAGES):
                if code == current_asr:
                    selected = i + 1
                    break
            self._asr_lang_popup.selectItemAtIndex_(selected)
        self._asr_lang_popup.setTarget_(self)
        self._asr_lang_popup.setAction_("asrLanguageChanged:")
        content.addSubview_(self._asr_lang_popup)

        # Custom Words
        y -= 44
        self._add_header(content, y, t("settings.custom_words.title"))

        y -= 32
        self._custom_words_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 24)
        )
        self._custom_words_field.setStringValue_(self._prefs.custom_words)
        self._custom_words_field.setPlaceholderString_(t("settings.custom_words.placeholder"))
        self._custom_words_field.setDelegate_(self)
        content.addSubview_(self._custom_words_field)

        y -= 22
        self._add_hint(content, y, t("settings.custom_words.hint"), x=MARGIN)

    def _build_model_tab(self, content):
        y = CONTENT_H - 36

        # On-device model
        self._add_header(content, y, t("settings.model.title"))

        y -= 28
        model_label = NSTextField.labelWithString_(self._prefs.model_id)
        model_label.setFrame_(NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20))
        model_label.setTextColor_(NSColor.secondaryLabelColor())
        model_label.setFont_(NSFont.systemFontOfSize_(11.0))
        content.addSubview_(model_label)

        # Remote server (optional — empty means transcribe on this Mac)
        y -= 44
        self._add_header(content, y, t("settings.remote.title"))

        y -= 32
        test_w = 64
        self._stt_endpoint_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN - test_w - 8, 24)
        )
        self._stt_endpoint_field.setStringValue_(self._prefs.stt_endpoint)
        self._stt_endpoint_field.setPlaceholderString_(t("settings.remote.placeholder"))
        self._stt_endpoint_field.setDelegate_(self)
        content.addSubview_(self._stt_endpoint_field)

        # A wrong address fails silently — it just falls back to on-device, which
        # looks like nothing happened. This is the only way to see it.
        self._stt_test_btn = NSButton.alloc().initWithFrame_(
            NSMakeRect(RIGHT - test_w, y, test_w, 24)
        )
        self._stt_test_btn.setTitle_(t("settings.remote.test"))
        self._stt_test_btn.setBezelStyle_(NSBezelStyleRounded)
        self._stt_test_btn.setTarget_(self)
        self._stt_test_btn.setAction_("testEndpoint:")
        content.addSubview_(self._stt_test_btn)

        y -= 22
        self._stt_hint = self._add_hint(content, y, t("settings.remote.hint"), x=MARGIN)

        # The corrector is a plain OpenAI-compatible chat endpoint, entirely separate
        # from the ASR server above — it works with on-device ASR too. Its fields come
        # before the checkbox they gate, because a disabled checkbox above the field
        # that enables it reads as broken.
        y -= 40
        self._add_header(content, y, t("settings.remote.llm_title"))

        y -= 30
        self._llm_endpoint_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 24)
        )
        self._llm_endpoint_field.setStringValue_(self._prefs.llm_endpoint)
        self._llm_endpoint_field.setPlaceholderString_(t("settings.remote.llm_placeholder"))
        self._llm_endpoint_field.setDelegate_(self)
        content.addSubview_(self._llm_endpoint_field)

        y -= 28
        self._llm_model_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 24)
        )
        self._llm_model_field.setStringValue_(self._prefs.llm_model)
        self._llm_model_field.setPlaceholderString_(t("settings.remote.llm_model_placeholder"))
        self._llm_model_field.setDelegate_(self)
        content.addSubview_(self._llm_model_field)

        # Without this the corrector has no domain to anchor on and leaves jargon
        # mangled — measured, not theoretical, so it gets a field rather than a file.
        y -= 28
        self._llm_context_field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 24)
        )
        self._llm_context_field.setStringValue_(self._prefs.llm_context)
        self._llm_context_field.setPlaceholderString_(
            t("settings.remote.llm_context_placeholder")
        )
        self._llm_context_field.setDelegate_(self)
        content.addSubview_(self._llm_context_field)

        y -= 20
        self._add_hint(content, y, t("settings.remote.llm_hint"), x=MARGIN)

        y -= 28
        self._stt_correction_checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20)
        )
        self._stt_correction_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._stt_correction_checkbox.setTitle_(t("settings.remote.correction"))
        self._stt_correction_checkbox.setTarget_(self)
        self._stt_correction_checkbox.setAction_("sttCorrectionToggled:")
        content.addSubview_(self._stt_correction_checkbox)

        y -= 22
        self._stt_correction_hint = self._add_hint(
            content, y, t("settings.remote.correction_hint"), x=MARGIN
        )

        y -= 28
        self._screen_context_checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20)
        )
        self._screen_context_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._screen_context_checkbox.setTitle_(t("settings.remote.screen_context"))
        self._screen_context_checkbox.setTarget_(self)
        self._screen_context_checkbox.setAction_("screenContextToggled:")
        content.addSubview_(self._screen_context_checkbox)

        y -= 22
        self._screen_context_hint = self._add_hint(
            content, y, t("settings.remote.screen_context_hint"), x=MARGIN
        )

        self._refresh_remote_controls()

    def _build_system_tab(self, content):
        y = CONTENT_H - 36

        # Permissions
        self._add_header(content, y, t("settings.permissions.title"))

        y -= 34
        self._acc_label = NSTextField.labelWithString_(
            t("settings.permissions.accessibility_checking")
        )
        self._acc_label.setFrame_(NSMakeRect(MARGIN, y, 300, 20))
        content.addSubview_(self._acc_label)

        acc_btn = NSButton.alloc().initWithFrame_(NSMakeRect(RIGHT - 72, y, 72, 24))
        acc_btn.setTitle_(t("common.open"))
        acc_btn.setBezelStyle_(NSBezelStyleRounded)
        acc_btn.setTarget_(self)
        acc_btn.setAction_("openAccessibility:")
        content.addSubview_(acc_btn)

        y -= 32
        self._mic_label = NSTextField.labelWithString_(
            t("settings.permissions.microphone_checking")
        )
        self._mic_label.setFrame_(NSMakeRect(MARGIN, y, 300, 20))
        content.addSubview_(self._mic_label)

        mic_perm_btn = NSButton.alloc().initWithFrame_(NSMakeRect(RIGHT - 72, y, 72, 24))
        mic_perm_btn.setTitle_(t("common.open"))
        mic_perm_btn.setBezelStyle_(NSBezelStyleRounded)
        mic_perm_btn.setTarget_(self)
        mic_perm_btn.setAction_("openMicrophonePrivacy:")
        content.addSubview_(mic_perm_btn)

        # Startup & Updates
        y -= 44
        self._add_header(content, y, t("settings.startup.title"))

        y -= 32
        self._login_checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20)
        )
        self._login_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._login_checkbox.setTitle_(t("settings.login.title"))
        self._login_checkbox.setState_(1 if self._prefs.launch_at_login else 0)
        self._login_checkbox.setTarget_(self)
        self._login_checkbox.setAction_("loginToggled:")
        content.addSubview_(self._login_checkbox)

        y -= 30
        self._update_checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(MARGIN, y, WIN_W - 2 * MARGIN, 20)
        )
        self._update_checkbox.setButtonType_(NSButtonTypeSwitch)
        self._update_checkbox.setTitle_(t("settings.update.title"))
        self._update_checkbox.setState_(1 if self._auto_update_check_enabled() else 0)
        self._update_checkbox.setTarget_(self)
        self._update_checkbox.setAction_("updateCheckToggled:")
        content.addSubview_(self._update_checkbox)

    # --- Toolbar delegate ---

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return list(_TAB_IDS)

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return list(_TAB_IDS)

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return list(_TAB_IDS)

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(
        self, toolbar, identifier, flag
    ):
        item = NSToolbarItem.alloc().initWithItemIdentifier_(identifier)
        item.setLabel_(self._tab_label(identifier))
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            _TAB_ICONS.get(identifier, "gearshape"), None
        )
        if image is not None:
            item.setImage_(image)
        item.setTarget_(self)
        item.setAction_("tabSelected:")
        return item

    @objc.typedSelector(b"v@:@")
    def tabSelected_(self, sender):
        identifier = sender.itemIdentifier()
        self._tab_view.selectTabViewItemWithIdentifier_(identifier)
        self._window.setTitle_(self._tab_label(identifier))
        self._window.toolbar().setSelectedItemIdentifier_(identifier)

    # --- Recording mode ---

    @objc.typedSelector(b"v@:@")
    def recordingModeChanged_(self, sender):
        mode = "hold" if sender.selectedSegment() == 1 else "toggle"
        self._prefs.recording_mode = mode
        self._apply_recording_mode_ui()
        self._update_hotkey_display()

    def _apply_recording_mode_ui(self):
        hold = self._prefs.recording_mode == "hold"
        if self._mode_segmented is not None:
            self._mode_segmented.setSelectedSegment_(1 if hold else 0)
        if self._shortcut_field is not None:
            self._shortcut_field.setHidden_(hold)
        if self._ptt_shortcut_field is not None:
            self._ptt_shortcut_field.setHidden_(not hold)
        if self._mode_hotkey_label is not None:
            self._mode_hotkey_label.setStringValue_(
                t("settings.recording.ptt_shortcut") if hold
                else t("settings.recording.toggle_shortcut")
            )
        if self._mode_hint is not None:
            self._mode_hint.setStringValue_(
                t("settings.recording.ptt_hint") if hold
                else t("settings.recording.toggle_hint")
            )

    def _populate_sounds(self):
        """Populate both sound dropdowns with system sounds + Custom option."""
        system_sounds = sounds.list_system_sounds()
        for popup, pref_value in [
            (self._start_sound_popup, self._prefs.sound_start),
            (self._stop_sound_popup, self._prefs.sound_stop),
        ]:
            popup.removeAllItems()
            for name in system_sounds:
                popup.addItemWithTitle_(name)
            popup.menu().addItem_(NSMenuItem.separatorItem())
            popup.addItemWithTitle_(t("settings.sound.custom"))

            # Select current value
            if sounds.is_custom_path(pref_value):
                filename = os.path.basename(pref_value)
                if filename:  # guard against empty/malformed paths
                    popup.insertItemWithTitle_atIndex_(filename, len(system_sounds))
                    popup.selectItemAtIndex_(len(system_sounds))
            else:
                idx = popup.indexOfItemWithTitle_(pref_value)
                if idx >= 0:
                    popup.selectItemAtIndex_(idx)

    def _populate_mics(self):
        self._mic_popup.removeAllItems()
        devices = list_input_devices()
        default_device = get_default_input_device(devices)
        default_label = t("common.system_default")
        if default_device is not None:
            default_label = f"{t('common.system_default')} ({default_device.name})"
        self._mic_popup.addItemWithTitle_(default_label)

        self._mic_device_ids = [None]
        current = self._prefs.mic_device
        selected_idx = 0
        selected_device = resolve_input_device(current, devices)

        for device in devices:
            self._mic_popup.addItemWithTitle_(device.display_name)
            self._mic_device_ids.append(device.device_id)
            if selected_device is not None and selected_device.device_id == device.device_id:
                selected_idx = self._mic_popup.numberOfItems() - 1

        self._mic_popup.selectItemAtIndex_(selected_idx)

    def _update_permissions(self):
        trusted = ApplicationServices.AXIsProcessTrusted()
        if trusted:
            self._acc_label.setStringValue_(t("settings.permissions.accessibility_granted"))
        else:
            self._acc_label.setStringValue_(t("settings.permissions.accessibility_not_granted"))

        mic_authorized = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        ) == 3  # AVAuthorizationStatusAuthorized
        if mic_authorized:
            self._mic_label.setStringValue_(t("settings.permissions.microphone_granted"))
        else:
            self._mic_label.setStringValue_(t("settings.permissions.microphone_not_granted"))

    def showWindow_(self, sender):
        self._populate_mics()
        self._populate_sounds()
        self._window.makeKeyAndOrderFront_(sender)
        NSApp.activateIgnoringOtherApps_(True)
        self._permission_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, "pollPermissions:", None, True
        )

    def window(self):
        return self._window

    def windowWillClose_(self, notification):
        self._save_custom_words()
        self._save_stt_endpoint()
        if self._llm_endpoint_field is not None:
            self._prefs.llm_endpoint = self._llm_endpoint_field.stringValue().strip()
        if self._permission_timer:
            self._permission_timer.invalidate()
            self._permission_timer = None

    def _save_custom_words(self):
        if self._custom_words_field is None:
            return
        self._prefs.custom_words = self._custom_words_field.stringValue()

    def _save_stt_endpoint(self):
        if self._stt_endpoint_field is None:
            return
        self._prefs.stt_endpoint = self._stt_endpoint_field.stringValue().strip()
        self._refresh_remote_controls()

    @objc.typedSelector(b"v@:@")
    def testEndpoint_(self, sender):
        self._save_stt_endpoint()
        url = self._prefs.stt_endpoint.strip()
        if not url:
            return
        self._stt_test_btn.setEnabled_(False)
        self._set_hint(t("settings.remote.testing"), NSColor.secondaryLabelColor())
        threading.Thread(target=self._run_endpoint_test, args=(url,), daemon=True).start()

    def _run_endpoint_test(self, url):
        """Off the main thread — a dead host blocks for the whole timeout."""
        import requests

        from vvrite.transcriber import _endpoint

        try:
            # Normalise exactly as transcription does, so the test cannot pass
            # against a different URL than the one dictation will use.
            resp = requests.get(f"{_endpoint(self._prefs)}/health", timeout=5)
            resp.raise_for_status()
            try:
                body = resp.json()
            except ValueError:
                # A non-JSON /health means this is some other service — most
                # likely the LLM endpoint pasted into the ASR field.
                raise ValueError(t("settings.remote.not_asr")) from None
            if not body.get("ok"):
                raise ValueError(t("settings.remote.not_ready"))
            message = t("settings.remote.ok", model=body.get("model", "?"))
            ok = True
        except Exception as e:
            message = t("settings.remote.fail", error=str(e).split("\n")[0][:60])
            ok = False
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "endpointTestFinished:", (message, ok), False
        )

    @objc.typedSelector(b"v@:@")
    def endpointTestFinished_(self, payload):
        message, ok = payload
        self._stt_test_btn.setEnabled_(True)
        self._set_hint(
            message,
            NSColor.systemGreenColor() if ok else NSColor.systemRedColor(),
        )

    def _set_hint(self, text, color):
        if self._stt_hint is not None:
            self._stt_hint.setStringValue_(text)
            self._stt_hint.setTextColor_(color)

    def _refresh_remote_controls(self):
        """Correction needs an LLM, not a remote ASR server.

        It used to be gated on stt_endpoint, from when the ASR server did the
        correcting — which left the checkbox greyed out for exactly the setup it now
        supports best: on-device ASR plus a remote corrector.
        """
        if self._stt_correction_checkbox is None:
            return
        # The model name is required too: vLLM answers 400 to a blank one, and the
        # correction then fails open so silently that it looks like it is just off.
        has_llm = bool(self._prefs.llm_endpoint.strip() and self._prefs.llm_model.strip())
        self._stt_correction_checkbox.setEnabled_(has_llm)
        self._stt_correction_checkbox.setState_(1 if self._prefs.stt_correction else 0)
        if self._stt_correction_hint is not None:
            self._stt_correction_hint.setTextColor_(
                NSColor.secondaryLabelColor() if has_llm else NSColor.tertiaryLabelColor()
            )

        if self._screen_context_checkbox is None:
            return
        # Screen text is only ever consumed by the corrector.
        correcting = has_llm and self._prefs.stt_correction
        self._screen_context_checkbox.setEnabled_(correcting)
        self._screen_context_checkbox.setState_(1 if self._prefs.screen_context else 0)
        if self._screen_context_hint is not None:
            self._screen_context_hint.setTextColor_(
                NSColor.secondaryLabelColor() if correcting else NSColor.tertiaryLabelColor()
            )

    @objc.typedSelector(b"v@:@")
    def sttCorrectionToggled_(self, sender):
        self._prefs.stt_correction = sender.state() == 1
        self._refresh_remote_controls()

    @objc.typedSelector(b"v@:@")
    def screenContextToggled_(self, sender):
        enabled = sender.state() == 1
        self._prefs.screen_context = enabled
        # Ask for Screen Recording now rather than silently returning no terms on the
        # next dictation. The first capture attempt is what triggers the system prompt.
        if enabled:
            screen.capture_async()

    @objc.typedSelector(b"v@:@")
    def pollPermissions_(self, timer):
        self._update_permissions()

    def _update_hotkey_display(self):
        delegate = NSApp.delegate()
        if delegate and delegate._status_bar:
            hotkey_str = format_shortcut(*active_shortcut(self._prefs))
            delegate._status_bar.setHotkeyDisplay_(hotkey_str)

    @objc.typedSelector(b"v@:@")
    def changeShortcut_(self, sender):
        if self._prefs.recording_mode == "hold":
            self._ptt_shortcut_field.startCapture()
        else:
            self._shortcut_field.startCapture()

    @objc.typedSelector(b"v@:@")
    def changeRetractShortcut_(self, sender):
        self._retract_shortcut_field.startCapture()

    @objc.typedSelector(b"v@:@")
    def retractShortcutToggled_(self, sender):
        self._prefs.retract_last_dictation_enabled = sender.state() == 1
        self._refresh_retract_controls()

    @objc.typedSelector(b"v@:@")
    def micChanged_(self, sender):
        index = sender.indexOfSelectedItem()
        if index <= 0:
            self._prefs.mic_device = None
        else:
            self._prefs.mic_device = self._mic_device_ids[index]

    @objc.typedSelector(b"v@:@")
    def uiLanguageChanged_(self, sender):
        index = sender.indexOfSelectedItem()
        if index == 0:
            self._prefs.ui_language = None
        else:
            code = SUPPORTED_LANGUAGES[index - 1][0]
            self._prefs.ui_language = code

        # Show restart dialog
        alert = NSAlert.alloc().init()
        alert.setMessageText_(t("settings.language.restart_message"))
        alert.addButtonWithTitle_(t("settings.language.restart_now"))
        alert.addButtonWithTitle_(t("common.later"))
        response = alert.runModal()

        # Close this window and invalidate cached settings window
        self._window.close()
        from AppKit import NSApp
        delegate = NSApp.delegate()
        if hasattr(delegate, 'invalidateSettingsWindow'):
            delegate.invalidateSettingsWindow()

        if response == NSAlertFirstButtonReturn:
            # Restart the app
            import subprocess
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle().bundlePath()
            subprocess.Popen(["/usr/bin/open", "-n", bundle])
            NSApp.terminate_(None)

    @objc.typedSelector(b"v@:@")
    def asrLanguageChanged_(self, sender):
        index = sender.indexOfSelectedItem()
        if index == 0:
            self._prefs.asr_language = "auto"
        else:
            code = SUPPORTED_LANGUAGES[index - 1][0]
            self._prefs.asr_language = code

    @objc.typedSelector(b"v@:@")
    def loginToggled_(self, sender):
        enabled = sender.state() == 1
        try:
            actual_state = launch_at_login.set_enabled(enabled)
            self._prefs.launch_at_login = actual_state
        except launch_at_login.LaunchAtLoginError as e:
            NSLog(f"Launch at login toggle failed: {e}")
            self._show_launch_at_login_error(str(e))
        finally:
            self._refresh_login_checkbox()

    @objc.typedSelector(b"v@:@")
    def updateCheckToggled_(self, sender):
        enabled = sender.state() == 1
        delegate = NSApp.delegate()
        if hasattr(delegate, "setAutoUpdateCheckEnabled"):
            delegate.setAutoUpdateCheckEnabled(enabled)
        else:
            self._prefs.auto_update_check = enabled

    def _auto_update_check_enabled(self) -> bool:
        delegate = NSApp.delegate()
        if hasattr(delegate, "autoUpdateCheckEnabled"):
            enabled = delegate.autoUpdateCheckEnabled()
            if enabled is not None:
                return bool(enabled)
        return bool(self._prefs.auto_update_check)

    def controlTextDidEndEditing_(self, notification):
        field = notification.object()
        if field == self._custom_words_field:
            self._save_custom_words()
        elif field == self._stt_endpoint_field:
            self._save_stt_endpoint()
        elif field == self._llm_endpoint_field:
            self._prefs.llm_endpoint = self._llm_endpoint_field.stringValue().strip()
            # The correction checkbox is gated on this field, so without a refresh
            # here the only way to reach it was to close and reopen Settings.
            self._refresh_remote_controls()
        elif field == self._llm_model_field:
            self._prefs.llm_model = self._llm_model_field.stringValue().strip()
            self._refresh_remote_controls()
        elif field == self._llm_context_field:
            self._prefs.llm_context = self._llm_context_field.stringValue().strip()

    @objc.typedSelector(b"v@:@")
    def openAccessibility_(self, sender):
        url = NSURL.URLWithString_(
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
        )
        NSWorkspace.sharedWorkspace().openURL_(url)

    @objc.typedSelector(b"v@:@")
    def openMicrophonePrivacy_(self, sender):
        url = NSURL.URLWithString_(
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
        )
        NSWorkspace.sharedWorkspace().openURL_(url)

    def _refresh_login_checkbox(self):
        if self._login_checkbox is None:
            return

        support_error = launch_at_login.support_error()
        if support_error:
            self._login_checkbox.setEnabled_(False)
            self._login_checkbox.setState_(1 if self._prefs.launch_at_login else 0)
            return

        self._login_checkbox.setEnabled_(True)
        actual_state = launch_at_login.is_registered()
        self._prefs.launch_at_login = actual_state
        self._login_checkbox.setState_(1 if actual_state else 0)

    def _refresh_retract_controls(self):
        enabled = bool(self._prefs.retract_last_dictation_enabled)
        if self._retract_checkbox is not None:
            self._retract_checkbox.setState_(1 if enabled else 0)
        if self._retract_shortcut_field is not None:
            self._retract_shortcut_field.setEnabled_(enabled)
        if self._retract_change_btn is not None:
            self._retract_change_btn.setEnabled_(enabled)

    @objc.typedSelector(b"v@:@")
    def startSoundChanged_(self, sender):
        title = sender.titleOfSelectedItem()
        if title == t("settings.sound.custom"):
            self.performSelector_withObject_afterDelay_(
                "openStartCustomSoundPanel:", None, 0.0
            )
            return
        # If re-selecting the custom file entry, keep the full path
        current = self._prefs.sound_start
        if sounds.is_custom_path(current) and os.path.basename(current) == title:
            sounds.play(current, self._prefs.start_volume)
            return
        self._prefs.sound_start = title
        sounds.play(title, self._prefs.start_volume)

    @objc.typedSelector(b"v@:@")
    def stopSoundChanged_(self, sender):
        title = sender.titleOfSelectedItem()
        if title == t("settings.sound.custom"):
            self.performSelector_withObject_afterDelay_(
                "openStopCustomSoundPanel:", None, 0.0
            )
            return
        # If re-selecting the custom file entry, keep the full path
        current = self._prefs.sound_stop
        if sounds.is_custom_path(current) and os.path.basename(current) == title:
            sounds.play(current, self._prefs.stop_volume)
            return
        self._prefs.sound_stop = title
        sounds.play(title, self._prefs.stop_volume)

    @objc.typedSelector(b"v@:@")
    def startVolumeChanged_(self, sender):
        vol = sender.intValue() / 100.0
        self._prefs.start_volume = vol
        self._start_volume_label.setStringValue_(f"{sender.intValue()}%")
        # Play preview only on mouse-up (NSEventTypeLeftMouseUp == 2)
        event = NSApp.currentEvent()
        if event and event.type() == 2:
            sounds.play(self._prefs.sound_start, vol)

    @objc.typedSelector(b"v@:@")
    def stopVolumeChanged_(self, sender):
        vol = sender.intValue() / 100.0
        self._prefs.stop_volume = vol
        self._stop_volume_label.setStringValue_(f"{sender.intValue()}%")
        # Play preview only on mouse-up (NSEventTypeLeftMouseUp == 2)
        event = NSApp.currentEvent()
        if event and event.type() == 2:
            sounds.play(self._prefs.sound_stop, vol)

    def _open_custom_sound_panel(self, for_start: bool):
        NSApp.activateIgnoringOtherApps_(True)
        if self._window is not None:
            self._window.makeKeyAndOrderFront_(None)

        panel = NSOpenPanel.openPanel()
        panel.setAllowedFileTypes_(["aiff", "wav", "mp3", "m4a", "caf"])
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(False)
        panel.setTitle_(t("settings.sound.choose_file"))

        if self._window is not None:
            panel.beginSheetModalForWindow_completionHandler_(
                self._window,
                lambda response: self._handle_custom_sound_panel_result(
                    response, panel, for_start
                ),
            )
            return

        self._handle_custom_sound_panel_result(panel.runModal(), panel, for_start)

    def _handle_custom_sound_panel_result(self, response, panel, for_start: bool):
        if response == 1:  # NSModalResponseOK
            path = str(panel.URL().path())
            if for_start:
                self._prefs.sound_start = path
                sounds.play(path, self._prefs.start_volume)
            else:
                self._prefs.sound_stop = path
                sounds.play(path, self._prefs.stop_volume)

        # Rebuild the popup in both the success and cancel paths so it reflects
        # the persisted selection rather than the transient "Custom..." item.
        self._populate_sounds()

    @objc.typedSelector(b"v@:@")
    def openStartCustomSoundPanel_(self, _sender):
        self._open_custom_sound_panel(True)

    @objc.typedSelector(b"v@:@")
    def openStopCustomSoundPanel_(self, _sender):
        self._open_custom_sound_panel(False)

    def _show_launch_at_login_error(self, message):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(t("settings.login.error"))
        alert.setInformativeText_(message)
        alert.runModal()
