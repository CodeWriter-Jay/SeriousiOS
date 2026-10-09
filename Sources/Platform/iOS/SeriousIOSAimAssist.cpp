#include "SeriousIOSAimAssist.h"
#include "SeriousIOSPlatformBridge.h"

#include <algorithm>
#include <cmath>
#include <mutex>

#if __has_include(<Engine/Engine.h>) && __has_include(<GameMP/Game.h>)
#include <Engine/Engine.h>
#include <Engine/Entities/Entity.h>
#include <GameMP/Game.h>
#include <SeriousSam/Menu.h>
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
extern CGame* _pGame;
extern BOOL bMenuActive;

bool queryEngineTarget(
    const SeriousIOSAimAssistConfig& config,
    SeriousIOSAimAssistTarget* outTarget) {
    if (_pGame == nullptr || _pGame->gm_bGameOn == FALSE || bMenuActive != FALSE) {
        return false;
    }

    CEntity* playerEntity = _pGame->gm_actrlControls[0].ctrl_penPlayer;
    if (playerEntity == nullptr) {
        return false;
    }

    CPlacement3D playerPlacement = playerEntity->GetPlacement();
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

    CWorld* world = playerEntity->en_pWorld;
    if (world == nullptr) {
        return false;
    }

    float bestScore = -1.0f;
    SeriousIOSAimAssistTarget bestTarget = {};

    // Scan entities in the active world
    FOREACHINLIST(CEntity, en_lnInWorld, world->wo_lhEntities, itEntity) {
        CEntity* target = itEntity;
        if (target == nullptr || target == playerEntity) {
            continue;
        }

        // Target must be alive and an enemy/monster
        if ((target->en_flFlags & ENF_ALIVE) == 0) {
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
        ray.cr_ttHitModels = CWorld::TT_COLLISIONBOX;
        if (world->CastRay(ray)) {
            if (ray.cr_penHit != target) {
                continue;
            }
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
    gConfig.strength = std::max(0.0f, std::min(2.0f, gConfig.strength));
    gConfig.friction = std::max(0.0f, std::min(1.0f, gConfig.friction));
    gConfig.maxAngleDegrees = std::max(1.0f, std::min(30.0f, gConfig.maxAngleDegrees));
    gConfig.maxDistance = std::max(5.0f, std::min(100.0f, gConfig.maxDistance));
    gConfig.breakoutSpeed = std::max(10.0f, std::min(200.0f, gConfig.breakoutSpeed));
}

extern "C" void SeriousIOS_GetAimAssistConfig(SeriousIOSAimAssistConfig* outConfig) {
    if (outConfig == nullptr) {
        return;
    }
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    *outConfig = gConfig;
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

extern "C" void SeriousIOS_SetMockAimAssistTarget(const SeriousIOSAimAssistTarget* mockTarget) {
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    if (mockTarget != nullptr) {
        gMockTarget = *mockTarget;
        gHasMockTarget = true;
    } else {
        gHasMockTarget = false;
        gMockTarget = {};
    }
}

extern "C" void SeriousIOS_ClearMockAimAssistTarget(void) {
    std::lock_guard<std::mutex> lock(gAimAssistMutex);
    gHasMockTarget = false;
    gMockTarget = {};
}

extern "C" bool SeriousIOS_GetAimAssistTarget(SeriousIOSAimAssistTarget* outTarget) {
    SeriousIOSAimAssistConfig configCopy;
    {
        std::lock_guard<std::mutex> lock(gAimAssistMutex);
        if (!gConfig.enabled) {
            if (outTarget != nullptr) {
                outTarget->hasTarget = false;
            }
            return false;
        }
        if (gHasMockTarget) {
            if (outTarget != nullptr) {
                *outTarget = gMockTarget;
            }
            return gMockTarget.hasTarget;
        }
        configCopy = gConfig;
    }

#if SERIOUSIOS_HAS_ENGINE
    return queryEngineTarget(configCopy, outTarget);
#else
    if (outTarget != nullptr) {
        outTarget->hasTarget = false;
    }
    return false;
#endif
}

extern "C" void SeriousIOS_ApplyAimAssistFilter(int* deltaX, int* deltaY) {
    if (deltaX == nullptr || deltaY == nullptr) {
        return;
    }
    if (*deltaX == 0 && *deltaY == 0) {
        return;
    }

    SeriousIOSAimAssistConfig config;
    SeriousIOS_GetAimAssistConfig(&config);
    if (!config.enabled) {
        return;
    }

    // Fast flick breakout detection: preserve snappy turning when user swipes quickly
    const double inputSpeed = std::hypot(static_cast<double>(*deltaX), static_cast<double>(*deltaY));
    if (inputSpeed > config.breakoutSpeed) {
        return;
    }

    SeriousIOSAimAssistTarget target = {};
    if (!SeriousIOS_GetAimAssistTarget(&target) || !target.hasTarget) {
        return;
    }

    const float proximity = std::max(0.0f, std::min(1.0f, target.proximity));

    // 1. Friction / Slowdown: Dampen crosshair movement near target
    const float frictionScale = 1.0f - (config.friction * 0.50f * proximity);
    const float dampedX = static_cast<float>(*deltaX) * frictionScale;
    const float dampedY = static_cast<float>(*deltaY) * frictionScale;

    // 2. Target Magnetism Pull: Apply directional attraction towards target center
    const float targetPixelX = target.deltaYawDegrees * kDegreesToMousePixels;
    const float targetPixelY = target.deltaPitchDegrees * kDegreesToMousePixels;

    // Pull when user is moving towards target or inside inner proximity cone
    const float dotProduct = static_cast<float>(*deltaX) * targetPixelX + static_cast<float>(*deltaY) * targetPixelY;
    float pullX = 0.0f;
    float pullY = 0.0f;

    if (dotProduct > 0.0f || proximity > 0.65f) {
        const float pullFactor = 0.22f * config.strength * proximity;
        pullX = targetPixelX * pullFactor;
        pullY = targetPixelY * pullFactor;

        // Clamp maximum pull delta per frame to prevent jarring snap
        const float maxPull = 9.0f * config.strength;
        pullX = std::max(-maxPull, std::min(maxPull, pullX));
        pullY = std::max(-maxPull, std::min(maxPull, pullY));
    }

    *deltaX = static_cast<int>(std::lround(dampedX + pullX));
    *deltaY = static_cast<int>(std::lround(dampedY + pullY));
}
