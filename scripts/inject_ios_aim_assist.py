#!/usr/bin/env python3
"""Inject mobile aim assist settings UI and configuration into SeriousIOS host."""

from __future__ import annotations

import argparse
from pathlib import Path


AIM_ASSIST_IVARS = r'''    BOOL _aimAssistEnabled;
    CGFloat _aimAssistStrength;
    UISwitch* _aimAssistSwitch;
    UISlider* _aimAssistStrengthSlider;
    UILabel* _aimAssistStrengthValueLabel;
'''

AIM_ASSIST_METHODS = r'''- (void)aimAssistEnabledChanged:(UISwitch*)sender {
    _aimAssistEnabled = sender.isOn;
    [NSUserDefaults.standardUserDefaults setBool:_aimAssistEnabled
                                          forKey:@"SeriousIOS.AimAssistEnabled"];
    SeriousIOSAimAssistConfig aimConfig;
    SeriousIOS_GetAimAssistConfig(&aimConfig);
    aimConfig.enabled = _aimAssistEnabled;
    SeriousIOS_SetAimAssistConfig(&aimConfig);
    SeriousIOS_DiagnosticsLog("input", "aim_assist_setting enabled=%d", _aimAssistEnabled ? 1 : 0);
}

- (void)aimAssistStrengthChanged:(UISlider*)sender {
    _aimAssistStrength = sender.value;
    [NSUserDefaults.standardUserDefaults setDouble:_aimAssistStrength
                                            forKey:@"SeriousIOS.AimAssistStrength"];
    SeriousIOSAimAssistConfig aimConfig;
    SeriousIOS_GetAimAssistConfig(&aimConfig);
    aimConfig.strength = (float)_aimAssistStrength;
    SeriousIOS_SetAimAssistConfig(&aimConfig);
    [self updateSensitivityValueLabels];
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def transform_text(text: str) -> str:
    # 1. Inject instance variables
    text = replace_once(
        text,
        "    UILabel* _touchSensitivityValueLabel;\n",
        "    UILabel* _touchSensitivityValueLabel;\n" + AIM_ASSIST_IVARS,
        "aim assist ivars",
    )

    # 2. Inject value label updates
    text = replace_once(
        text,
        '    _touchSensitivityValueLabel.text = [NSString stringWithFormat:@"%.2fx", _touchAimSensitivity];\n',
        '    _touchSensitivityValueLabel.text = [NSString stringWithFormat:@"%.2fx", _touchAimSensitivity];\n'
        '    _aimAssistStrengthValueLabel.text = [NSString stringWithFormat:@"%.2fx", _aimAssistStrength];\n',
        "aim assist label update",
    )

    # 3. Inject event methods
    text = replace_once(
        text,
        "- (void)touchSensitivityChanged:(UISlider*)sender {\n",
        AIM_ASSIST_METHODS + "\n- (void)touchSensitivityChanged:(UISlider*)sender {\n",
        "aim assist methods",
    )

    # 4. Inject configuration setup
    text = replace_once(
        text,
        '''    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;''',
        '''    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;
    _aimAssistEnabled = [defaults objectForKey:@"SeriousIOS.AimAssistEnabled"] != nil
        ? [defaults boolForKey:@"SeriousIOS.AimAssistEnabled"]
        : YES;
    _aimAssistStrength = [defaults objectForKey:@"SeriousIOS.AimAssistStrength"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.AimAssistStrength"]
        : 0.60;
    SeriousIOSAimAssistConfig aimConfig;
    SeriousIOS_GetAimAssistConfig(&aimConfig);
    aimConfig.enabled = _aimAssistEnabled;
    aimConfig.strength = (float)_aimAssistStrength;
    SeriousIOS_SetAimAssistConfig(&aimConfig);''',
        "aim assist configuration",
    )

    # 5. Inject UI elements creation
    ui_creation_anchor = '''    [_touchSensitivitySlider addTarget:self action:@selector(touchSensitivityChanged:)
                        forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_touchSensitivitySlider];'''

    ui_creation_new = '''    [_touchSensitivitySlider addTarget:self action:@selector(touchSensitivityChanged:)
                        forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_touchSensitivitySlider];

    UILabel* aimAssistLabel = [self controlsEditorLabelWithText:@"Aim assist"
                                                           font:[UIFont systemFontOfSize:14.0 weight:UIFontWeightSemibold]];
    aimAssistLabel.accessibilityIdentifier = @"aim-assist-label";
    _aimAssistSwitch = [[UISwitch alloc] initWithFrame:CGRectZero];
    _aimAssistSwitch.accessibilityIdentifier = @"aim-assist-switch";
    _aimAssistSwitch.on = _aimAssistEnabled;
    [_aimAssistSwitch addTarget:self action:@selector(aimAssistEnabledChanged:)
              forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_aimAssistSwitch];

    UILabel* aimAssistStrengthLabel = [self controlsEditorLabelWithText:@"Aim assist strength"
                                                                   font:[UIFont systemFontOfSize:13.0 weight:UIFontWeightMedium]];
    aimAssistStrengthLabel.accessibilityIdentifier = @"aim-assist-strength-label";
    _aimAssistStrengthValueLabel = [self controlsEditorLabelWithText:@""
                                                                font:[UIFont monospacedDigitSystemFontOfSize:12.0 weight:UIFontWeightMedium]];
    _aimAssistStrengthValueLabel.textAlignment = NSTextAlignmentRight;
    _aimAssistStrengthSlider = [[UISlider alloc] initWithFrame:CGRectZero];
    _aimAssistStrengthSlider.accessibilityIdentifier = @"aim-assist-strength-slider";
    _aimAssistStrengthSlider.minimumValue = 0.10f;
    _aimAssistStrengthSlider.maximumValue = 1.50f;
    _aimAssistStrengthSlider.value = _aimAssistStrength;
    [_aimAssistStrengthSlider addTarget:self action:@selector(aimAssistStrengthChanged:)
                       forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_aimAssistStrengthSlider];'''

    text = replace_once(text, ui_creation_anchor, ui_creation_new, "aim assist ui creation")

    # 6. Adjust panel height
    text = replace_once(
        text,
        "    const CGFloat panelHeight = MIN(320.0, MAX(300.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));",
        "    const CGFloat panelHeight = MIN(390.0, MAX(350.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));",
        "aim assist panel height",
    )

    # 7. Inject layout for new controls
    ui_layout_anchor = '''    UIView* touchSensitivityLabelView = [self descendantViewWithAccessibilityIdentifier:@"touch-sensitivity-label"
                                                                                  inView:_controlsEditorPanel];'''
    ui_layout_new = '''    UIView* touchSensitivityLabelView = [self descendantViewWithAccessibilityIdentifier:@"touch-sensitivity-label"
                                                                                  inView:_controlsEditorPanel];
    UIView* aimAssistLabelView = [self descendantViewWithAccessibilityIdentifier:@"aim-assist-label"
                                                                          inView:_controlsEditorPanel];
    UIView* aimAssistStrengthLabelView = [self descendantViewWithAccessibilityIdentifier:@"aim-assist-strength-label"
                                                                                  inView:_controlsEditorPanel];'''
    text = replace_once(text, ui_layout_anchor, ui_layout_new, "aim assist layout lookups")

    frames_anchor = '''    touchSensitivityLabelView.frame = CGRectMake(left, 190.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 190.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 208.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 46.0;'''

    frames_new = '''    touchSensitivityLabelView.frame = CGRectMake(left, 190.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 190.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 208.0, contentWidth, 30.0);
    aimAssistLabelView.frame = CGRectMake(left, 240.0, contentWidth - 70.0, 30.0);
    _aimAssistSwitch.frame = CGRectMake(panelWidth - right - 51.0, 238.0, 51.0, 31.0);
    aimAssistStrengthLabelView.frame = CGRectMake(left, 272.0, contentWidth - 62.0, 20.0);
    _aimAssistStrengthValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 272.0, 62.0, 20.0);
    _aimAssistStrengthSlider.frame = CGRectMake(left, 292.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 46.0;'''

    text = replace_once(text, frames_anchor, frames_new, "aim assist frames")

    return text


def self_test() -> None:
    fixture = '''    UILabel* _touchSensitivityValueLabel;
    _touchSensitivityValueLabel.text = [NSString stringWithFormat:@"%.2fx", _touchAimSensitivity];
- (void)touchSensitivityChanged:(UISlider*)sender {
}
    _touchAimSensitivity = [defaults objectForKey:@"SeriousIOS.TouchAimSensitivity"] != nil
        ? [defaults doubleForKey:@"SeriousIOS.TouchAimSensitivity"]
        : 0.72;
    [_touchSensitivitySlider addTarget:self action:@selector(touchSensitivityChanged:)
                        forControlEvents:UIControlEventValueChanged];
    [_controlsEditorPanel addSubview:_touchSensitivitySlider];
    const CGFloat panelHeight = MIN(320.0, MAX(300.0, height - self.safeAreaInsets.top - self.safeAreaInsets.bottom - 20.0));
    UIView* touchSensitivityLabelView = [self descendantViewWithAccessibilityIdentifier:@"touch-sensitivity-label"
                                                                                  inView:_controlsEditorPanel];
    touchSensitivityLabelView.frame = CGRectMake(left, 190.0, contentWidth - 62.0, 20.0);
    _touchSensitivityValueLabel.frame = CGRectMake(panelWidth - right - 62.0, 190.0, 62.0, 20.0);
    _touchSensitivitySlider.frame = CGRectMake(left, 208.0, contentWidth, 30.0);
    const CGFloat buttonY = panelHeight - 46.0;
'''
    transformed = transform_text(fixture)
    assert "_aimAssistEnabled;" in transformed
    assert "_aimAssistSwitch" in transformed
    assert "aimAssistEnabledChanged:" in transformed
    assert "SeriousIOS.AimAssistEnabled" in transformed
    assert "SeriousIOS_SetAimAssistConfig" in transformed
    print("SeriousiOS aim assist transform self-test passed")


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
    print(f"Injected mobile aim assist UI and controls in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
