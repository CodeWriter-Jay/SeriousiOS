#include "SeriousIOSAimAssist.h"
#include "SeriousIOSApplicationLifecycle.h"
#include "SeriousIOSPlatformBridge.h"

#include <algorithm>
#include <cmath>
#include <mutex>

#if __has_include(<Engine/Engine.h>)
#include <Engine/Engine.h>
#include <Engine/Entities/Entity.h>
#include <Engine/Network/Network.h>
#include <Engine/Network/PlayerTarget.h>
#include <Engine/Network/SessionState.h>
#include <Engine/World/World.h>
#define SERIOUSIOS_HAS_ENGINE 1
#else
#define SERIOUSIOS_HAS_ENGINE 0
#endif

namespace {

constexpr float kDefaultStrength = 0.60f;
constexpr float kDefaultFriction = 0.50f;
constexpr float kDefaultMaxAngleDegrees = 8.5f;
constexpr float kDefaultMaxDistance = 35.0f;
constexpr float kDefaultBreakoutSpeed = 45.0f;
constexpr float kDegreesToMousePixels = 9.5f;

std::mutex gAimAssistMutex;
SeriousIOSAimAssistConfig gConfig = {
    true,                   // enabled
    kDefaultStrength,       // strength
    kDefaultFriction,       // friction
    kDefaultMaxAngleDegrees,// maxAngleDegrees
    kDefaultMaxDistance,    // maxDistance
    kDefaultBreakoutSpeed   // breakoutSpeed
};

bool gHasMockTarget = false;
SeriousIOSAimAssistTarget gMockTarget = {};

#if SERIOUSIOS_HAS_ENGINE
bool queryEngineTarget(
    const SeriousIOSAimAssistConfig& config,
    SeriousIOSAimAssistTarget* outTarget) {
    if (!SeriousIOS_ApplicationGameplayControlsActive() || _pNetwork == nullptr) {
        return false;
    }

    if (_pNetwork->ga_sesSessionState.ses_apltPlayers.Count() == 0) {
        return false;
    }

    CPlayerTarget& playerTarget = _pNetwork->ga_sesSessionState.ses_apltPlayers[0];
    if (!playerTarget.plt_bActive || playerTarget.plt_penPlayerEntity == nullptr) {
        return false;
    }

    CEntity* playerEntity = reinterpret_cast<CEntity*>(playerTarget.plt_penPlayerEntity);
    CWorld* world = playerEntity->en_pwoWorld;
    if (world == nullptr) {
        return false;
    }

    const CPlacement3D& playerPlacement = playerEntity->GetPlacement();
    FLOAT3D eyePos = playerPlacement.pl_PositionVector;
    eyePos(2) += 1.75f; // Standard standing eye height in Serious Engine

    const ANGLE heading = playerPlacement.pl_OrientationAngle(1);
    const ANGLE pitch = playerPlacement.pl_OrientationAngle(2);

    const float headingRad = heading * (3.1415926535f / 180.0f);
    const float pitchRad = pitch * (3.1415926535f / 180.0f);

    const FLOAT3D viewDir(
        -std::sin(headingRad) * std::cos(pitchRad),
        std::sin(pitchRad),
        -std::cos(headingRad) * std::cos(pitchRad));

    float bestScore = -1.0f;
    SeriousIOSAimAssistTarget bestTarget = {};

    // Scan entities in the active world
    const INDEX entityCount = world->wo_cenEntities.Count();
    for (INDEX i = 0; i < entityCount; ++i) {
        CEntity* target = &world->wo_cenEntities[i];
        if (target == nullptr || target == playerEntity) {
            continue;
        }

        // Target must be alive
        if ((target->en_ulFlags & ENF_ALIVE) == 0) {
            continue;
        }

        const FLOAT3D targetPos = target->GetPlacement().pl_PositionVector;
        const FLOAT3D toTarget = targetPos - eyePos;
        const float dist = toTarget.Length();
        if (dist <= 0.5f || dist > config.maxDistance) {
            continue;
        }

        const FLOAT3D dirToTarget = toTarget / dist;
        const float cosAngle = viewDir % dirToTarget; // Dot product in Serious Engine
        if (cosAngle < 0.0f) {
            continue;
        }

        const float clampedCos = std::max(-1.0f, std::min(1.0f, cosAngle));
        const float angleDegrees = std::acos(clampedCos) * (180.0f / 3.1415926535f);
        if (angleDegrees > config.maxAngleDegrees) {
            continue;
        }

        // Line-of-sight ray check to avoid snapping behind walls
        CCastRay ray(playerEntity, eyePos, targetPos);
        world->CastRay(ray);
        if (ray.cr_penHit != nullptr && ray.cr_penHit != target) {
            continue;
        }

        const float proximity = 1.0f - (angleDegrees / config.maxAngleDegrees);
        const float distanceWeight = 1.0f - (dist / config.maxDistance);
        const float score = proximity * 0.70f + distanceWeight * 0.30f;

        if (score > bestScore) {
            bestScore = score;
            bestTarget.hasTarget = true;
            bestTarget.distance = dist;
            bestTarget.proximity = proximity;

            // Compute relative angle delta to target
            const float targetHeading = std::atan2(-dirToTarget(1), -dirToTarget(3)) * (180.0f / 3.1415926535f);
            const float targetPitch = std::asin(std::max(-1.0f, std::min(1.0f, dirToTarget(2)))) * (180.0f / 3.1415926535f);

            float deltaYaw = targetHeading - heading;
            while (deltaYaw > 180.0f) deltaYaw -= 360.0f;
            while (deltaYaw < -180.0f) deltaYaw += 360.0f;

            bestTarget.deltaYawDegrees = deltaYaw;
            bestTarget.deltaPitchDegrees = targetPitch - pitch;
        }
    }

    if (bestTarget.hasTarget && outTarget != nullptr) {
        *outTarget = bestTarget;
        return true;
    }
    return false;
}
#endif

} // namespace

extern "C" void SeriousIOS_SetAimAssistConfig(const SeriousIOSAimAssistConfig* config) {
    if (config == nullptr) {
        return;
    }
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    gConfig = *config;
}

extern "C" void SeriousIOS_ResetAimAssistConfig(void) {
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    gConfig = {
        true,
        kDefaultStrength,
        kDefaultFriction,
        kDefaultMaxAngleDegrees,
        kDefaultMaxDistance,
        kDefaultBreakoutSpeed
    };
}

extern "C" void SeriousIOS_GetAimAssistConfig(SeriousIOSAimAssistConfig* outConfig) {
    if (outConfig == nullptr) {
        return;
    }
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    *outConfig = gConfig;
}

extern "C" bool SeriousIOS_GetAimAssistTarget(SeriousIOSAimAssistTarget* outTarget) {
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    if (!gConfig.enabled) {
        return false;
    }

    if (gHasMockTarget) {
        if (outTarget != nullptr) {
            *outTarget = gMockTarget;
        }
        return gMockTarget.hasTarget;
    }

#if SERIOUSIOS_HAS_ENGINE
    return queryEngineTarget(gConfig, outTarget);
#else
    return false;
#endif
}

extern "C" void SeriousIOS_SetMockAimAssistTarget(const SeriousIOSAimAssistTarget* target) {
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    if (target != nullptr) {
        gHasMockTarget = true;
        gMockTarget = *target;
    } else {
        gHasMockTarget = false;
        gMockTarget = {};
    }
}

extern "C" void SeriousIOS_ClearMockAimAssistTarget(void) {
    SeriousIOS_SetMockAimAssistTarget(nullptr);
}

extern "C" void SeriousIOS_ApplyAimAssistFilter(int* inOutDeltaX, int* inOutDeltaY) {
    if (inOutDeltaX == nullptr || inOutDeltaY == nullptr) {
        return;
    }

    SeriousIOSAimAssistConfig config;
    SeriousIOS_GetAimAssistConfig(&config);
    if (!config.enabled) {
        return;
    }

    const float rawDeltaX = static_cast<float>(*inOutDeltaX);
    const float rawDeltaY = static_cast<float>(*inOutDeltaY);
    const float rawSpeed = std::hypot(rawDeltaX, rawDeltaY);

    // Breakout guard: fast flick should never feel stuck
    if (rawSpeed > config.breakoutSpeed) {
        return;
    }

    SeriousIOSAimAssistTarget target = {};
    if (!SeriousIOS_GetAimAssistTarget(&target) || !target.hasTarget) {
        return;
    }

    // 1. Friction / Slowdown damping
    const float effectiveFriction = std::max(0.0f, std::min(1.0f, config.friction));
    const float frictionFactor = 1.0f - (effectiveFriction * 0.50f * target.proximity);
    float filteredDeltaX = rawDeltaX * frictionFactor;
    float filteredDeltaY = rawDeltaY * frictionFactor;

    // 2. Magnetic Pull
    const float desiredDeltaPixelsX = target.deltaYawDegrees * kDegreesToMousePixels;
    const float desiredDeltaPixelsY = target.deltaPitchDegrees * kDegreesToMousePixels;

    const float effectiveStrength = std::max(0.0f, std::min(1.5f, config.strength));
    const float pullWeight = target.proximity * 0.28f * effectiveStrength;

    // Apply gentle attraction towards target
    if (std::abs(desiredDeltaPixelsX) > 0.01f) {
        const float pullX = desiredDeltaPixelsX * pullWeight;
        filteredDeltaX += pullX;
    }
    if (std::abs(desiredDeltaPixelsY) > 0.01f) {
        const float pullY = desiredDeltaPixelsY * pullWeight;
        filteredDeltaY += pullY;
    }

    *inOutDeltaX = static_cast<int>(std::llround(filteredDeltaX));
    *inOutDeltaY = static_cast<int>(std::llround(filteredDeltaY));
}
