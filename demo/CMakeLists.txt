# The Zoo's C side: chiptune, nothing else. tools/build_demo.py drives this;
# it is also the smallest example of adding chiptune to a Lua game.
cmake_minimum_required(VERSION 3.19)
set(CMAKE_C_STANDARD 11)

set(ENVSDK $ENV{PLAYDATE_SDK_PATH})
if (NOT ${ENVSDK} STREQUAL "")
	file(TO_CMAKE_PATH ${ENVSDK} SDK)
else()
	execute_process(
		COMMAND bash -c "egrep '^\\s*SDKRoot' $HOME/.Playdate/config"
		COMMAND head -n 1
		COMMAND cut -c9-
		OUTPUT_VARIABLE SDK
		OUTPUT_STRIP_TRAILING_WHITESPACE)
endif()
if (NOT EXISTS ${SDK})
	message(FATAL_ERROR "SDK Path not found; set ENV value PLAYDATE_SDK_PATH")
endif()

set(CMAKE_CONFIGURATION_TYPES "Debug;Release")
set(PLAYDATE_GAME_NAME Juice)
set(PLAYDATE_GAME_DEVICE Juice_DEVICE)
project(${PLAYDATE_GAME_NAME} C ASM)

include(${CMAKE_CURRENT_SOURCE_DIR}/../chiptune/chiptune.cmake)

if (TOOLCHAIN STREQUAL "armgcc")
	add_executable(${PLAYDATE_GAME_DEVICE} ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
else()
	add_library(${PLAYDATE_GAME_NAME} SHARED ${CHIPTUNE_SOURCES} ${CHIPTUNE_MAIN})
endif()

include(${SDK}/C_API/buildsupport/playdate_game.cmake)
