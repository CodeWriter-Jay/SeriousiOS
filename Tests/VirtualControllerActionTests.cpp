#include "SeriousIOSInputBridge.h"
#include "SeriousIOSPlatformBridge.h"

#include <SDL.h>

#include <cassert>
#include <cstdarg>
#include <iostream>

extern "C" {
void SeriousIOS_DiagnosticsLog(const char* /*domain*/, const char* /*format*/, ...) {}
void SeriousIOS_DiagnosticsLogV(const char* /*domain*/, const char* /*format*/, va_list /*args*/) {}
void SeriousIOS_SetSDLMouseState(int /*x*/, int /*y*/, unsigned int /*buttons*/) {}
}

namespace {

void drainEvents() {
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
    }
}

void testNextAndPrevWeaponActions() {
    drainEvents();

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_NEXT_WEAPON, true);
    SDL_Event event = {};
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYDOWN);
    assert(event.key.keysym.sym == SDLK_RIGHTBRACKET);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_NEXT_WEAPON, false);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYUP);
    assert(event.key.keysym.sym == SDLK_RIGHTBRACKET);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_PREVIOUS_WEAPON, true);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYDOWN);
    assert(event.key.keysym.sym == SDLK_LEFTBRACKET);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_PREVIOUS_WEAPON, false);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYUP);
    assert(event.key.keysym.sym == SDLK_LEFTBRACKET);

    std::cout << "[PASS] testNextAndPrevWeaponActions\n";
}

void testAltFireScopeAction() {
    drainEvents();

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_ALT_FIRE, true);
    SDL_Event event = {};
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_MOUSEBUTTONDOWN);
    assert(event.button.button == SDL_BUTTON_RIGHT);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_ALT_FIRE, false);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_MOUSEBUTTONUP);
    assert(event.button.button == SDL_BUTTON_RIGHT);

    std::cout << "[PASS] testAltFireScopeAction\n";
}

void testCrouchComputerQuickSaveActions() {
    drainEvents();

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_CROUCH, true);
    SDL_Event event = {};
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYDOWN);
    assert(event.key.keysym.sym == SDLK_c);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_COMPUTER, true);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYDOWN);
    assert(event.key.keysym.sym == SDLK_TAB);

    SeriousIOS_SetVirtualAction(SERIOUSIOS_ACTION_QUICK_SAVE, true);
    assert(SDL_PollEvent(&event) == 1);
    assert(event.type == SDL_KEYDOWN);
    assert(event.key.keysym.sym == SDLK_F6);

    SeriousIOS_ReleaseVirtualController();
    int releasedKeys = 0;
    while (SDL_PollEvent(&event)) {
        if (event.type == SDL_KEYUP) {
            releasedKeys++;
        }
    }
    assert(releasedKeys == 3);

    std::cout << "[PASS] testCrouchComputerQuickSaveActions\n";
}

} // namespace

int main() {
    testNextAndPrevWeaponActions();
    testAltFireScopeAction();
    testCrouchComputerQuickSaveActions();
    std::cout << "All virtual controller action tests passed successfully.\n";
    return 0;
}
