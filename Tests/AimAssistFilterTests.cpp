#include "SeriousIOSAimAssist.h"

#include <cassert>
#include <cmath>
#include <iostream>

namespace {

void testDefaultConfig() {
    SeriousIOS_ResetAimAssistConfig();
    SeriousIOSAimAssistConfig config = {};
    SeriousIOS_GetAimAssistConfig(&config);

    assert(config.enabled == true);
    assert(std::fabs(config.strength - 0.60f) < 0.001f);
    assert(std::fabs(config.friction - 0.50f) < 0.001f);
    assert(std::fabs(config.maxAngleDegrees - 8.5f) < 0.001f);
    assert(std::fabs(config.maxDistance - 35.0f) < 0.001f);
    assert(std::fabs(config.breakoutSpeed - 45.0f) < 0.001f);
    std::cout << "[PASS] testDefaultConfig\n";
}

void testDisabledPassThrough() {
    SeriousIOS_ResetAimAssistConfig();
    SeriousIOSAimAssistConfig config = {};
    SeriousIOS_GetAimAssistConfig(&config);
    config.enabled = false;
    SeriousIOS_SetAimAssistConfig(&config);

    // Provide a mock target
    SeriousIOSAimAssistTarget mock = {};
    mock.hasTarget = true;
    mock.proximity = 1.0f;
    mock.deltaYawDegrees = 5.0f;
    mock.deltaPitchDegrees = -2.0f;
    SeriousIOS_SetMockAimAssistTarget(&mock);

    int deltaX = 10;
    int deltaY = -5;
    SeriousIOS_ApplyAimAssistFilter(&deltaX, &deltaY);

    assert(deltaX == 10);
    assert(deltaY == -5);
    SeriousIOS_ClearMockAimAssistTarget();
    std::cout << "[PASS] testDisabledPassThrough\n";
}

void testFrictionSlowdown() {
    SeriousIOS_ResetAimAssistConfig();
    SeriousIOSAimAssistConfig config = {};
    SeriousIOS_GetAimAssistConfig(&config);
    config.enabled = true;
    config.friction = 0.50f;
    config.strength = 0.0f; // Disable pull to isolate friction
    SeriousIOS_SetAimAssistConfig(&config);

    // Target directly centered: zero angle delta, max proximity
    SeriousIOSAimAssistTarget mock = {};
    mock.hasTarget = true;
    mock.proximity = 1.0f;
    mock.deltaYawDegrees = 0.0f;
    mock.deltaPitchDegrees = 0.0f;
    mock.distance = 15.0f;
    SeriousIOS_SetMockAimAssistTarget(&mock);

    int deltaX = 20;
    int deltaY = 12;
    SeriousIOS_ApplyAimAssistFilter(&deltaX, &deltaY);

    // frictionScale = 1.0 - (0.50 * 0.50 * 1.0) = 0.75
    // 20 * 0.75 = 15
    // 12 * 0.75 = 9
    assert(deltaX == 15);
    assert(deltaY == 9);
    SeriousIOS_ClearMockAimAssistTarget();
    std::cout << "[PASS] testFrictionSlowdown\n";
}

void testMagnetismPull() {
    SeriousIOS_ResetAimAssistConfig();
    SeriousIOSAimAssistConfig config = {};
    SeriousIOS_GetAimAssistConfig(&config);
    config.enabled = true;
    config.friction = 0.0f; // Disable friction to isolate pull
    config.strength = 0.80f;
    SeriousIOS_SetAimAssistConfig(&config);

    // Target to the right (+Yaw)
    SeriousIOSAimAssistTarget mock = {};
    mock.hasTarget = true;
    mock.proximity = 0.80f;
    mock.deltaYawDegrees = 1.5f;
    mock.deltaPitchDegrees = 0.0f;
    mock.distance = 10.0f;
    SeriousIOS_SetMockAimAssistTarget(&mock);

    // User nudges rightwards (+X)
    int deltaX = 4;
    int deltaY = 0;
    SeriousIOS_ApplyAimAssistFilter(&deltaX, &deltaY);

    // Pull should increase deltaX towards the target
    assert(deltaX > 4);
    assert(deltaY == 0);
    SeriousIOS_ClearMockAimAssistTarget();
    std::cout << "[PASS] testMagnetismPull\n";
}

void testBreakoutHighSpeedFlick() {
    SeriousIOS_ResetAimAssistConfig();
    SeriousIOSAimAssistConfig config = {};
    SeriousIOS_GetAimAssistConfig(&config);
    config.enabled = true;
    config.breakoutSpeed = 45.0f;
    SeriousIOS_SetAimAssistConfig(&config);

    // Strong target attraction configured
    SeriousIOSAimAssistTarget mock = {};
    mock.hasTarget = true;
    mock.proximity = 1.0f;
    mock.deltaYawDegrees = -4.0f;
    mock.deltaPitchDegrees = 3.0f;
    SeriousIOS_SetMockAimAssistTarget(&mock);

    // High speed swipe (hypot > 45)
    int deltaX = 50;
    int deltaY = 20;
    SeriousIOS_ApplyAimAssistFilter(&deltaX, &deltaY);

    // Must break out cleanly with exact raw input preserved
    assert(deltaX == 50);
    assert(deltaY == 20);
    SeriousIOS_ClearMockAimAssistTarget();
    std::cout << "[PASS] testBreakoutHighSpeedFlick\n";
}

} // namespace

int main() {
    testDefaultConfig();
    testDisabledPassThrough();
    testFrictionSlowdown();
    testMagnetismPull();
    testBreakoutHighSpeedFlick();
    std::cout << "All SeriousiOS aim assist filter tests passed successfully.\n";
    return 0;
}
