#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct SeriousIOSAimAssistConfig {
    bool enabled;
    float strength;           // Magnetism pull strength (0.0 to 1.5, default 0.60)
    float friction;           // Slowdown friction factor (0.0 to 1.0, default 0.50)
    float maxAngleDegrees;    // Maximum target detection angle cone (default 8.5)
    float maxDistance;        // Maximum target detection distance in meters (default 35.0)
    float breakoutSpeed;      // Flick gesture speed threshold to disengage (default 45.0)
} SeriousIOSAimAssistConfig;

typedef struct SeriousIOSAimAssistTarget {
    bool hasTarget;
    float deltaYawDegrees;    // Angle delta to target center on horizontal axis (degrees)
    float deltaPitchDegrees;  // Angle delta to target center on vertical axis (degrees)
    float proximity;          // Proximity to crosshair center (0.0 = edge, 1.0 = exact center)
    float distance;           // Distance to target in world units / meters
} SeriousIOSAimAssistTarget;

// Configuration lifecycle
void SeriousIOS_SetAimAssistConfig(const SeriousIOSAimAssistConfig* config);
void SeriousIOS_GetAimAssistConfig(SeriousIOSAimAssistConfig* outConfig);
void SeriousIOS_ResetAimAssistConfig(void);

// Target query
bool SeriousIOS_GetAimAssistTarget(SeriousIOSAimAssistTarget* outTarget);

// Test injection hooks for standalone unit verification
void SeriousIOS_SetMockAimAssistTarget(const SeriousIOSAimAssistTarget* mockTarget);
void SeriousIOS_ClearMockAimAssistTarget(void);

// Filter relative mouse delta through aim assist friction and pull
void SeriousIOS_ApplyAimAssistFilter(int* deltaX, int* deltaY);

#ifdef __cplusplus
} // extern "C"
#endif
