-- chiptune -- Game Boy music and sound effects, from a real tracker driver.
--
-- The engine is GBM, a tracker driver written for the DMG, ported to C and
-- run with an emulated DMG APU inside a Playdate audio callback (chiptune/).
-- Songs are tracker projects encoded to small blobs (a few KB for a minute of
-- music): four channels, instruments with LSDj-style tables, arpeggios,
-- slides, vibrato, drum samples, and two SFX slots that borrow a channel
-- from the music and give it back.
--
-- This file is the Lua face of it. It needs the C half built into the game
-- (chiptune/README.md); without it every call is a silent no-op and
-- Chiptune.available is false, so a game can still run -- or fall back to
-- pre-rendered audio through Jukebox (tools/chiptune.py render).
--
-- Why the music runs on the audio thread and not in playdate.update: the
-- driver ticks 59.73 times a second, like the Game Boy's VBlank. Ticked from
-- a 30 fps update loop, every song would play at half speed, and every slow
-- frame would be a stumble in the music.
Chiptune = Chiptune or {}

local pd = rawget(_G, "playdate")

-- ============================================================== pure section

Chiptune.available = false
Chiptune._ready    = false
Chiptune._songs    = {}      -- name -> native id
Chiptune._sfx      = {}      -- name -> index in the SFX bank
Chiptune._current  = nil
Chiptune._sync     = 0
Chiptune._playing  = false
Chiptune._onSync   = nil
Chiptune._onEnd    = nil

--- The SFX names an encoded blob carries after its data (tools/gbm_format.py):
--- names := count { len bytes }*, then u16 len(names), then "NM".
--- Returns a list in bank order, or {} for a blob without them.
function Chiptune.parseNames(bytes)
    local n = #bytes
    if n < 4 or bytes:sub(n - 1) ~= "NM" then return {} end
    local len = bytes:byte(n - 3) | (bytes:byte(n - 2) << 8)
    local at = n - 3 - len
    if at < 1 then return {} end
    local count = bytes:byte(at)
    local out, p = {}, at + 1
    for i = 1, count do
        local l = bytes:byte(p)
        if not l then break end
        out[i] = bytes:sub(p + 1, p + l)
        p = p + 1 + l
    end
    return out
end

--- Channel list -> the driver's mute mask. Accepts a mask as it is, or names
--- ("pu1", "pu2", "wav", "noi") / numbers 1-8 (a format-2 song has up to 8
--- voices), so call sites read as intent.
local CHANNEL = { pu1 = 1, pu2 = 2, wav = 4, noi = 8 }
for n = 1, 8 do CHANNEL[n] = 1 << (n - 1) end
function Chiptune.mask(channels)
    if type(channels) == "number" then return channels & 255 end
    local m = 0
    for _, c in ipairs(channels or {}) do
        local b = CHANNEL[type(c) == "string" and c:lower() or c]
        assert(b, "chiptune: no channel " .. tostring(c))
        m = m | b
    end
    return m
end

--- An SFX by name or by 0-based index -> its index, or nil.
function Chiptune.sfxIndex(id)
    if type(id) == "number" then return id end
    return Chiptune._sfx[id]
end

--- Feed a status snapshot through the callbacks: the part of update() that
--- does not touch the device.
function Chiptune._observe(playing, sync)
    if sync ~= Chiptune._sync then
        Chiptune._sync = sync
        if Chiptune._onSync then Chiptune._onSync(sync) end
    end
    if Chiptune._playing and not playing then
        local name = Chiptune._current
        Chiptune._current = nil
        if Chiptune._onEnd then Chiptune._onEnd(name) end
    end
    Chiptune._playing = playing
end

-- ============================================================ device layer

local native = nil

local function readFile(path)
    local file = pd.file
    local size = file.getSize(path)
    local f = size and file.open(path, file.kFileRead)
    if not f then return nil, "chiptune: cannot open " .. path end
    local data = f:read(size)
    f:close()
    return data
end

--- spec = { songs = { title = "music/title.gbm", battle = "music/battle.gbm" },
---          sfx = "music/sfx.gbm",            -- an SFX bank (names inside)
---          duck = { amount = 6, speed = 2 },  -- music dips while an effect plays
---          volume = 0.8 }
--- Returns true, or false and why.
function Chiptune.load(spec)
    native = rawget(_G, "chiptune_native")
    Chiptune.available = native ~= nil
    if not (pd and native) then return false, "chiptune: the C extension is not built in" end
    spec = spec or {}
    for name, path in pairs(spec.songs or {}) do
        local data, err = readFile(path)
        if not data then return false, err end
        local id, why = native.load(data)
        if not id then return false, "chiptune: " .. path .. ": " .. tostring(why) end
        Chiptune._songs[name] = id
    end
    if spec.sfx then
        local data, err = readFile(spec.sfx)
        if not data then return false, err end
        local id, why = native.load(data)
        if not id then return false, "chiptune: " .. spec.sfx .. ": " .. tostring(why) end
        native.sfxbank(id)
        for i, n in ipairs(Chiptune.parseNames(data)) do Chiptune._sfx[n] = i - 1 end
    end
    local d = spec.duck or { amount = 6, speed = 2 }
    native.duck(d.amount or 0, d.speed or 1)
    if spec.volume then native.volume(spec.volume) end
    Chiptune._ready = true
    return true
end

--- Plays a song from its start (or from order/row), unless it is already the
--- one playing: most "play the menu music" calls come back to a menu whose
--- music never stopped, and restarting it there is the bug players notice.
--- opts = { order = 0, row = 0, restart = false }
function Chiptune.play(name, opts)
    if not Chiptune._ready then return false end
    local id = Chiptune._songs[name]
    if not id then return false end
    opts = opts or {}
    if Chiptune._current == name and Chiptune._playing and not opts.restart then return true end
    if not native.play(id, opts.order or 0, opts.row or 0) then return false end
    Chiptune._current = name
    Chiptune._playing = true
    return true
end

function Chiptune.stop()
    if not Chiptune._ready then return end
    native.stop()
    Chiptune._current, Chiptune._playing = nil, false
end

--- Fires an effect by name (or 0-based index). An effect of lower priority
--- than the ones already sounding is dropped by the driver.
function Chiptune.sfx(id)
    if not Chiptune._ready then return false end
    local i = Chiptune.sfxIndex(id)
    if not i then return false end
    return native.sfx(i)
end

function Chiptune.stopSfx()
    if Chiptune._ready then native.sfxstop() end
end

--- Music volume drops `amount` envelope steps (0-15) while an effect plays,
--- a step every `speed` frames. 0 turns ducking off.
function Chiptune.duck(amount, speed)
    if Chiptune._ready then native.duck(amount or 0, speed or 1) end
end

--- Silences music channels ({"wav", "noi"}, or a mask); the song keeps time,
--- so unmuting brings a part back in on the beat -- layered music for free.
function Chiptune.mute(channels)
    if Chiptune._ready then native.mute(Chiptune.mask(channels)) end
end

--- Repeat one order instead of moving on (nil lets the song continue): a
--- "wait here until the boss is ready" loop.
function Chiptune.hold(order)
    if Chiptune._ready then native.hold(order or 255) end
end

--- 0-1, both ears (or left, right).
function Chiptune.setVolume(l, r)
    if Chiptune._ready then native.volume(l, r or l) end
end

--- Wire to playdate.gameWillPause / gameWillResume: the system menu should
--- not play over the music.
function Chiptune.pause()
    if Chiptune._ready then native.pause(true) end
end

function Chiptune.resume()
    if Chiptune._ready then native.pause(false) end
end

--- fn(value) runs when the song passes an Exx command: hang gameplay on the
--- music (a door opens on the downbeat, a boss appears at the drop).
function Chiptune.onSync(fn) Chiptune._onSync = fn end
--- fn(name) runs when a song without a loop ends.
function Chiptune.onEnd(fn) Chiptune._onEnd = fn end

--- Once a frame, for the callbacks.
function Chiptune.update()
    if not Chiptune._ready then return end
    local playing, _, _, sync = native.status()
    Chiptune._observe(playing, sync)
end

--- order, row: where the song is (the next row to play).
function Chiptune.position()
    if not Chiptune._ready then return 0, 0 end
    local _, order, row = native.status()
    return order, row
end

--- A level 0-15 per music channel (PU1, PU2, WAV, NOI; or a format-2 song's
--- 1-8 voices), as they sound right now: for meters and for things that
--- pulse with the music.
function Chiptune.levels()
    if not Chiptune._ready then return 0, 0, 0, 0 end
    return native.levels()
end

function Chiptune.current() return Chiptune._current end
function Chiptune.isPlaying() return Chiptune._playing end

--- The effects in the loaded bank, sorted by index.
function Chiptune.sfxNames()
    local out = {}
    for n, i in pairs(Chiptune._sfx) do out[i + 1] = n end
    return out
end

return Chiptune
