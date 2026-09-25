/* chiptune for Lua games: registers the `chiptune_native` functions that
   chiptune.lua drives. Call from your eventHandler:

       if (event == kEventInitLua) chiptune_register(pd);

   or compile chiptune_main.c, which does exactly that, if the game has no
   C of its own. */
#ifndef CHIPTUNE_PD_H
#define CHIPTUNE_PD_H
#include "pd_api.h"
int chiptune_register(PlaydateAPI *pd);
#endif
