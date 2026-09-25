/* The whole C side of a Lua game that only wants chiptune. A game with C of
   its own leaves this file out and calls chiptune_register() itself. */
#include "pd_api.h"
#include "chiptune_pd.h"

#ifdef _WINDLL
__declspec(dllexport)
#endif
int eventHandler(PlaydateAPI *pd, PDSystemEvent event, uint32_t arg)
{
    (void)arg;
    if (event == kEventInitLua) chiptune_register(pd);
    return 0;
}
