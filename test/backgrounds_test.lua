-- Host tests for backgrounds.lua.
--
-- The headline case is the first one: this file runs under a stock `lua` with
-- no `playdate` global anywhere, so simply getting to line two proves the
-- module keeps CONVENTIONS rule 1. Everything after that leans on the pure
-- simulation being reachable without the SDK (rule 3).

local A = require("assert")

-- ---------------------------------------------------------------- rule 1 ---

A.eq(rawget(_G, "playdate"), nil, "host lua really has no playdate global")

local B = require("backgrounds")

A.truthy(B, "require('backgrounds') returns the module")
A.eq(B, rawget(_G, "Backgrounds"), "module is also published as a global")
A.eq(type(B.update), "function", "update is exported")
A.eq(type(B.draw), "function", "draw is exported")

-- load() must report "not ready" rather than crash when there is no SDK, and
-- every draw path must then be a silent no-op.
A.eq(B.load(), false, "load reports no SDK on the host")
A.eq(B._ready, false, "_ready is false without the SDK")
for i = 1, B.count do
    A.eq(B.draw(i), false, "draw(" .. i .. ") no-ops without the SDK")
end
A.eq(B.draw(0), false, "draw(0) is refused")
A.eq(B.draw(B.count + 1), false, "draw past the end is refused")

local W, H = B.SCREEN_W, B.SCREEN_H
A.eq(W, 400, "screen width")
A.eq(H, 240, "screen height")

-- --------------------------------------------------- names vs. implementations

A.eq(#B.names, B.count, "names list length matches count")

local implemented = 0
while B.state(implemented + 1) do implemented = implemented + 1 end
A.eq(implemented, B.count, "count matches the number of implementations")
A.eq(B.state(B.count + 1), nil, "no state past the last background")
A.eq(B.state(0), nil, "no state at index 0")

local seen = {}
local namesOk = true
for i = 1, B.count do
    local n = B.names[i]
    if type(n) ~= "string" or n == "" or seen[n] then namesOk = false end
    seen[n] = true
    A.eq(B.getName(i), n, "getName(" .. i .. ") agrees with the name list")
    A.eq(B.indexOf(n), i, "indexOf round-trips " .. tostring(n))
end
A.truthy(namesOk, "every name is a non-empty unique string")
A.eq(B.getName(B.count + 1), nil, "getName is nil past the end")
A.eq(B.indexOf("Nope"), nil, "indexOf is nil for an unknown name")

-- The nine the README advertises must still be there after the refactor.
for _, n in ipairs({"Starfield", "Waves", "Radar", "Rain", "Squares",
                    "Spirograph", "Lava Lamp", "Dither Hills", "Bubbles Rise"}) do
    A.truthy(B.indexOf(n), "README background still present: " .. n)
end

-- ------------------------------------------------------------- invariants ---

-- Every cyclic quantity must sit inside [0, period) and must be advancing by a
-- rate smaller than that period -- that is what makes the single-subtract wrap
-- in advance() correct and the animation safe on a 32-bit float forever.
local function accsOk(st)
    for i = 1, st.np do
        local p, r, per = st.p[i], st.rate[i], st.per[i]
        if type(per) ~= "number" or per <= 0 then return false, "bad period" end
        if type(r) ~= "number" or r <= 0 or r >= per then return false, "bad rate" end
        if p < 0 or p >= per then return false, "accumulator escaped its period" end
    end
    return true, "ok"
end

local function boundsOk(st, margin)
    local items = st.items
    for k = 1, #items do
        local it = items[k]
        if type(it.x) == "number" and (it.x < -margin or it.x > W + margin) then return false end
        if type(it.y) == "number" and (it.y < -margin or it.y > H + margin) then return false end
    end
    -- Lightning keeps its vertices as flat {x,y,x,y,...} lists, not item tables.
    if st.bolts then
        for b = 1, #st.bolts do
            local bolt = st.bolts[b]
            for k = 1, #bolt, 2 do
                if bolt[k] < -margin or bolt[k] > W + margin then return false end
                if bolt[k + 1] < -margin or bolt[k + 1] > H + margin then return false end
            end
        end
    end
    return true
end

-- A cheap order-sensitive fingerprint of the whole simulation.
local function signature(st)
    local acc = 0
    for i = 1, st.np do acc = acc + st.p[i] * i end
    local items = st.items
    for i = 1, #items do
        local it = items[i]
        if type(it.x) == "number" then acc = acc + it.x * (i + 1) end
        if type(it.y) == "number" then acc = acc + it.y * (i + 2) end
        if type(it.r) == "number" then acc = acc + it.r * (i + 3) end
    end
    if st.grid then
        for i = 1, #st.grid do acc = acc + st.grid[i] * i end
    end
    if st.bolts then
        for b = 1, #st.bolts do
            local bolt = st.bolts[b]
            for k = 1, #bolt do acc = acc + bolt[k] * k * b end
        end
    end
    -- Music-driven derived state (Terrain's column gains, the Equalizer's bars).
    for _, key in ipairs({"gain", "bar"}) do
        local t = st[key]
        if t then for i = 1, #t do acc = acc + t[i] * (i + 5) end end
    end
    return acc
end

local SEED <const> = 424242
local STEPS <const> = 400

local function run(i, seed, steps)
    local st = B.reset(i, seed)
    local ok = true
    local why = "ok"
    local margin = B.margin(i)
    for n = 1, steps do
        B.update(i)
        -- Sample rather than assert every frame: one bad frame poisons the
        -- accumulated fingerprint anyway, and this keeps the check count sane.
        if n % 40 == 0 then
            local a, msg = accsOk(st)
            if not a then ok, why = false, msg end
            if not boundsOk(st, margin) then ok, why = false, "left the screen" end
        end
    end
    return st, ok, why
end

local firstPass = {}
for i = 1, B.count do
    local st, ok, why = run(i, SEED, STEPS)
    A.truthy(ok, B.names[i] .. " stays bounded and in-period (" .. why .. ")")
    A.truthy(st.np > 0 or #st.items > 0, B.names[i] .. " actually has state")
    firstPass[i] = signature(st)
end

-- Same seed, same frames, same state: the whole point of dropping math.random.
for i = 1, B.count do
    local st = run(i, SEED, STEPS)
    A.eq(signature(st), firstPass[i], B.names[i] .. " replays identically from a seed")
end

-- The randomised backgrounds must actually depend on the seed, or "deterministic
-- from a seed" would be true for the boring reason.
for _, n in ipairs({"Starfield", "Rain", "Matrix Rain", "Confetti", "Life", "Lightning"}) do
    local i = B.indexOf(n)
    local st = run(i, SEED + 1, STEPS)
    A.truthy(signature(st) ~= firstPass[i], n .. " differs on a different seed")
end

-- ------------------------------------------------------------------ looping --

-- The reason accumulators exist. 30000 frames is about 17 minutes at 30fps --
-- a plausible "left it on the menu" session. Every phase must still be inside
-- its period and every particle still on screen, exactly as at frame one. A
-- module that had kept `tick * rate` would pass this and still die later; what
-- this pins is that nothing here can grow at all.
local LONG <const> = 30000
for i = 1, B.count do
    if B.names[i] ~= "Life" then   -- a 1500-cell CA every 6th frame; not worth 30k frames here
        local st = B.reset(i, SEED)
        local ok, why = true, "ok"
        for n = 1, LONG do
            B.update(i)
            if n % 2500 == 0 then
                local a, msg = accsOk(st)
                if not a then ok, why = false, msg end
                if not boundsOk(st, B.margin(i)) then ok, why = false, "left the screen" end
            end
        end
        A.truthy(ok, B.names[i] .. " still loops cleanly after " .. LONG .. " frames (" .. why .. ")")
    end
end

-- Phase-only backgrounds must genuinely move, otherwise the wrap test above
-- would pass on a frozen animation.
for _, n in ipairs({"Waves", "Radar", "Squares", "Spirograph", "Plasma", "Fire",
                    "Moire", "Terrain", "Dither Hills", "Lava Lamp"}) do
    local i = B.indexOf(n)
    local st = B.reset(i, SEED)
    local before = signature(st)
    B.update(i)
    A.truthy(signature(st) ~= before, n .. " advances when updated")
end

-- ------------------------------------------------------------ dither tiles --

-- CONVENTIONS rule 6: an all-zero tile renders solid black, not transparent.
-- Every level any background can ask for must light at least one pixel of the
-- equivalent 8x8 Bayer tile, and so must a level a future edit gets wrong.
for _, lvl in ipairs(B.DITHER_LEVELS) do
    local s = B.safeDither(lvl)
    A.truthy(s > 0 and s <= 1, "dither level " .. lvl .. " clamps into (0,1]")
    A.truthy(B.ditherPixels(lvl) >= 1, "dither level " .. lvl .. " is not an all-zero tile")
end
A.truthy(B.ditherPixels(0) >= 1, "a zero level still lights a pixel")
A.truthy(B.ditherPixels(-3) >= 1, "a negative level still lights a pixel")
A.truthy(B.ditherPixels(nil) >= 1, "a nil level still lights a pixel")
A.eq(B.ditherPixels(1), 64, "a full level fills the tile")
A.eq(B.ditherPixels(9), 64, "an over-range level saturates rather than wrapping")
A.eq(B.safeDither(0.5), 0.5, "an in-range level passes through untouched")

-- --------------------------------------------------------------- lifecycle --

-- update() with no argument follows the last background drawn, so the README's
-- update()/draw(i) pair works without the consumer tracking an index.
B.draw(3)
A.eq(B.current, 3, "draw records the current background")
local radar = B.state(3)
local before = signature(radar)
B.update()
A.truthy(signature(radar) ~= before, "bare update() advances the current background")

-- A brand-new index must not have been simulated by the calls above -- that is
-- the "one background must not pay for the other sixteen" rule.
B.load({seed = 99})
A.eq(B._states[1], nil, "load with a seed drops the built states")
A.eq(B._seed, 99, "load stores the seed")
B.state(5)
A.eq(B._states[6], nil, "asking for one background builds only that one")

-- Out-of-range calls stay quiet instead of indexing a nil spec.
B.update(0)
B.update(B.count + 1)
B.update(nil)
A.eq(B.reset(B.count + 1), nil, "reset past the end returns nil")
A.truthy(B.reset(1, 7), "reset with a seed returns the fresh state")

-- ----------------------------------------------------------- music input ---

local au = B.audio
A.eq(au.energy, 0, "nothing fed: no energy")
A.eq(au.beat, 0, "nothing fed: no beat")

-- With no levels, or an all-zero feed, every background must be the one it
-- always was. Unfed vs zero-fed catches any reactive term that is not exactly
-- neutral at zero (a stray +0.5, a gain that is 1.0000001).
for i = 1, B.count do
    B.resetLevels()
    local plain = B.reset(i, SEED)
    for _ = 1, 150 do B.update(i) end
    local want = signature(plain)
    local wantGain = plain.gain and plain.gain[10]

    B.resetLevels()
    local fed = B.reset(i, SEED)
    for _ = 1, 150 do B.setLevels(0, 0, 0, 0); B.update(i) end
    A.eq(signature(fed), want, B.names[i] .. ": zero levels == no levels")
    A.eq(fed.gain and fed.gain[10], wantGain, B.names[i] .. ": zero levels leave gains neutral")
end

-- Smoothing: fast attack, slower decay, and an exact return to silence.
B.resetLevels()
B.setLevels(15, 0, 0, 0)
A.near(au.env[1], 0.6, 1e-9, "attack closes 60% of the gap in a frame")
B.setLevels(15, 0, 0, 0)
A.near(au.env[1], 0.84, 1e-9, "attack keeps closing")
A.near(au.energy, 0.84, 1e-9, "energy is the loudest smoothed channel")
B.setLevels(0, 0, 0, 0)
A.near(au.env[1], 0.84 * 0.88, 1e-9, "decay is slower than attack")
local prevEnv, mono = au.env[1], true
local frames = 0
while au.env[1] > 0 and frames < 200 do
    B.setLevels(0, 0, 0, 0)
    if au.env[1] > prevEnv then mono = false end
    prevEnv = au.env[1]
    frames = frames + 1
end
A.truthy(mono, "decay never rises")
A.eq(au.env[1], 0, "the tail snaps to exactly zero")
A.truthy(frames < 60, "and does so in a bounded time")

-- Input shapes: values, array, range clamping, channel cap.
B.resetLevels()
B.setLevels(15, 7.5, 0)
local a1, a2 = au.raw[1], au.raw[2]
B.resetLevels()
B.setLevels({15, 7.5, 0})
A.eq(au.raw[1], a1, "array form == value form (ch 1)")
A.eq(au.raw[2], a2, "array form == value form (ch 2)")
A.eq(au.n, 3, "n counts the channels fed")
A.eq(a1, 1, "15 is full scale")
A.eq(a2, 0.5, "7.5 is half scale")
B.setLevels(99, -4, "x", nil, 3)
A.eq(au.raw[1], 1, "over-range clamps to 1")
A.eq(au.raw[2], 0, "negative clamps to 0")
A.eq(au.raw[3], 0, "non-numbers read as 0")
B.setLevels(1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
A.eq(au.n, 8, "more than 8 channels are ignored")
B.setLevels()
A.eq(au.n, 0, "an empty feed means silence")

-- Onsets: a sudden rise is a hit, a held note is not, and hits have a refractory gap.
B.resetLevels()
B.setLevels(0, 0, 0, 0)
A.falsy(au.onset, "silence is not a hit")
B.setLevels(0, 0, 0, 15)
A.truthy(au.onset, "a jump from silence is a hit")
A.eq(au.beat, 1, "a hit sets the beat to 1")
B.setLevels(0, 0, 0, 15)
A.falsy(au.onset, "a held note is not another hit")
A.near(au.beat, 0.82, 1e-9, "the beat decays")
B.setLevels(0, 0, 0, 0)
B.setLevels(0, 0, 0, 15)
A.falsy(au.onset, "a rise inside the refractory gap is ignored")
for _ = 1, 10 do B.setLevels(0, 0, 0, 0) end
B.setLevels(0, 0, 0, 15)
A.truthy(au.onset, "the next hit registers once the gap is over")
for _ = 1, 60 do B.setLevels(0, 0, 0, 15) end
A.eq(au.beat, 0, "the beat dies out to exactly zero")
B.resetLevels()
B.setLevels(0, 0, 0, 2)
A.falsy(au.onset, "a small rise is not a hit")

-- Reactive backgrounds really react, and deterministically.
local function loud(i, steps)
    B.resetLevels()
    local st = B.reset(i, SEED)
    for n = 1, steps do
        B.setLevels(15, (n * 5) % 16, 15 - (n * 3) % 16, (n * 7) % 16)
        B.update(i)
    end
    return st
end
for _, n in ipairs({"Starfield", "Radar", "Plasma", "Dither Hills", "Terrain", "Equalizer"}) do
    local i = B.indexOf(n)
    A.truthy(i, n .. " exists")
    B.resetLevels()
    local quiet = signature(run(i, SEED, 120))
    local a = signature(loud(i, 120))
    local b = signature(loud(i, 120))
    A.eq(a, b, n .. " reacts the same way every time")
    A.truthy(a ~= quiet, n .. " changes with the music")
end
B.resetLevels()
A.truthy(B.isReactive(B.indexOf("Terrain")), "Terrain is flagged reactive")
A.falsy(B.isReactive(B.indexOf("Waves")), "Waves is not")
A.falsy(B.isReactive(99), "unknown index is not")

-- Terrain: a loud left channel raises the left of the ridge line, not the right.
B.resetLevels()
local ter = B.reset(B.indexOf("Terrain"), SEED)
for _ = 1, 30 do B.setLevels(15, 0, 0, 0); B.update(B.indexOf("Terrain")) end
A.truthy(ter.gain[1] > 1.9, "terrain: loud channel 1 lifts the left column")
A.near(ter.gain[31], 1, 1e-9, "terrain: silent channel 4 leaves the right column alone")
A.truthy(ter.gain[1] > ter.gain[16], "terrain: gain falls off across the spectrum")

-- Equalizer: bars follow the envelope, stay in range, and the peak holds then falls.
B.resetLevels()
local eqI = B.indexOf("Equalizer")
local eq = B.reset(eqI, SEED)
for _ = 1, 10 do B.setLevels(15, 15, 15, 15); B.update(eqI) end
local eqOk = true
for c = 1, #eq.bar do
    if eq.bar[c] < 0 or eq.bar[c] > 1 or eq.peak[c] < eq.bar[c] then eqOk = false end
end
A.truthy(eqOk, "equalizer bars in 0..1 with the peak at or above")
A.truthy(eq.bar[8] > 0.5, "equalizer bars rise with a loud feed")
local top = eq.peak[8]
for _ = 1, 8 do B.setLevels(0, 0, 0, 0); B.update(eqI) end
A.eq(eq.peak[8], top, "the peak holds for a few frames")
for _ = 1, 80 do B.setLevels(0, 0, 0, 0); B.update(eqI) end
A.eq(eq.peak[8], 0, "then falls to the floor")
A.eq(eq.bar[8], 0, "and the bar is empty")

-- Lightning strikes on a musical hit, but not inside the flash of the last one.
B.resetLevels()
local lI = B.indexOf("Lightning")
local lt = B.reset(lI, SEED)
local bolts0 = lt.bolts
for _ = 1, 10 do B.update(lI) end
A.eq(lt.bolts, bolts0, "no music, no early strike")
A.eq(lt.p[1], 10, "the timer is at frame 10")
B.setLevels(0, 0, 0, 15)
B.update(lI)
A.eq(lt.p[1], 0, "a hit restarts the strike age")
A.truthy(lt.bolts ~= bolts0, "and builds a new bolt")
for _ = 1, 8 do B.setLevels(0, 0, 0, 0) end
local bolts1 = lt.bolts
B.setLevels(0, 0, 0, 15)
B.update(lI)
A.eq(lt.bolts, bolts1, "a hit during the flash does not re-strike")
A.eq(lt.p[1], 1, "the age keeps counting")

-- Loop-forever survives a driven session: phases stay in period, items on screen.
for i = 1, B.count do
    if B.names[i] ~= "Life" then
        B.resetLevels()
        local st = B.reset(i, SEED)
        local ok, why = true, "ok"
        for n = 1, 12000 do
            B.setLevels(15, (n * 5) % 16, 15 - (n * 3) % 16, (n * 7) % 16, n % 16, 15, 0, (n * 11) % 16)
            B.update(i)
            if n % 1500 == 0 then
                local a, msg = accsOk(st)
                if not a then ok, why = false, msg end
                if not boundsOk(st, B.margin(i)) then ok, why = false, "left the screen" end
            end
        end
        A.truthy(ok, B.names[i] .. " still loops cleanly under music (" .. why .. ")")
    end
end
B.resetLevels()

return true
