-- Host tests for ui.lua: key repeat, wrapping, list window, grid movement,
-- scroll thumb. The draw functions are only checked for "no-ops under host".
local A = require("assert")
local UI = require("ui")

A.truthy(UI, "ui: require returns the module")
A.eq(rawget(_G, "UI"), UI, "ui: global and return value are the same table")

-- wrap / window / thumb --------------------------------------------------

A.eq(UI.wrap(1, -1, 5), 5, "ui: wrap below 1 goes to n")
A.eq(UI.wrap(5, 1, 5), 1, "ui: wrap above n goes to 1")
A.eq(UI.wrap(3, 1, 5), 4, "ui: wrap inside is a plain step")
A.eq(UI.wrap(1, 1, 1), 1, "ui: wrap in a one-item list stays")

A.eq(UI.window(1, 20, 8), 1, "ui: window pinned at the top")
A.eq(UI.window(4, 20, 8), 1, "ui: window still pinned while sel is in the top half")
A.eq(UI.window(10, 20, 8), 6, "ui: window keeps sel at visible/2")
A.eq(UI.window(20, 20, 8), 13, "ui: window pinned at the bottom")
A.eq(UI.window(3, 5, 8), 1, "ui: window with fewer items than rows")

local off, size = UI.thumb(100, 0, 10, 40)
A.eq(off, 0, "ui: thumb at top has offset 0")
A.eq(size, 25, "ui: thumb size is the visible share of the track")
off, size = UI.thumb(100, 30, 10, 40)
A.eq(off + size, 100, "ui: thumb at the bottom reaches the track end")
A.eq(select(2, UI.thumb(100, 0, 1, 1000)), 10, "ui: thumb has a minimum size")
A.eq(select(2, UI.thumb(100, 0, 10, 5)), 100, "ui: thumb fills the track when nothing scrolls")

A.eq(UI.plain("double_jump"), "double jump", "ui: plain swaps underscores")
A.eq(UI.plain("double_jump"), "double jump", "ui: plain is stable from the cache")

-- key repeat -------------------------------------------------------------

local rep = UI.repeater()
local steps = {}
for frame = 1, 20 do
    rep:feed("down", true)
    if rep:step("down") then steps[#steps + 1] = frame end
end
A.eq(steps[1], 1, "ui: repeater steps on the press frame")
A.eq(steps[2], 12, "ui: repeater waits 10 frames, first repeat on frame 12")
A.eq(steps[3], 15, "ui: repeater then steps every 3 frames")
A.eq(steps[4], 18, "ui: repeater keeps its rhythm")
A.eq(#steps, 4, "ui: nothing else stepped in 20 frames")

rep:feed("down", false)
A.falsy(rep:step("down"), "ui: release stops stepping")
rep:feed("down", true)
A.truthy(rep:step("down"), "ui: a new press steps at once")
A.falsy(rep:step("never_fed"), "ui: unknown key never steps")

local r2 = UI.repeater(4, 2)
local n2 = 0
for _ = 1, 9 do r2:feed("up", true); if r2:step("up") then n2 = n2 + 1 end end
A.eq(n2, 1 + 2, "ui: custom delay/every (press, frames 6 and 8)")

local r3 = UI.repeater()
r3:feed("up", true); r3:feed("down", true)
A.eq(r3:vertical(), -1, "ui: up wins when both step")
r3:feed("up", false)
r3:feed("down", true)
A.eq(r3:vertical(), 0, "ui: held key past press frame but before delay is 0")
r3:feed("left", true)
A.eq(r3:horizontal(), -1, "ui: horizontal reads left")
A.eq(rep.poll and rep:poll(), nil, "ui: poll is a no-op under host lua")

-- list ---------------------------------------------------------------------

local items = {}
for i = 1, 20 do items[i] = "item" .. i end
local l = UI.list{ items = items, x = 10, y = 30, w = 100, rowH = 16, visible = 8 }
A.eq(l.sel, 1, "ui: list starts on 1")
A.truthy(l:move(-1), "ui: move reports a step")
A.eq(l.sel, 20, "ui: list wraps up from the first item")
A.eq(l:first(), 13, "ui: window at the end shows the last rows")
l:move(1)
A.eq(l.sel, 1, "ui: list wraps down from the last item")
A.eq(l:first(), 1, "ui: window back at the top")
A.falsy(l:move(0), "ui: zero move is not a step")
for _ = 1, 9 do l:move(1) end
A.eq(l.sel, 10, "ui: nine steps down")
A.eq(l:first(), 6, "ui: window follows the selection")

local rv = UI.repeater()
rv:feed("down", true)
A.truthy(l:navigate(rv), "ui: navigate steps from the repeater")
A.eq(l.sel, 11, "ui: navigate moved down")
A.eq(l:draw(), 7, "ui: draw returns the first row and is a no-op on host")

l:setItems({ "a", "b" })
A.eq(l.sel, 2, "ui: setItems clamps the selection")
l.sel = 1
A.falsy(UI.list{ items = {} }:move(1), "ui: empty list does not move")

-- the highlight spring: converges, never overshoots, and snaps at the target
local sp = UI.spring(0, 3)
local prev, over = 0, false
for _ = 1, 60 do
    local v = sp:update(100)
    if v > 100.0001 or v < prev - 1e-9 then over = true end
    prev = v
end
A.falsy(over, "ui: spring rises monotonically without overshoot")
A.near(sp.value, 100, 0.5, "ui: spring converges")
sp:reset(5)
A.eq(sp.value, 5, "ui: spring reset")

-- grid ---------------------------------------------------------------------

local cells = {}
for i = 1, 20 do cells[i] = "c" .. i end            -- 3 cols: 7 rows, last has 2
local g = UI.grid{ cols = 3, visible = 3, items = cells }
A.eq(g:rows(), 7, "ui: grid row count")
A.truthy(g:move(1, 0), "ui: grid move reports a step")
A.eq(g.sel, 2, "ui: grid right")
g:move(1, 0); g:move(1, 0)
A.eq(g.sel, 1, "ui: grid right wraps within the row")
g:move(-1, 0)
A.eq(g.sel, 3, "ui: grid left wraps within the row")
g:move(0, 1)
A.eq(g.sel, 6, "ui: grid down")
g:move(0, -1); g:move(0, -1)
A.eq(g.sel, 20, "ui: grid up wraps from the first row to the last")
A.eq(g.top, 4, "ui: grid window followed to the last rows")
g.sel = 3; g.top = 0
g:move(0, -1)
A.eq(g.sel, 20, "ui: short last row clamps to its final cell")
g:move(0, 1)
A.eq(g.sel, 2, "ui: grid down wraps to the first row")
A.eq(g.top, 0, "ui: grid window back at the top")
for _ = 1, 3 do g:move(0, 1) end
A.eq(g.sel, 11, "ui: three rows down")
A.eq(g.top, 1, "ui: window scrolls one row past the bottom edge")
g:move(0, -1); g:move(0, -1); g:move(0, -1)
A.eq(g.top, 0, "ui: window scrolls back up with the selection")
A.falsy(g:move(0, 0), "ui: grid zero move is not a step")

g.sel, g.top = 5, 0
A.truthy(g:scroll(2), "ui: crank scroll reports a move")
A.eq(g.sel, 11, "ui: scroll by rows keeps the column")
g:scroll(100)
A.eq(g.sel, 20, "ui: scroll clamps at the last row without wrapping")
g:scroll(-100)
A.eq(g.sel, 2, "ui: scroll clamps at the first row")
A.eq(g.top, 0, "ui: window back at the top after scrolling up")

local rg = UI.repeater()
rg:feed("right", true)
g.sel = 1
A.truthy(g:navigate(rg), "ui: grid navigate steps from the repeater")
A.eq(g.sel, 2, "ui: grid navigate moved right")
A.falsy(UI.grid{ items = {} }:move(1, 1), "ui: empty grid does not move")
A.eq(UI.grid{ items = {} }:rows(), 0, "ui: empty grid has no rows")
g:draw(6, 28, 98, 14)

-- meters: the peak tick holds, then falls by `decay` a frame -----------------

local m = UI.meters{ decay = 0.5 }
A.eq(m:track(1, 10), 10, "ui: peak jumps to a louder level")
A.eq(m:track(1, 0), 9.5, "ui: peak falls by decay")
A.eq(m:track(1, 20), 20, "ui: peak follows a new maximum")
m:draw({ 3, 4 }, 4, 0, 0, 40, 120)
A.eq(m.peak[2], 4, "ui: draw tracks peaks on host without the SDK")
A.eq(m.peak[4], 0, "ui: missing levels count as 0")

-- draw helpers must be silent without the SDK
UI.panel(0, 0, 10, 10); UI.header("x", "y"); UI.footer("x")
UI.outlined("x", 0, 0); UI.scrollbar(0, 0, 4, 10, 0, 1, 2)
A.truthy(true, "ui: draw helpers are no-ops under host lua")

-- effects: pure animation state, stepped one frame at a time -----------------

A.eq(UI.stagger(0, 0, 2, 6), 0, "ui: stagger item 0 starts at 0")
A.near(UI.stagger(3, 0, 2, 6), 0.5, 1e-9, "ui: stagger halfway")
A.near(UI.stagger(3, 1, 2, 6), 1 / 6, 1e-9, "ui: stagger item 1 starts 2 frames late")
A.eq(UI.stagger(10, 1, 2, 6), 1, "ui: stagger finishes at 1")
A.eq(UI.stagger(-5, 0, 2, 6), 0, "ui: negative time holds at 0 (entrance delay)")
A.eq(UI.stagger(0, 3, 2, 0), 1, "ui: zero duration is instantly done")
A.eq(UI.popScale(0, 10), 0, "ui: pop starts at 0")
A.eq(UI.popScale(10, 10), 1, "ui: pop ends at 1")
local peak = 0
for t = 1, 9 do peak = math.max(peak, UI.popScale(t, 10)) end
A.truthy(peak > 1 and peak < 1.2, "ui: pop overshoots a little")

local wb = UI.wobble()
wb:kick(4)
local sawNeg, last = false, nil
for _ = 1, 80 do
    last = wb:update()
    if last < 0 then sawNeg = true end
end
A.truthy(sawNeg, "ui: wobble swings past rest")
A.eq(last, 0, "ui: wobble settles exactly at 0")

local function frames(obj, n) for _ = 1, n do obj:update() end end
local fl = UI.list{ items = items, x = 10, y = 30, w = 100, rowH = 16, visible = 8 }
A.eq(fl.fillT, fl.fx.fill, "ui: a fresh list is at rest")
A.eq(UI.stagger(fl.enterT, 5, fl.fx.stagger, fl.fx.enterDur), 1, "ui: no entrance until :enter()")
fl:move(1)
A.eq(fl.fillT, 0, "ui: a new selection restarts the fill")
A.eq(fl.nudgeW.pos, -fl.fx.nudge, "ui: nudge starts behind and swings in")
A.eq(fl.prev, 1, "ui: previous row remembered")
A.eq(fl.prevOff, fl.fx.nudge, "ui: previous row eases back from the nudge")
A.eq(fl.bumpW.vel, 0, "ui: a plain step does not bump")
frames(fl, 3)
A.eq(fl.fillT, 3, "ui: fill progresses a frame per update")
local over = false
for _ = 1, 40 do fl:update(); if fl.nudgeW.pos > 0 then over = true end end
A.truthy(over, "ui: nudge overshoots")
A.eq(fl.nudgeW.pos, 0, "ui: nudge settles")
A.eq(fl.prevOff, 0, "ui: previous row has eased back")

local wl = UI.list{ items = items, visible = 8 }
wl:move(-1)
A.eq(wl.sel, 20, "ui: wrap up")
A.eq(wl.bumpW.vel, wl.fx.bump, "ui: wrapping up kicks the list")
wl:update()
A.truthy(wl.bumpW.pos ~= 0, "ui: the bump moves the list")
frames(wl, 60)
A.eq(wl.bumpW.pos, 0, "ui: the bump settles")
wl:move(1)
A.eq(wl.bumpW.vel, -wl.fx.bump, "ui: wrapping down kicks the other way")
local nb = UI.list{ items = items, bump = 0 }
nb:move(-1)
A.eq(nb.bumpW.vel, 0, "ui: bump = 0 turns the bump off")
local nf = UI.list{ items = items, fill = 0, nudge = 0 }
nf:move(1)
A.eq(nf.nudgeW.pos, 0, "ui: nudge = 0 turns the nudge off")

local cl = UI.list{ items = items, flash = 4 }
cl:confirm()
A.eq(cl.flashT, 4, "ui: confirm starts the flash")
frames(cl, 4)
A.eq(cl.flashT, 0, "ui: flash ends after its frames")

local el = UI.list{ items = items, stagger = 2, enterDur = 6 }
el:enter(3)
A.eq(el.enterT, -3, "ui: enter(delay) holds the first row back")
A.eq(UI.stagger(el.enterT, 0, 2, 6), 0, "ui: nothing visible during the delay")
frames(el, 3 + 7)
A.eq(el.enterT, 7, "ui: entrance clock runs on update")
A.near(UI.stagger(el.enterT, 2, 2, 6), 0.5, 1e-9, "ui: row 2 is half in 7 frames after the start")
A.eq(UI.stagger(el.enterT, 0, 2, 6), 1, "ui: row 0 is already in")
A.eq(UI.stagger(el.enterT, 4, 2, 6), 0, "ui: row 4 has not started")

-- the list's scroll bar thumb follows the window through a spring
local sl = UI.list{ items = items, visible = 8, scrollbar = true }
sl.sel = 20
frames(sl, 60)
A.near(sl.sbSpring.value, 12, 0.1, "ui: scroll bar spring reaches the last window")

-- grid effects
local eg = UI.grid{ cols = 3, visible = 3, items = cells }
eg:move(0, -1)
A.eq(eg.sel, 19, "ui: grid wrap up")
A.eq(eg.bumpW.vel, eg.fx.bump, "ui: grid wrap bumps")
A.eq(eg.fillT, 0, "ui: grid fill restarts on a move")
local eg2 = UI.grid{ cols = 3, visible = 3, items = cells }
A.falsy(eg2:scroll(-3), "ui: scrolling past the top does not move")
A.eq(eg2.sel, 1, "ui: and the selection stays")
A.eq(eg2.bumpW.vel, -eg2.fx.bump * -1, "ui: but it bumps against the edge")
A.truthy(eg2:scroll(2), "ui: scrolling inside the grid moves")
eg2:confirm()
A.eq(eg2.flashT, eg2.fx.flash, "ui: grid confirm flashes")
eg2:enter(); frames(eg2, 2)
A.eq(eg2.enterT, 2, "ui: grid entrance clock")
eg2:draw(6, 28, 98, 14)
A.near(eg2.spring.value, 0, 0.5, "ui: grid scroll spring starts at the top")

-- popping a panel is a no-op without the SDK
UI.panel(0, 0, 100, 50, 0.5)

-- a selected cell wider than its column grows to fit, and slides left at the edge
local bx, bw = UI.cellBar(10, 96, 60, 300)
A.eq(bx, 10, "ui: cellBar keeps a cell that fits")
A.eq(bw, 96, "ui: cellBar keeps the cell width when the text fits")
bx, bw = UI.cellBar(10, 96, 130, 300)
A.eq(bw, 130, "ui: cellBar widens to the text")
A.eq(bx, 10, "ui: cellBar keeps the left edge when there is room")
bx, bw = UI.cellBar(200, 96, 130, 300)
A.eq(bx, 170, "ui: cellBar slides left to stay inside the grid")
A.eq(bx + bw, 300, "ui: cellBar ends at the grid edge")
-- the selected row never leaves the window while the scroll spring trails
local big = {}
for i = 1, 90 do big[i] = "n" .. i end
local sg = UI.grid{ cols = 3, visible = 5, items = big }      -- 30 rows
local inside = true
for step = 1, 60 do
    sg:move(0, 1)
    sg:update()
    local row = (sg.sel - 1) // 3
    if sg.spring.value < row - 4 - 1e-9 or sg.spring.value > row + 1e-9 then inside = false end
end
A.truthy(inside, "ui: grid keeps the selected row in the window while scrolling")
sg:scroll(100)                                                -- a big jump at once
sg:update()
A.truthy(sg.spring.value >= (sg.sel - 1) // 3 - 4 - 1e-9, "ui: grid clamps the spring after a jump")
sg.sel = 1; sg:follow(); sg:update()
A.truthy(sg.spring.value <= 0 + 1e-9 + 0, "ui: grid clamps the spring going back up") 

-- the list bar stays inside the list area when a wrap sends it across
local bl = UI.list{ items = items, x = 0, y = 30, w = 100, rowH = 16, visible = 8 }
bl:update()
local okBar = true
bl:move(-1)
for _ = 1, 30 do
    bl:update()
    if bl.by < 30 - 1 or bl.by > 30 + 7 * 16 + 1 then okBar = false end
end
A.truthy(okBar, "ui: list bar stays within the visible rows during a wrap")