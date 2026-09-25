package.path = package.path .. ";./?.lua;./test/?.lua"
local A = require("assert")

-- The C half cannot run here; test/chiptune/ holds it to the original ROM.
-- What is tested here is the Lua half against a stand-in for the natives:
-- that it asks them for the right things, and stays inert without them.

-- Rule 1: loads and stays inert with no SDK present.
local C = require("chiptune")
A.falsy(C._ready, "not ready without the SDK")
A.falsy(C.load({ songs = { a = "a.gbm" } }), "load() fails off-device")
A.falsy(C.available, "and says the extension is missing")
A.falsy(C.play("a"), "play() no-ops")
A.falsy(C.sfx("coin"), "sfx() no-ops")
C.stop(); C.pause(); C.resume(); C.mute({ "wav" }); C.duck(4, 2); C.hold(2); C.update(); C.stopSfx()
A.eq(select(2, C.position()), 0, "position() is 0, 0")

-- ------------------------------------------------------------ SFX names
-- The trailer tools/gbm_format.py appends: names, u16 length, "NM".
local function trailer(names)
    local t = { string.char(#names) }
    for _, n in ipairs(names) do t[#t + 1] = string.char(#n) .. n end
    local body = table.concat(t)
    return body .. string.char(#body & 255, #body >> 8) .. "NM"
end
local blob = "GB\1" .. string.rep("\0", 40)
local names = C.parseNames(blob .. trailer({ "coin", "jump", "hit" }))
A.eq(#names, 3, "three names")
A.eq(names[1], "coin", "in bank order")
A.eq(names[3], "hit", "to the last")
A.eq(#C.parseNames(blob), 0, "a blob without names has none")
A.eq(#C.parseNames("NM"), 0, "and a truncated one does not crash")
A.eq(#C.parseNames(blob .. trailer({})), 0, "an empty list is empty")

-- --------------------------------------------------------------- masks
A.eq(C.mask({ "pu1", "noi" }), 9, "names -> bits")
A.eq(C.mask({ 3 }), 4, "channel 3 is the wave channel")
A.eq(C.mask(0x1FF), 255, "a mask passes through, clipped to 8 voices")
A.eq(C.mask({ 5, 8 }), 0x90, "format 2's voices 5-8 by number")
A.eq(C.mask({}), 0, "nothing muted")
A.falsy(pcall(C.mask, { "bass" }), "an unknown channel is an error, not silence")

-- ----------------------------------------------------------- callbacks
local synced, ended = {}, {}
C.onSync(function(v) synced[#synced + 1] = v end)
C.onEnd(function(n) ended[#ended + 1] = n end)
C._current, C._playing, C._sync = "victory", true, 0
C._observe(true, 0)
A.eq(#synced, 0, "no Exx yet: no callback")
C._observe(true, 3)
A.eq(synced[1], 3, "an Exx fires once")
C._observe(true, 3)
A.eq(#synced, 1, "and not again while it holds")
C._observe(false, 3)
A.eq(ended[1], "victory", "a song that stops reports its name")
A.eq(C.current(), nil, "and is no longer current")
C._observe(false, 3)
A.eq(#ended, 1, "once")

-- ---------------------------------------------- against a stand-in native
local calls = {}
local function log(name) return function(...) calls[#calls + 1] = { name, ... }; return true end end
local status = { false, 0, 0, 0, 0, 0 }
local nextId = 0
_G.chiptune_native = {
    load = function(bytes) nextId = nextId + 1; calls[#calls + 1] = { "load", #bytes }; return nextId end,
    play = log("play"), stop = log("stop"), pause = log("pause"), sfxbank = log("sfxbank"),
    sfx = log("sfx"), sfxstop = log("sfxstop"), duck = log("duck"), mute = log("mute"),
    hold = log("hold"), master = log("master"), volume = log("volume"),
    status = function() return table.unpack(status) end,
}
local files = { ["m/title.gbm"] = blob, ["m/sfx.gbm"] = blob .. trailer({ "coin", "jump" }) }
_G.playdate = { file = {
    kFileRead = 1,
    getSize = function(p) return files[p] and #files[p] end,
    open = function(p) local d = files[p]; return d and { read = function(_, n) return d:sub(1, n) end, close = function() end } end,
} }
package.loaded["chiptune"] = nil
Chiptune = nil
C = require("chiptune")
local ok, err = C.load({ songs = { title = "m/title.gbm" }, sfx = "m/sfx.gbm", duck = { amount = 5, speed = 3 } })
A.truthy(ok, "loads with the natives present: " .. tostring(err))
A.truthy(C.available, "and says so")
A.eq(C.sfxIndex("jump"), 1, "SFX names come from the bank")
A.eq(C.sfxNames()[1], "coin", "listed in order")

calls = {}
A.truthy(C.play("title"), "plays a loaded song")
A.eq(calls[1][1], "play", "through native.play")
A.eq(calls[1][3], 0, "from order 0")
calls = {}
C.play("title")
A.eq(#calls, 0, "playing it again does not restart it")
C.play("title", { restart = true, order = 2 })
A.eq(calls[1][3], 2, "unless asked, from where asked")
A.falsy(C.play("nope"), "an unknown song is refused")

calls = {}
C.sfx("jump")
A.eq(calls[1][2], 1, "sfx by name sends its index")
C.sfx(0)
A.eq(calls[2][2], 0, "and by index as it is")
A.falsy(C.sfx("boom"), "an unknown effect is refused")

calls = {}
C.mute({ "pu2", "wav" })
A.eq(calls[1][2], 6, "mute sends the mask")
C.hold()
A.eq(calls[2][2], 255, "hold(nil) lets the song go on")

status = { true, 3, 7, 0, 0, 100 }
local o, r = C.position()
A.eq(o, 3, "position reads the order")
A.eq(r, 7, "and the row")

_G.playdate, _G.chiptune_native = nil, nil
