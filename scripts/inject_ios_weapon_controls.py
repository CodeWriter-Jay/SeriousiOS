#!/usr/bin/env python3
"""Inject weapon switching, scope, optional controls, layout editing, and export diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path


WEAPON_IVARS = r'''    UIButton* _nextWeaponButton;
    UIButton* _prevWeaponButton;
    UIButton* _scopeButton;
    UIButton* _crouchButton;
    UIButton* _computerButton;
    UIButton* _quickSaveButton;
    UIButton* _editControlsButton;
    BOOL _crouchButtonEnabled;
    BOOL _computerButtonEnabled;
    BOOL _quickSaveButtonEnabled;
    UIButton* _selectedControlButton;
    UILabel* _selectedControlNameLabel;
    UISlider* _controlSizeSlider;
    UILabel* _controlSizeValueLabel;
    UISlider* _controlOpacitySlider;
    UILabel* _controlOpacityValueLabel;
    UISwitch* _crouchSwitch;
    UISwitch* _computerSwitch;
    UISwitch* _quickSaveSwitch;
    UIButton* _exportDiagnosticsButton;
'''

WEAPON_METHODS = r'''- (void)gameplayNextWeaponDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_NEXT_WEAPON, true);
}

- (void)gameplayNextWeaponUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_NEXT_WEAPON, false);
}

- (void)gameplayPrevWeaponDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_PREVIOUS_WEAPON, true);
}

- (void)gameplayPrevWeaponUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_PREVIOUS_WEAPON, false);
}

- (void)gameplayScopeDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_ALT_FIRE, true);
}

- (void)gameplayScopeUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_ALT_FIRE, false);
}

- (void)gameplayCrouchDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_CROUCH, true);
}

- (void)gameplayCrouchUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_CROUCH, false);
}

- (void)gameplayComputerDown {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_COMPUTER, true);
}

- (void)gameplayComputerUp {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_COMPUTER, false);
}

- (void)gameplayQuickSaveTap {
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_QUICK_SAVE, true);
    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_QUICK_SAVE, false);
}

- (void)selectControlButtonForEditing:(UIButton*)button {
    if (button == nil) {
        return;
    }
    _selectedControlButton = button;
    for (UIButton* b in [self gameplayControlButtons]) {
        if (b == button) {
            b.layer.borderColor = [UIColor colorWithRed:0.28 green:0.68 blue:1.0 alpha:0.98].CGColor;
            b.layer.borderWidth = 3.0;
        } else {
            b.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.58].CGColor;
            b.layer.borderWidth = 1.4;
        }
    }
    _selectedControlNameLabel.text = [NSString stringWithFormat:@"Selected: %@", button.accessibilityLabel ?: @"Control"];
    const CGFloat currentSize = MAX(CGRectGetWidth(button.bounds), CGRectGetHeight(button.bounds));
    _controlSizeSlider.value = (float)currentSize;
    _controlSizeValueLabel.text = [NSString stringWithFormat:@"%.0f pt", currentSize];
    _controlOpacitySlider.value = (float)button.alpha;
    _controlOpacityValueLabel.text = [NSString stringWithFormat:@"%.0f%%", button.alpha * 100.0];
}

- (void)controlButtonTapped:(UITapGestureRecognizer*)gesture {
    if (_controlsEditorVisible && [gesture.view isKindOfClass:UIButton.class]) {
        [self selectControlButtonForEditing:(UIButton*)gesture.view];
    }
}

- (void)controlSizeSliderChanged:(UISlider*)sender {
    if (_selectedControlButton == nil) {
        return;
    }
    const CGFloat size = sender.value;
    const CGPoint center = _selectedControlButton.center;
    _selectedControlButton.bounds = CGRectMake(0.0, 0.0, size, size);
    _selectedControlButton.center = center;
    _selectedControlButton.frame = [self clampedControlFrame:_selectedControlButton.frame];
    [self updateControlButtonCorners];
    _controlSizeValueLabel.text = [NSString stringWithFormat:@"%.0f pt", size];
    [self persistControlFrameForButton:_selectedControlButton];
}

- (void)controlOpacitySliderChanged:(UISlider*)sender {
    if (_selectedControlButton == nil) {
        return;
    }
    _selectedControlButton.alpha = sender.value;
    _controlOpacityValueLabel.text = [NSString stringWithFormat:@"%.0f%%", sender.value * 100.0];
    NSString* opacityKey = [@"SeriousIOS.TouchControlOpacity." stringByAppendingString:_selectedControlButton.accessibilityIdentifier ?: @"unknown"];
    [NSUserDefaults.standardUserDefaults setDouble:sender.value forKey:opacityKey];
}

- (void)crouchSwitchChanged:(UISwitch*)sender {
    _crouchButtonEnabled = sender.isOn;
    [NSUserDefaults.standardUserDefaults setBool:_crouchButtonEnabled forKey:@"SeriousIOS.CrouchButtonEnabled"];
    [self updateGameplayControlVisibility];
}

- (void)computerSwitchChanged:(UISwitch*)sender {
    _computerButtonEnabled = sender.isOn;
    [NSUserDefaults.standardUserDefaults setBool:_computerButtonEnabled forKey:@"SeriousIOS.ComputerButtonEnabled"];
    [self updateGameplayControlVisibility];
}

- (void)quickSaveSwitchChanged:(UISwitch*)sender {
    _quickSaveButtonEnabled = sender.isOn;
    [NSUserDefaults.standardUserDefaults setBool:_quickSaveButtonEnabled forKey:@"SeriousIOS.QuickSaveButtonEnabled"];
    [self updateGameplayControlVisibility];
}

- (void)exportDiagnosticsTapped {
    [self exportDiagnostics];
}

- (void)editControlsTapped {
    [self showControlsEditor];
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_text(text: str) -> str:
    # 1. Add IVARs
    text = replace_once(
        text,
        "    UIButton* _returnToGameButton;\n",
        "    UIButton* _returnToGameButton;\n" + WEAPON_IVARS,
        "weapon control ivars",
    )

    # 2. Make _controlsEditorPanel a UIScrollView
    text = replace_once(
        text,
        "    UIView* _controlsEditorPanel;\n",
        "    UIScrollView* _controlsEditorPanel;\n",
        "editor panel ivar type",
    )
    text = replace_once(
        text,
        "    _controlsEditorPanel = [[UIView alloc] initWithFrame:CGRectZero];",
        '''    _controlsEditorPanel = [[UIScrollView alloc] initWithFrame:CGRectZero];
    _controlsEditorPanel.alwaysBounceVertical = YES;
    _controlsEditorPanel.showsVerticalScrollIndicator = YES;
    _controlsEditorPanel.clipsToBounds = YES;''',
        "editor panel scrollview alloc",
    )

    # 3. Add methods
    text = replace_once(
        text,
        "- (void)touchSensitivityChanged:(UISlider*)sender {\n",
        WEAPON_METHODS + "\n- (void)touchSensitivityChanged:(UISlider*)sender {\n",
        "weapon control methods",
    )

    # 4. Expand gameplayControlButtons array
    old_buttons = "    return @[_fireButton, _jumpButton, _useButton, _pauseButton];"
    new_buttons = (
        "    return @[_fireButton, _jumpButton, _useButton, _pauseButton,\n"
        "             _nextWeaponButton, _prevWeaponButton, _scopeButton,\n"
        "             _crouchButton, _computerButton, _quickSaveButton];"
    )
    text = replace_once(text, old_buttons, new_buttons, "expand editable controls list")

    # 5. Initialize defaults in configureAdvancedTouchControls
    old_defaults = '    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil'
    new_defaults = '''    _crouchButtonEnabled = [defaults objectForKey:@"SeriousIOS.CrouchButtonEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.CrouchButtonEnabled"]
        : NO;
    _computerButtonEnabled = [defaults objectForKey:@"SeriousIOS.ComputerButtonEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.ComputerButtonEnabled"]
        : NO;
    _quickSaveButtonEnabled = [defaults objectForKey:@"SeriousIOS.QuickSaveButtonEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.QuickSaveButtonEnabled"]
        : NO;
    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil'''
    text = replace_once(text, old_defaults, new_defaults, "read optional control defaults")

    # 6. Instantiate and style buttons in init / setup
    button_creation_anchor = '''    [_pauseButton addTarget:self action:@selector(gameplayPause)
          forControlEvents:UIControlEventTouchUpInside];'''
    button_creation_new = '''    [_pauseButton addTarget:self action:@selector(gameplayPause)
          forControlEvents:UIControlEventTouchUpInside];

    _nextWeaponButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_nextWeaponButton
                      symbol:@"chevron.right.circle.fill"
                    fallback:@"forward.fill"
                       label:@"Next Weapon"
                  identifier:@"next-weapon"];
    [_nextWeaponButton addTarget:self action:@selector(gameplayNextWeaponDown) forControlEvents:UIControlEventTouchDown];
    [_nextWeaponButton addTarget:self action:@selector(gameplayNextWeaponUp) forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [self addSubview:_nextWeaponButton];

    _prevWeaponButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_prevWeaponButton
                      symbol:@"chevron.left.circle.fill"
                    fallback:@"backward.fill"
                       label:@"Previous Weapon"
                  identifier:@"prev-weapon"];
    [_prevWeaponButton addTarget:self action:@selector(gameplayPrevWeaponDown) forControlEvents:UIControlEventTouchDown];
    [_prevWeaponButton addTarget:self action:@selector(gameplayPrevWeaponUp) forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [self addSubview:_prevWeaponButton];

    _scopeButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_scopeButton
                      symbol:@"viewfinder"
                    fallback:@"scope"
                       label:@"Scope"
                  identifier:@"scope"];
    [_scopeButton addTarget:self action:@selector(gameplayScopeDown) forControlEvents:UIControlEventTouchDown];
    [_scopeButton addTarget:self action:@selector(gameplayScopeUp) forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [self addSubview:_scopeButton];

    _crouchButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_crouchButton
                      symbol:@"arrow.down.to.line"
                    fallback:@"chevron.down"
                       label:@"Crouch"
                  identifier:@"crouch"];
    [_crouchButton addTarget:self action:@selector(gameplayCrouchDown) forControlEvents:UIControlEventTouchDown];
    [_crouchButton addTarget:self action:@selector(gameplayCrouchUp) forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [self addSubview:_crouchButton];

    _computerButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_computerButton
                      symbol:@"display"
                    fallback:@"desktopcomputer"
                       label:@"NETRICSA"
                  identifier:@"computer"];
    [_computerButton addTarget:self action:@selector(gameplayComputerDown) forControlEvents:UIControlEventTouchDown];
    [_computerButton addTarget:self action:@selector(gameplayComputerUp) forControlEvents:UIControlEventTouchUpInside | UIControlEventTouchUpOutside | UIControlEventTouchCancel];
    [self addSubview:_computerButton];

    _quickSaveButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self styleControlButton:_quickSaveButton
                      symbol:@"square.and.arrow.down.fill"
                    fallback:@"tray.and.arrow.down.fill"
                       label:@"Quick Save"
                  identifier:@"quick-save"];
    [_quickSaveButton addTarget:self action:@selector(gameplayQuickSaveTap) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_quickSaveButton];

    _editControlsButton = [UIButton buttonWithType:UIButtonTypeSystem];
    UIButtonConfiguration* editControlsConfiguration = [UIButtonConfiguration tintedButtonConfiguration];
    editControlsConfiguration.title = @"Customize Controls";
    editControlsConfiguration.baseForegroundColor = UIColor.whiteColor;
    editControlsConfiguration.baseBackgroundColor = [UIColor colorWithRed:0.12 green:0.35 blue:0.75 alpha:0.80];
    editControlsConfiguration.cornerStyle = UIButtonConfigurationCornerStyleCapsule;
    editControlsConfiguration.imagePadding = 8.0;
    UIImageSymbolConfiguration* editSymbolConfiguration = [UIImageSymbolConfiguration configurationWithPointSize:16.0 weight:UIImageSymbolWeightSemibold];
    editControlsConfiguration.image = [UIImage systemImageNamed:@"slider.horizontal.3" withConfiguration:editSymbolConfiguration];
    _editControlsButton.configuration = editControlsConfiguration;
    _editControlsButton.hidden = YES;
    _editControlsButton.alpha = 0.95;
    _editControlsButton.accessibilityLabel = @"Customize Controls";
    _editControlsButton.accessibilityIdentifier = @"pause-edit-controls";
    [_editControlsButton addTarget:self action:@selector(editControlsTapped) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:_editControlsButton];'''
    text = replace_once(text, button_creation_anchor, button_creation_new, "create new weapon and edit buttons")

    # 7. Apply stored opacity and tap gesture in styleControlButton
    old_style = '''    button.exclusiveTouch = NO;
}'''
    new_style = '''    button.exclusiveTouch = NO;
    NSString* opacityKey = [@"SeriousIOS.TouchControlOpacity." stringByAppendingString:identifier];
    if ([NSUserDefaults.standardUserDefaults objectForKey:opacityKey] != nil) {
        button.alpha = (CGFloat)[NSUserDefaults.standardUserDefaults doubleForKey:opacityKey];
    }
    UITapGestureRecognizer* editTap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(controlButtonTapped:)];
    editTap.cancelsTouchesInView = NO;
    [button addGestureRecognizer:editTap];
}'''
    text = replace_once(text, old_style, new_style, "load control opacity and edit tap")

    # 8. Select button on pan or pinch gesture
    text = replace_once(
        text,
        "    UIButton* button = (UIButton*)gesture.view;\n    const CGPoint translation = [gesture translationInView:self];",
        "    UIButton* button = (UIButton*)gesture.view;\n    [self selectControlButtonForEditing:button];\n    const CGPoint translation = [gesture translationInView:self];",
        "select on pan gesture",
    )
    text = replace_once(
        text,
        "    UIButton* button = (UIButton*)gesture.view;\n    const CGFloat unit = MIN(CGRectGetWidth(self.bounds), CGRectGetHeight(self.bounds));",
        "    UIButton* button = (UIButton*)gesture.view;\n    [self selectControlButtonForEditing:button];\n    const CGFloat unit = MIN(CGRectGetWidth(self.bounds), CGRectGetHeight(self.bounds));",
        "select on pinch gesture",
    )

    # 9. Layout newly added controls in layoutGameplayControls
    layout_anchor = '''    _pauseButton.frame = [self storedControlFrameForButton:_pauseButton defaultFrame:pauseDefault];'''
    layout_new = '''    _pauseButton.frame = [self storedControlFrameForButton:_pauseButton defaultFrame:pauseDefault];

    const CGFloat weaponButtonSize = MAX(44.0, actionSize * 0.84);
    const CGRect nextWeaponDefault = CGRectMake(
        CGRectGetMinX(fireDefault) - gap - weaponButtonSize,
        CGRectGetMinY(useDefault) - gap - weaponButtonSize,
        weaponButtonSize,
        weaponButtonSize);
    const CGRect prevWeaponDefault = CGRectMake(
        CGRectGetMinX(nextWeaponDefault) - gap - weaponButtonSize,
        CGRectGetMinY(nextWeaponDefault),
        weaponButtonSize,
        weaponButtonSize);
    const CGRect scopeDefault = CGRectMake(
        CGRectGetMinX(jumpDefault) - gap - weaponButtonSize,
        CGRectGetMinY(jumpDefault),
        weaponButtonSize,
        weaponButtonSize);
    const CGRect crouchDefault = CGRectMake(
        CGRectGetMinX(scopeDefault) - gap - weaponButtonSize,
        CGRectGetMinY(scopeDefault),
        weaponButtonSize,
        weaponButtonSize);
    const CGFloat utilitySize = MAX(42.0, pauseSize * 0.86);
    const CGRect computerDefault = CGRectMake(
        width * 0.5 + 40.0,
        self.safeAreaInsets.top + margin,
        utilitySize,
        utilitySize);
    const CGRect quickSaveDefault = CGRectMake(
        width * 0.5 - utilitySize - 40.0,
        self.safeAreaInsets.top + margin,
        utilitySize,
        utilitySize);

    _nextWeaponButton.frame = [self storedControlFrameForButton:_nextWeaponButton defaultFrame:nextWeaponDefault];
    _prevWeaponButton.frame = [self storedControlFrameForButton:_prevWeaponButton defaultFrame:prevWeaponDefault];
    _scopeButton.frame = [self storedControlFrameForButton:_scopeButton defaultFrame:scopeDefault];
    _crouchButton.frame = [self storedControlFrameForButton:_crouchButton defaultFrame:crouchDefault];
    _computerButton.frame = [self storedControlFrameForButton:_computerButton defaultFrame:computerDefault];
    _quickSaveButton.frame = [self storedControlFrameForButton:_quickSaveButton defaultFrame:quickSaveDefault];'''
    text = replace_once(text, layout_anchor, layout_new, "layout new controls")

    # 10. Update visibility in updateGameplayControlVisibility
    vis_anchor = '''    _skipButton.hidden = YES;
    _skipButton.userInteractionEnabled = NO;
    _pauseButton.hidden = !active;'''
    vis_new = '''    _skipButton.hidden = YES;
    _skipButton.userInteractionEnabled = NO;
    _pauseButton.hidden = !active;

    const BOOL weaponsVisible = active && !computerActive;
    _nextWeaponButton.hidden = !weaponsVisible;
    _nextWeaponButton.userInteractionEnabled = weaponsVisible;
    _prevWeaponButton.hidden = !weaponsVisible;
    _prevWeaponButton.userInteractionEnabled = weaponsVisible;
    _scopeButton.hidden = !weaponsVisible;
    _scopeButton.userInteractionEnabled = weaponsVisible;
    _crouchButton.hidden = !weaponsVisible || !_crouchButtonEnabled;
    _crouchButton.userInteractionEnabled = weaponsVisible && _crouchButtonEnabled;
    _computerButton.hidden = !weaponsVisible || !_computerButtonEnabled;
    _computerButton.userInteractionEnabled = weaponsVisible && _computerButtonEnabled;
    _quickSaveButton.hidden = !weaponsVisible || !_quickSaveButtonEnabled;
    _quickSaveButton.userInteractionEnabled = weaponsVisible && _quickSaveButtonEnabled;'''
    text = replace_once(text, vis_anchor, vis_new, "update new controls visibility")

    # 11. Pause menu button visibility and layout
    pause_menu_anchor = '''    _returnToGameButton.hidden = !pauseMenuActive || _controlsEditorVisible;
    _returnToGameButton.userInteractionEnabled = pauseMenuActive && !_controlsEditorVisible;
    if (!_returnToGameButton.hidden) {
        [self bringSubviewToFront:_returnToGameButton];
    }'''
    pause_menu_new = '''    _returnToGameButton.hidden = !pauseMenuActive || _controlsEditorVisible;
    _returnToGameButton.userInteractionEnabled = pauseMenuActive && !_controlsEditorVisible;
    if (!_returnToGameButton.hidden) {
        [self bringSubviewToFront:_returnToGameButton];
    }
    _editControlsButton.hidden = !pauseMenuActive || _controlsEditorVisible;
    _editControlsButton.userInteractionEnabled = pauseMenuActive && !_controlsEditorVisible;
    if (!_editControlsButton.hidden) {
        [self bringSubviewToFront:_editControlsButton];
    }'''
    text = replace_once(text, pause_menu_anchor, pause_menu_new, "pause menu edit button visibility")

    return_layout_anchor = '''- (void)layoutReturnToGameButton {
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat width = 170.0;
    const CGFloat height = 50.0;
    const CGFloat x = MAX(
        safe.left + 12.0,
        CGRectGetWidth(self.bounds) - safe.right - width - 14.0);
    const CGFloat y = safe.top + 12.0;
    _returnToGameButton.frame = CGRectMake(x, y, width, height);
}'''
    return_layout_new = '''- (void)layoutReturnToGameButton {
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat width = 170.0;
    const CGFloat height = 50.0;
    const CGFloat editWidth = 180.0;
    const CGFloat gap = 12.0;
    const CGFloat returnX = MAX(
        safe.left + 12.0,
        CGRectGetWidth(self.bounds) - safe.right - width - 14.0);
    const CGFloat y = safe.top + 12.0;
    _returnToGameButton.frame = CGRectMake(returnX, y, width, height);
    if (_editControlsButton != nil) {
        const CGFloat editX = MAX(safe.left + 12.0, returnX - gap - editWidth);
        _editControlsButton.frame = CGRectMake(editX, y, editWidth, height);
    }
}'''
    text = replace_once(text, return_layout_anchor, return_layout_new, "pause menu dual buttons layout")

    # 12. In Controls Editor, add controls: selected control size/opacity, optional button switches, and export diagnostics
    editor_panel_anchor = '''    [_controlsEditorPanel addSubview:_aimAssistStrengthSlider];'''
    editor_panel_new = '''    [_controlsEditorPanel addSubview:_aimAssistStrengthSlider];

    _selectedControlNameLabel = [self controlsEditorLabelWithText:@"Tap a button to resize"
                                                             font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightBold]];
    _selectedControlNameLabel.textColor = [UIColor colorWithRed:0.35 green:0.75 blue:1.0 alpha:1.0];
    _selectedControlNameLabel.accessibilityIdentifier = @"selected-control-name-label";
    [_controlsEditorPanel addSubview:_selectedControlNameLabel];

    UILabel* sizeLabel = [self controlsEditorLabelWithText:@"Selected Button Size"
                                                      font:[UIFont systemFontOfSize:12.0 weight:UIFontWeightMedium]];
    sizeLabel.accessibilityIdentifier = @"control-size-label";
    [_controlsEditorPanel addSubview:sizeLabel];

    _controlSizeValueLabel = [self controlsEditorLabelWithText:@""
                                                          font:[UIFont monospacedDigitSystemFontOfSize:12.0 weight:UIFontWeightMedium]];
    _controlSizeValueLabel.textAlignment = NSTextAlignmentRight;
    [_controlsEditorPanel addSubview:_controlSizeValueLabel];

    _controlSizeSlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _controlSizeSlider.minimumValue = 40.0f;
    _controlSizeSlider.maximumValue = 110.0f;
    _controlSizeSlider.value = 58.0f;
    [_controlSizeSlider addTarget:self action:@selector(controlSizeSliderChanged:)
                 forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_controlSizeSlider];

    UILabel* opacityLabel = [self controlsEditorLabelWithText:@"Selected Button Opacity"
                                                         font:[UIFont systemFontOfSize:12.0 weight:UIFontWeightMedium]];
    opacityLabel.accessibilityIdentifier = @"control-opacity-label";
    [_controlsEditorPanel addSubview:opacityLabel];

    _controlOpacityValueLabel = [self controlsEditorLabelWithText:@""
                                                             font:[UIFont monospacedDigitSystemFontOfSize:12.0 weight:UIFontWeightMedium]];
    _controlOpacityValueLabel.textAlignment = NSTextAlignmentRight;
    [_controlsEditorPanel addSubview:_controlOpacityValueLabel];

    _controlOpacitySlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _controlOpacitySlider.minimumValue = 0.20f;
    _controlOpacitySlider.maximumValue = 1.00f;
    _controlOpacitySlider.value = 0.85f;
    [_controlOpacitySlider addTarget:self action:@selector(controlOpacitySliderChanged:)
                    forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_controlOpacitySlider];

    UILabel* crouchLabel = [self controlsEditorLabelWithText:@"Show Crouch button"
                                                        font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    crouchLabel.accessibilityIdentifier = @"crouch-label";
    [_controlsEditorPanel addSubview:crouchLabel];

    _crouchSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _crouchSwitch.accessibilityIdentifier = @"crouch-switch";
    _crouchSwitch.on = _crouchButtonEnabled;
    [_crouchSwitch addTarget:self action:@selector(crouchSwitchChanged:)
            forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_crouchSwitch];

    UILabel* computerLabel = [self controlsEditorLabelWithText:@"Show NETRICSA button"
                                                          font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    computerLabel.accessibilityIdentifier = @"computer-label";
    [_controlsEditorPanel addSubview:computerLabel];

    _computerSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _computerSwitch.accessibilityIdentifier = @"computer-switch";
    _computerSwitch.on = _computerButtonEnabled;
    [_computerSwitch addTarget:self action:@selector(computerSwitchChanged:)
              forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_computerSwitch];

    UILabel* quickSaveLabel = [self controlsEditorLabelWithText:@"Show Quick Save button"
                                                           font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    quickSaveLabel.accessibilityIdentifier = @"quicksave-label";
    [_controlsEditorPanel addSubview:quickSaveLabel];

    _quickSaveSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _quickSaveSwitch.accessibilityIdentifier = @"quicksave-switch";
    _quickSaveSwitch.on = _quickSaveButtonEnabled;
    [_quickSaveSwitch addTarget:self action:@selector(quickSaveSwitchChanged:)
               forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_quickSaveSwitch];

    _exportDiagnosticsButton = [self controlsEditorButtonWithTitle:@"Export Diagnostics"
                                                            action:@selector(exportDiagnosticsTapped)];
    _exportDiagnosticsButton.accessibilityIdentifier = @"export-diagnostics-button";
    [_controlsEditorPanel addSubview:_exportDiagnosticsButton];'''
    text = replace_once(text, editor_panel_anchor, editor_panel_new, "controls editor sliders and export button")

    # 13. Position size/opacity sliders, optional switches, and export button in layoutControlsEditor
    editor_layout_anchor = '''    const CGFloat buttonY = panelHeight - 46.0;
    reset.frame = CGRectMake(left, buttonY, 128.0, 36.0);
    done.frame = CGRectMake(panelWidth - right - 90.0, buttonY, 90.0, 36.0);'''
    editor_layout_new = '''    UIView* selNameView = [self descendantViewWithAccessibilityIdentifier:@"selected-control-name-label" inView:_controlsEditorPanel];
    UIView* sizeLabelView = [self descendantViewWithAccessibilityIdentifier:@"control-size-label" inView:_controlsEditorPanel];
    UIView* opacityLabelView = [self descendantViewWithAccessibilityIdentifier:@"control-opacity-label" inView:_controlsEditorPanel];
    UIView* crouchLabelView = [self descendantViewWithAccessibilityIdentifier:@"crouch-label" inView:_controlsEditorPanel];
    UIView* compLabelView = [self descendantViewWithAccessibilityIdentifier:@"computer-label" inView:_controlsEditorPanel];
    UIView* qsLabelView = [self descendantViewWithAccessibilityIdentifier:@"quicksave-label" inView:_controlsEditorPanel];
    UIButton* exportBtn = (UIButton*)[self descendantViewWithAccessibilityIdentifier:@"export-diagnostics-button" inView:_controlsEditorPanel];

    selNameView.frame = CGRectMake(left, 332.0, contentWidth, 18.0);
    sizeLabelView.frame = CGRectMake(left, 354.0, contentWidth - 62.0, 18.0);
    _controlSizeValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 354.0, 62.0, 18.0);
    _controlSizeSlider.frame = CGRectMake(left, 374.0, contentWidth, 24.0);

    opacityLabelView.frame = CGRectMake(left, 402.0, contentWidth - 62.0, 18.0);
    _controlOpacityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 402.0, 62.0, 18.0);
    _controlOpacitySlider.frame = CGRectMake(left, 422.0, contentWidth, 24.0);

    crouchLabelView.frame = CGRectMake(left, 452.0, contentWidth - 60.0, 26.0);
    _crouchSwitch.frame = CGRectMake(panelWidth - right - 51.0, 450.0, 51.0, 31.0);

    compLabelView.frame = CGRectMake(left, 486.0, contentWidth - 60.0, 26.0);
    _computerSwitch.frame = CGRectMake(panelWidth - right - 51.0, 484.0, 51.0, 31.0);

    qsLabelView.frame = CGRectMake(left, 520.0, contentWidth - 60.0, 26.0);
    _quickSaveSwitch.frame = CGRectMake(panelWidth - right - 51.0, 518.0, 51.0, 31.0);

    const CGFloat buttonY = 560.0;
    reset.frame = CGRectMake(left, buttonY, 80.0, 34.0);
    exportBtn.frame = CGRectMake(left + 88.0, buttonY, 136.0, 34.0);
    done.frame = CGRectMake(panelWidth - right - 68.0, buttonY, 68.0, 34.0);
    _controlsEditorPanel.contentSize = CGSizeMake(panelWidth, buttonY + 44.0);'''
    text = replace_once(text, editor_layout_anchor, editor_layout_new, "layout editor sliders and export button")

    # 14. Sync selection and switches in showControlsEditor
    show_anchor = '''    for (UIGestureRecognizer* gesture in _controlEditingGestures) {
        gesture.enabled = YES;
    }'''
    show_new = '''    for (UIGestureRecognizer* gesture in _controlEditingGestures) {
        gesture.enabled = YES;
    }
    _crouchSwitch.on = _crouchButtonEnabled;
    _computerSwitch.on = _computerButtonEnabled;
    _quickSaveSwitch.on = _quickSaveButtonEnabled;
    if (_selectedControlButton == nil) {
        [self selectControlButtonForEditing:_fireButton];
    } else {
        [self selectControlButtonForEditing:_selectedControlButton];
    }'''
    text = replace_once(text, show_anchor, show_new, "sync editor controls on show")

    # 15. Clear selection highlight in hideControlsEditor
    hide_anchor = '''    for (UIButton* button in [self gameplayControlButtons]) {
        [self persistControlFrameForButton:button];
    }'''
    hide_new = '''    for (UIButton* button in [self gameplayControlButtons]) {
        [self persistControlFrameForButton:button];
        button.layer.borderWidth = 0.0;
    }
    _selectedControlButton = nil;'''
    text = replace_once(text, hide_anchor, hide_new, "clear selection highlight on hide")

    return text


def self_test() -> None:
    fixture = '''    UIButton* _returnToGameButton;
    UIView* _controlsEditorPanel;
    _controlsEditorPanel = [[UIView alloc] initWithFrame:CGRectZero];
- (void)touchSensitivityChanged:(UISlider*)sender {
}
    return @[_fireButton, _jumpButton, _useButton, _pauseButton];
    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
    [_pauseButton addTarget:self action:@selector(gameplayPause)
          forControlEvents:UIControlEventTouchUpInside];
    button.exclusiveTouch = NO;
}
    UIButton* button = (UIButton*)gesture.view;
    const CGPoint translation = [gesture translationInView:self];
    UIButton* button = (UIButton*)gesture.view;
    const CGFloat unit = MIN(CGRectGetWidth(self.bounds), CGRectGetHeight(self.bounds));
    _pauseButton.frame = [self storedControlFrameForButton:_pauseButton defaultFrame:pauseDefault];
    _skipButton.hidden = YES;
    _skipButton.userInteractionEnabled = NO;
    _pauseButton.hidden = !active;
    _returnToGameButton.hidden = !pauseMenuActive || _controlsEditorVisible;
    _returnToGameButton.userInteractionEnabled = pauseMenuActive && !_controlsEditorVisible;
    if (!_returnToGameButton.hidden) {
        [self bringSubviewToFront:_returnToGameButton];
    }
- (void)layoutReturnToGameButton {
    const UIEdgeInsets safe = self.safeAreaInsets;
    const CGFloat width = 170.0;
    const CGFloat height = 50.0;
    const CGFloat x = MAX(
        safe.left + 12.0,
        CGRectGetWidth(self.bounds) - safe.right - width - 14.0);
    const CGFloat y = safe.top + 12.0;
    _returnToGameButton.frame = CGRectMake(x, y, width, height);
}
    [_controlsEditorPanel addSubview:_aimAssistStrengthSlider];
    const CGFloat buttonY = panelHeight - 46.0;
    reset.frame = CGRectMake(left, buttonY, 128.0, 36.0);
    done.frame = CGRectMake(panelWidth - right - 90.0, buttonY, 90.0, 36.0);
    for (UIGestureRecognizer* gesture in _controlEditingGestures) {
        gesture.enabled = YES;
    }
    for (UIButton* button in [self gameplayControlButtons]) {
        [self persistControlFrameForButton:button];
    }
'''
    transformed = transform_text(fixture)
    assert "_nextWeaponButton" in transformed
    assert "_scopeButton" in transformed
    assert "_editControlsButton" in transformed
    assert "UIScrollView* _controlsEditorPanel;" in transformed
    assert "selectControlButtonForEditing:" in transformed
    assert "controlSizeSliderChanged:" in transformed
    assert "controlOpacitySliderChanged:" in transformed
    assert "export-diagnostics-button" in transformed
    assert "crouch-switch" in transformed
    assert "computer-switch" in transformed
    assert "quicksave-switch" in transformed
    print("SeriousiOS weapon controls transform self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path, nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        if args.host_source is None:
            return 0
    if args.host_source is None:
        parser.error("host_source is required unless only --self-test is used")

    path = args.host_source.resolve()
    if not path.is_file():
        raise SystemExit(f"host source does not exist: {path}")
    transformed = transform_text(path.read_text(encoding="utf-8"))
    path.write_text(transformed, encoding="utf-8")
    print(f"Injected weapon controls, layout sliders, and edit button in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
