-- Host tests for credits.lua: layout, the timeline and the clock. The default
-- host metrics (7 px a letter, 15 px a line) make every position below plain
-- arithmetic. The device shell is only checked for "no-ops, not crashes".
local A = require("assert")
local Credits = require("credits")

local W, H = Credits.SCREEN_W, Credits.SCREEN_H
local GAPS = Credits.GAPS
local floor = math.floor

-- ---------------------------------------------------------------------------
-- module contract (CONVENTIONS rule 1)
-- ---------------------------------------------------------------------------

A.truthy(Credits, "credits: require returns the module")
A.eq(rawget(_G, "Credits"), Credits, "credits: global and return value are the same table")
A.falsy(Credits.load(), "credits: load() reports not-ready under host lua")

-- ---------------------------------------------------------------------------
-- text helpers
-- ---------------------------------------------------------------------------

local function w7(s) return 7 * #s end
local lines = Credits.wrap("the quick brown fox jumps", 70, w7)
A.eq(#lines, 3, "credits: wrap breaks at the width")
A.eq(lines[1], "the quick", "credits: wrap keeps whole words")
A.eq(lines[3], "jumps", "credits: wrap keeps the tail")

lines = Credits.wrap("a supercalifragilistic b", 70, w7)
A.eq(lines[2], "supercalifragilistic", "credits: an over-wide word gets its own line, unsplit")
A.eq(#lines, 3, "credits: ...and the words around it keep theirs")

lines = Credits.wrap("one\n\ntwo", 200, w7)
A.eq(#lines, 3, "credits: newlines are paragraphs")
A.eq(lines[2], "", "credits: a blank line survives")

A.eq(Credits.ulen("Женя"), 4, "credits: lengths count characters, not bytes")
A.eq(Credits.uprefix("Женя", 2), "Же", "credits: a typed prefix never splits a character")
A.eq(Credits.uprefix("abc", 9), "abc", "credits: a prefix longer than the text is the text")

-- ---------------------------------------------------------------------------
-- layout: one roll, film-style split
-- ---------------------------------------------------------------------------

local plan = Credits.layout({
    { heading = "Music" },
    { role = "Composer", name = "Ann" },
}, { speed = 2 })
local seg = plan.segments[1]
A.eq(#plan.segments, 1, "credits: entries without a card are one roll")
A.eq(seg.kind, "roll", "credits: ...of kind roll")
A.eq(#seg.rows, 2, "credits: a heading and a role are two rows")
A.eq(seg.rows[2].y, 15 + GAPS.role, "credits: rows stack with the kind's gap")

local role, name = seg.rows[2].parts[1], seg.rows[2].parts[2]
A.eq(role.x + role.w, W / 2 - 8, "credits: split: the role ends half a gutter left of centre")
A.eq(name.x, W / 2 + 8, "credits: split: the name starts half a gutter right of it")
A.eq(seg.height, 34, "credits: roll height")
A.near(plan.duration, (H + 34) / 2, 1e-9, "credits: a roll lasts (screen + content) / speed")
A.eq(plan.skipTo, plan.duration, "credits: with no card, skip goes to the end")

local rules = seg.rows[1].rules
A.truthy(rules, "credits: a centred heading gets side rules")
A.truthy(rules.left < seg.rows[1].parts[1].x and rules.right > seg.rows[1].parts[1].x,
    "credits: the rules sit either side of the heading")
A.eq(seg.rows[1].reveal, "type", "credits: headings type in by default")
A.eq(seg.rows[2].reveal, "slide", "credits: roles slide in by default")
A.eq(role.side, -1, "credits: the role slides in from the left")
A.eq(name.side, 1, "credits: the name slides in from the right")

local multi = Credits.layout({ { role = "Art", names = { "Ann", "Bo", "Cy" } } }).segments[1].rows
A.eq(#multi, 3, "credits: one row per name")
A.eq(#multi[1].parts, 2, "credits: the first row carries the role")
A.eq(#multi[2].parts, 1, "credits: later rows are the name alone")
A.eq(multi[2].y, 15 + 2, "credits: names of one role sit tight")

local long = string.rep("x", 40)    -- 280 px: cannot fit the left half
local stacked = Credits.layout({ { role = long, name = "Ann" } }).segments[1].rows
A.eq(#stacked, 2, "credits: an over-wide role falls back to stacking")
A.eq(stacked[1].parts[1].x, (W - 280) // 2, "credits: ...centred")
A.eq(stacked[2].parts[1].style, "name", "credits: ...name under role")

local leader = Credits.layout({ { role = "Code", name = "Zhenya" } }, { style = "leader" }).segments[1].rows[1]
A.eq(leader.parts[1].x, 24, "credits: leader: role at the margin")
A.eq(leader.parts[2].x + leader.parts[2].w, W - 24, "credits: leader: name flush right")
A.truthy(leader.dots and leader.dots.x1 > 24 + 28 and leader.dots.x2 < leader.parts[2].x,
    "credits: leader: the dots run between them")

-- ---------------------------------------------------------------------------
-- layout: grids, paragraphs, images, titles
-- ---------------------------------------------------------------------------

local grid = Credits.layout({ { names = { "Ann", "Bob", "Cyd", "Dee", "Eve" } } }).segments[1].rows
A.eq(#grid, 2, "credits: five short names fill four columns, then one")
A.eq(#grid[1].parts, 4, "credits: auto columns cap at four")
local lone = grid[2].parts[1]
A.near(lone.x + lone.w / 2, W / 2, 1, "credits: a short last row is centred, not left-packed")
A.eq(#Credits.layout({ { names = { "a", "b", "c", "d", "e" }, columns = 2 } }).segments[1].rows, 3,
    "credits: explicit columns")

local para = Credits.layout({ { text = string.rep("word ", 30) } }).segments[1].rows
local fitsInside = true
for _, r in ipairs(para) do
    local p = r.parts[1]
    if p.x < 24 or p.x + p.w > W - 24 then fitsInside = false end
end
A.truthy(#para > 1, "credits: a long paragraph wraps")
A.truthy(fitsInside, "credits: every wrapped line stays inside the margins")

local logo = Credits.layout({ { image = "logo", w = 64, h = 40 } }).segments[1].rows[1]
A.truthy(logo.image, "credits: an image is an image row")
A.eq(logo.h, 40, "credits: image rows take the image's height")
A.eq(logo.x, (W - 64) // 2, "credits: images centre")

local title = Credits.layout({ { title = "AB", sub = "cd" } }).segments[1].rows
A.eq(title[1].h, 30, "credits: titles are pixel-doubled by default")
A.eq(title[1].parts[1].w, 28, "credits: ...in width too")
A.eq(#title, 2, "credits: a subtitle is its own row")
A.eq(Credits.layout({ { title = "AB" } }, { fonts = { title = {} } }).segments[1].rows[1].h, 15,
    "credits: a title font of your own is not doubled")

local script = { "hello", { name = "A" } }
Credits.layout(script)
A.eq(script[1], "hello", "credits: layout does not rewrite the script it is given")

A.eq(Credits.layout({ { name = "A" } }, { reveal = "type" }).segments[1].rows[1].reveal, "type",
    "credits: opts.reveal sets the roll's default")
A.eq(Credits.layout({ { name = "A", reveal = "none" } }, { reveal = "type" }).segments[1].rows[1].reveal,
    "none", "credits: an entry's own reveal wins")

-- ---------------------------------------------------------------------------
-- the timeline: holds, the final stop, fitting the music
-- ---------------------------------------------------------------------------

local held = Credits.layout({ { name = "A" }, { name = "B", hold = 30 }, { name = "C" } })
local hs = held.segments[1]
A.eq(hs.height, 53, "credits: three names")
A.near(held.duration, H + 53 + 30, 1e-9, "credits: a hold adds its frames")
-- B spans 19..34, so it is centred when the content top is at 120 - 26.5.
local centred = H / 2 - 26.5
A.near(Credits._scrollAt(hs, 0), H, 1e-9, "credits: a roll starts just below the screen")
A.near(Credits._scrollAt(hs, H - centred), centred, 1e-9, "credits: the held row arrives at the centre")
A.near(Credits._scrollAt(hs, H - centred + 15), centred, 1e-9, "credits: ...and stays there")
A.near(Credits._scrollAt(hs, H - centred + 30), centred, 1e-9, "credits: ...for exactly its hold")
A.near(Credits._scrollAt(hs, H - centred + 31), centred - 1, 1e-9, "credits: then moves on")
A.near(Credits._scrollAt(hs, held.duration), -53, 1e-9, "credits: a roll ends just above the screen")

local stay = Credits.layout({ { name = "A" }, { image = "logo", w = 64, h = 40, hold = true } })
A.near(Credits._scrollAt(stay.segments[1], stay.duration), H / 2 - (31 + 71) / 2, 1e-9,
    "credits: hold = true ends with that entry centred")

local ok, err = pcall(Credits.layout, { { name = "A", hold = true }, { name = "B" } })
A.falsy(ok, "credits: nothing may follow hold = true")
A.truthy(err and err:find("nothing may follow"), "credits: ...and the error says so")

local song = Credits.layout({ { name = "A" }, { name = "B", hold = 30 }, { name = "C" } }, { fit = 600 })
A.near(song.duration, 600, 1e-6, "credits: fit lands the end on the frame asked for")
A.near(song.speed, (H + 53) / 570, 1e-9, "credits: ...by solving the speed around the holds")
ok, err = pcall(Credits.layout, { { name = "A", hold = 90 } }, { fit = 60 })
A.falsy(ok, "credits: fit shorter than the holds is refused")
A.truthy(err and err:find("holds and cards alone"), "credits: ...with the reason")

-- ---------------------------------------------------------------------------
-- cards
-- ---------------------------------------------------------------------------

local cards = Credits.layout({
    { name = "Roll" },
    { card = "THE END", hold = 50 },
    { card = { { heading = "Thanks" }, { name = "for playing" } } },
}, { card = { fadeIn = 10, fadeOut = 8, stagger = 4 } })
local c2, c3 = cards.segments[2], cards.segments[3]
A.eq(#cards.segments, 3, "credits: a roll and two cards")
A.eq(c2.kind, "card", "credits: card segments")
A.near(c2.t1 - c2.t0, 10 + 50 + 8, 1e-9, "credits: a card is fade in + hold + fade out")
A.eq(c2.top, (H - 30) // 2, "credits: a card centres its content")
A.eq(c2.rows[1].reveal, "fade", "credits: card rows dissolve by default")
A.truthy(c3.stay, "credits: the last card stays")
A.near(c3.t1 - c3.t0, 4 + 10, 1e-9, "credits: ...so it ends once its last row is in")
A.eq(cards.skipTo, c3.t0, "credits: skip goes to the last card")
A.near(cards.duration, c3.t1, 1e-9, "credits: the last card's arrival is the end")

local r = c2.rows[1]
local function alphaAt(t) return Credits._cardAlpha(c2, r, t, Credits._cardP(c2, r, t)) end
A.eq(alphaAt(c2.t0), 0, "credits: a card starts invisible")
A.near(alphaAt(c2.t0 + 5), 0.5, 1e-9, "credits: ...dissolves in")
A.eq(alphaAt(c2.t0 + 30), 1, "credits: ...holds")
A.near(alphaAt(c2.t1 - 4), 0.5, 1e-9, "credits: ...dissolves out")
A.eq(alphaAt(c2.t1), 0, "credits: ...and is gone at its end")

local typed = Credits.layout({ { card = { { heading = "Typewriter", reveal = "type" }, { name = "next" } } } })
local tr = typed.segments[1].rows
A.eq(tr[2].ct0, tr[1].dur, "credits: a typing row holds the next one back until it finishes")

ok = pcall(Credits.layout, { { card = "A", hold = true }, { card = "B" } })
A.falsy(ok, "credits: only the last card can stay")

-- ---------------------------------------------------------------------------
-- the clock: cues, rewinds, skip, the end
-- ---------------------------------------------------------------------------

local fired = {}
local roll = Credits.new({
    { name = "A", on = function() fired[#fired + 1] = "A" end },
    { name = "B" },
    { card = "END", on = function() fired[#fired + 1] = "END" end },
}, { speed = 1 })
A.eq(roll.t, 0, "credits: a new roll starts at frame 0")
A.falsy(roll.done, "credits: ...not done")
-- A spans 0..15: centred at a scroll of 112.5, i.e. frame 127.5
for _ = 1, 127 do roll:advance(1) end
A.eq(#fired, 0, "credits: a cue waits for its row to reach the centre")
roll:advance(1)
A.eq(fired[1], "A", "credits: ...and fires as it does")
roll:advance(1)
A.eq(#fired, 1, "credits: once")
roll:advance(-20)
A.eq(#fired, 1, "credits: rewinding fires nothing")
roll:advance(30)
A.eq(#fired, 2, "credits: playing through again re-fires it")
A.near(roll:progress(), roll.t / roll.duration, 1e-12, "credits: progress")
A.truthy(roll:scroll(), "credits: scroll() reports the roll's position")

roll:skip()
A.eq(roll.t, roll.skipTo, "credits: skip lands on the last card")
A.eq(#fired, 2, "credits: skip itself fires nothing")
roll:advance(1)
A.eq(fired[3], "END", "credits: ...but the card it lands on still cues")
A.eq(roll:scroll(), nil, "credits: no scroll during a card")
roll:seek(0)
roll:seek(roll.skipTo + 2)
A.eq(#fired, 3, "credits: seek never fires cues")

local first = 0
local opener = Credits.new({ { card = "HELLO", hold = 10, on = function() first = first + 1 end }, { name = "x" } })
opener:advance(1)
A.eq(first, 1, "credits: a cue at frame 0 fires on the first advance")
opener:advance(1)
A.eq(first, 1, "credits: ...once")
opener:restart()
opener:advance(1)
A.eq(first, 2, "credits: restart re-arms it")

local ends = 0
local short = Credits.new({ { name = "A" } }, { speed = 10 }):onEnd(function() ends = ends + 1 end)
for _ = 1, 100 do short:advance(1) end
A.truthy(short.done, "credits: done at the end")
A.eq(ends, 1, "credits: onEnd fires once")
A.eq(short.t, short.duration, "credits: the clock stops at the end")
short:advance(-5)
A.falsy(short.done, "credits: rewinding from the end un-dones it")
short:advance(10)
A.eq(ends, 2, "credits: reaching the end again fires again")

local ends2 = 0
local skipper = Credits.new({ { name = "A" }, { name = "B" } }):onEnd(function() ends2 = ends2 + 1 end)
skipper:skip()
A.eq(skipper.t, skipper.duration, "credits: with no card, skip goes to the end")
skipper:advance(1)
A.eq(ends2, 1, "credits: ...and the end still fires")

local clicks = 0
local typist = Credits.new({ { heading = "Typing" }, { space = 400 } },
    { speed = 1, onType = function() clicks = clicks + 1 end })
for _ = 1, 60 do typist:advance(1) end
A.truthy(clicks > 0, "credits: onType fires while a heading types in")
local before = clicks
typist:advance(-10)
A.eq(clicks, before, "credits: no typing sound while rewinding")

-- ---------------------------------------------------------------------------
-- edges: rows dither out through the top and bottom
-- ---------------------------------------------------------------------------

A.eq(Credits._edgeAlpha(plan, H / 2 - 7, 14), 1, "credits: full ink mid-screen")
A.eq(Credits._edgeAlpha(plan, H - 7, 14), 0, "credits: none with the centre on the edge")
A.near(Credits._edgeAlpha(plan, H - 19, 14), 0.5, 1e-9, "credits: half way through the fade band")
A.eq(Credits._edgeAlpha({ fade = 0 }, H - 7, 14), 1, "credits: fade = 0 is a hard cut")

-- ---------------------------------------------------------------------------
-- bad scripts fail at new(), with a reason
-- ---------------------------------------------------------------------------

local function refuses(script, opts, needle, msg)
    local good, e = pcall(Credits.layout, script, opts)
    A.truthy(not good and e and e:find(needle, 1, true), msg)
end
refuses({}, nil, "empty", "credits: an empty script is refused")
refuses({ { bogus = 1 } }, nil, "none of", "credits: an unknown entry is refused")
refuses({ { name = "A", reveal = "spin" } }, nil, "no reveal", "credits: an unknown reveal is refused")
refuses({ { name = "A" } }, { style = "fancy" }, "no style", "credits: an unknown style is refused")
refuses({ { card = { { card = "x" } } } }, nil, "cannot hold a card", "credits: cards do not nest")
refuses({ { card = "x", hold = "long" } }, nil, "frame count", "credits: a card's hold is checked")

-- ---------------------------------------------------------------------------
-- device shell no-ops under host lua
-- ---------------------------------------------------------------------------

roll:draw()
roll:update()
A.truthy(true, "credits: draw and update survive without the SDK")
