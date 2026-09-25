# chiptune's C sources, for a Playdate CMake project.
#
#   include(Source/juice/chiptune/chiptune.cmake)
#   add_library(${PLAYDATE_GAME_NAME} SHARED ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})   # simulator
#   add_executable(${PLAYDATE_GAME_DEVICE} ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})     # device
#
# CHIPTUNE_MAIN is the stand-in eventHandler for a game with no C of its own;
# a game with its own eventHandler leaves it out and calls chiptune_register().
set(CHIPTUNE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(CHIPTUNE_SOURCES
    ${CHIPTUNE_DIR}/gbapu.c
    ${CHIPTUNE_DIR}/gbm.c
    ${CHIPTUNE_DIR}/chip.c
    ${CHIPTUNE_DIR}/chiptune_pd.c)
set(CHIPTUNE_MAIN ${CHIPTUNE_DIR}/chiptune_main.c)
