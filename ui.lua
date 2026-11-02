-- ui.lua -- menu plumbing for Playdate games: key repeat, a scrolling list
-- with a springy highlight, a scrolling grid, panels, header/footer bars,
-- scroll bar, level meters and outlined text.
--
-- Everything here was pulled out of the demo's menus, so it is the set of
-- things a game's menus actually needed, not a widget toolkit. There is no
-- layout engine and no event system: you own the state, call move/navigate
-- from your update, and draw from your draw.
--
-- The input and scroll maths (Repeater, UI.wrap, UI.window, UI.thumb, List,
-- Grid) is pure and has no SDK call, so it is what test/ui_test.lua pins. The
-- draw functions are the thin device shell; under host lua they return early.
--
-- Nothing here allocates per frame once the objects are built. Two traps that
-- would: a `label` function that concatenates strings (build the labels once
-- and pass them as items), and name.gsub on every frame (UI.plain caches).
--
-- Independent on purpose: the highlight spring is a 20-line copy of the
-- critically damped one in tween.lua, so this file imports nothing.

UI = UI or {}

local pd  = rawget(_G, "playdate")
local gfx = pd and pd.graphics

local floor <const> = math.floor
local min <const>   = math.min
local max <const>   = math.max

local W <const> = 400
local H <const> = 240

-- Fonts the draw helpers use. Set these once after loading your fonts;
-- header uses `title` and `body`, footer and list use `body`. A nil font
-- leaves whatever font is current.
UI.font = UI.font or { title = nil, body = nil }

-- ---------------------------------------------------------------------------
-- pure: wrap, window, scroll thumb
-- ---------------------------------------------------------------------------

-- Step i (1-based) by d within 1..n, wrapping at both ends.
function UI.wrap(i, d, n)
    return (i - 1 + d) % n + 1
end

-- First visible index of a list of n items showing `visible` rows with item
-- `sel` kept near the middle and the window pinned at both ends.
function UI.window(sel, n, visible)
    return max(1, min(sel - floor(visible / 2), n - visible + 1))
end

-- Scroll bar thumb for a view onto `total` rows of which `visible` show,
-- scrolled to row `top` (0-based). Returns offset and size in a track of h px.
function UI.thumb(h, top, visible, total)
    if total <= visible then return 0, h end
    local size = min(h, max(10, floor(h * visible / total)))
    return floor((h - size) * top / (total - visible)), size
end

-- Item names come from data ("double_jump") but Playdate text markup treats
-- _ as italic, so show them with spaces. Cached: gsub allocates, and this is
-- called from draw.
local plainCache = {}
function UI.plain(name)
    local s = plainCache[name]
    if not s then
        s = (name:gsub("_", " "))
        plainCache[name] = s
    end
    return s
end

-- ---------------------------------------------------------------------------
-- pure: spring (for the highlight)
-- ---------------------------------------------------------------------------

-- Critically damped, dt of one frame; same maths as Tween.newSpring. Never
-- overshoots, which is what a menu bar needs.
local Spring = {}
Spring.__index = Spring

function UI.spring(value, smoothTime)
    return setmetatable({ value = value or 0, velocity = 0, smoothTime = smoothTime or 3 }, Spring)
end

function Spring:reset(value)
    self.value = value or 0
    self.velocity = 0
    return self
end

function Spring:update(target)
    local omega = 2 / max(self.smoothTime, 1e-4)
    local expf = 1 / (1 + omega + 0.48 * omega * omega + 0.235 * omega * omega * omega)
    local change = self.value - target
    local temp = (self.velocity + omega * change) * 1
    self.velocity = (self.velocity - omega * temp) * expf
    local out = target + (change + temp) * expf
    -- A spring can step past the target on a big change; snap instead of
    -- ticking backwards.
    if (target - self.value > 0) == (out > target) then
        out = target
        self.velocity = 0
    end
    self.value = out
    return out
end

-- ---------------------------------------------------------------------------
-- pure: key repeat
-- ---------------------------------------------------------------------------

-- A press steps once; held past `delay` frames it steps every `every` frames.
-- Feed it every frame (feed, or poll on device), then ask step(key).
local Repeater = {}
Repeater.__index = Repeater

local DPAD <const> = { "up", "down", "left", "right" }

function UI.repeater(delay, every)
    return setmetatable({ delay = delay or 10, every = every or 3, held = {}, keys = nil }, Repeater)
end

-- Record whether `key` (any name) is down this frame.
function Repeater:feed(key, down)
    local held = self.held
    held[key] = down and (held[key] or 0) + 1 or 0
end

-- Read the d-pad from the SDK. No-op under host lua.
function Repeater:poll()
    if not pd then return end
    local keys = self.keys
    if not keys then
        keys = { up = pd.kButtonUp, down = pd.kButtonDown, left = pd.kButtonLeft, right = pd.kButtonRight }
        self.keys = keys
    end
    for i = 1, 4 do
        local name = DPAD[i]
        self:feed(name, pd.buttonIsPressed(keys[name]))
    end
end

-- True on the frame the key goes down and on each repeat while held.
function Repeater:step(key)
    local n = self.held[key]
    if not n or n == 0 then return false end
    return n == 1 or (n > self.delay and n % self.every == 0)
end

-- -1, 0 or 1 from a pair of keys; the first wins if both step.
function Repeater:axis(neg, pos)
    if self:step(neg) then return -1 end
    if self:step(pos) then return 1 end
    return 0
end

function Repeater:vertical() return self:axis("up", "down") end
function Repeater:horizontal() return self:axis("left", "right") end

-- ---------------------------------------------------------------------------
-- pure: easing and animation state shared by list and grid
-- ---------------------------------------------------------------------------

local abs <const> = math.abs

-- Fast start, soft landing; p in 0..1.
local function easeOut(p)
    local q = 1 - p
    return 1 - q * q * q
end
UI.easeOut = easeOut

-- Progress 0..1 of item i (0-based) in a staggered entrance: item i starts
-- `delay` frames after item i-1 and takes `dur` frames. t is frames since the
-- entrance began; negative t holds everything at 0.
function UI.stagger(t, i, delay, dur)
    if dur <= 0 then return 1 end
    local p = (t - i * delay) / dur
    return p <= 0 and 0 or (p >= 1 and 1 or p)
end

-- Scale for a pop-open: 0 until t > 0, overshoots about 10% past 1 on the
-- way, 1 from t = dur on. Feed it to UI.panel's `scale`.
function UI.popScale(t, dur)
    if t <= 0 then return 0 end
    if t >= dur then return 1 end
    local p = t / dur - 1
    return 1 + 2.70158 * p * p * p + 1.70158 * p * p
end

-- A damped oscillator for offsets that should overshoot and settle. pos is
-- the offset from rest, kick(v) adds velocity. One call to update is one
-- frame; it lands exactly on 0 so a resting list costs nothing.
local Wobble = {}
Wobble.__index = Wobble

function UI.wobble(k, damp)
    return setmetatable({ pos = 0, vel = 0, k = k or 0.3, damp = damp or 0.7 }, Wobble)
end

function Wobble:kick(v) self.vel = self.vel + v end

function Wobble:update()
    if self.pos == 0 and self.vel == 0 then return 0 end
    self.vel = (self.vel - self.pos * self.k) * self.damp
    self.pos = self.pos + self.vel
    if abs(self.pos) < 0.05 and abs(self.vel) < 0.05 then self.pos, self.vel = 0, 0 end
    return self.pos
end

-- Effect settings shared by UI.list and UI.grid. Every one can be passed in
-- the constructor options; 0 turns that effect off.
--   fill      frames for the highlight to grow in on a new item (from 30%
--             of its width, from the left)
--   nudge     px the selected row is pushed right; it overshoots then settles
--   bump      px kick of the whole list when the selection wraps or hits the
--             end
--   flash     frames the row blinks inverted after :confirm()
--   stagger   frames between rows starting their entrance (:enter())
--   slide     px each row slides in from the left during the entrance
--   enterDur  frames each row takes to slide in
local FX = { fill = 6, nudge = 4, bump = 4, flash = 8, stagger = 2, slide = 24, enterDur = 6 }

local function fxInit(self, opts)
    local fx = {}
    for k, v in pairs(FX) do
        local o = opts[k]
        if o == nil then o = v end
        fx[k] = o
    end
    self.fx = fx
    self.fillT, self.flashT, self.enterT = fx.fill, 0, 1e9   -- all at rest
    self.prev, self.prevOff = 0, 0
    self.nudgeW, self.bumpW = UI.wobble(), UI.wobble()
end

-- The selection moved from `old`. wrapDir is +1/-1 when it wrapped (bumps).
local function fxSelect(self, old, wrapDir)
    local fx, w = self.fx, self.nudgeW
    self.prev, self.prevOff = old, fx.nudge + w.pos
    self.fillT = 0
    w.pos, w.vel = -fx.nudge, 0
    if wrapDir ~= 0 and fx.bump > 0 then self.bumpW:kick(-wrapDir * fx.bump) end
end

local function fxUpdate(self)
    self.fillT = self.fillT + 1
    self.enterT = self.enterT + 1
    self.nudgeW:update()
    self.bumpW:update()
    local off = self.prevOff
    if off ~= 0 then
        off = off * 0.6
        self.prevOff = abs(off) < 0.3 and 0 or off
    end
    if self.flashT > 0 then self.flashT = self.flashT - 1 end
end

-- Horizontal offset of item i from the nudge (selected item) or its decay
-- (the one just deselected).
local function fxOffset(self, i)
    if i == self.sel then return self.fx.nudge + self.nudgeW.pos end
    if i == self.prev then return self.prevOff end
    return 0
end

-- Width fraction of the highlight.
local function fxFill(self)
    local f = self.fx.fill
    if f <= 0 or self.fillT >= f then return 1 end
    return 0.3 + 0.7 * easeOut(self.fillT / f)
end

-- Entrance progress of the item at 0-based visible position ri.
local function fxEnter(self, ri)
    local fx = self.fx
    return UI.stagger(self.enterT, ri, fx.stagger, fx.enterDur)
end

local function fxSlide(self, p)
    return -floor((1 - easeOut(p)) * self.fx.slide)
end

-- Row blinks between inverted and plain every 2 frames while flashing.
local function fxFlashing(self)
    return self.flashT > 0 and (self.flashT // 2) % 2 == 0
end

-- ---------------------------------------------------------------------------
-- pure core + draw: list
-- ---------------------------------------------------------------------------

local List = {}
List.__index = List

-- opts: items, x, y, w, rowH, visible (required for draw); label(item, i)
-- (optional, must not allocate if you can help it); smooth (spring frames,
-- default 3); sel (default 1); scrollbar (draw a spring-following bar to the
-- right when items overflow, default false); and the effect settings above.
function UI.list(opts)
    local l = setmetatable({}, List)
    l.items = opts.items or {}
    l.x, l.y, l.w = opts.x or 0, opts.y or 0, opts.w or 100
    l.rowH, l.visible = opts.rowH or 16, opts.visible or 8
    l.label = opts.label
    l.sel = opts.sel or 1
    l.scrollbar = opts.scrollbar or false
    l.spring = UI.spring(0, opts.smooth or 3)
    l.sbSpring = UI.spring(0, 4)
    l.by = 0
    fxInit(l, opts)
    return l
end

function List:setItems(items)
    self.items = items
    self.sel = min(self.sel, max(1, #items))
end

-- Move the selection by d, wrapping. Returns true if d was not zero. Wrapping
-- past either end kicks the whole list (the bump effect).
function List:move(d)
    local n = #self.items
    if d == 0 or n == 0 then return false end
    local old = self.sel
    local new = UI.wrap(old, d, n)
    self.sel = new
    if new ~= old then
        local wrapped = (d > 0 and new < old) or (d < 0 and new > old)
        fxSelect(self, old, wrapped and (d > 0 and 1 or -1) or 0)
    end
    return true
end

-- Jump to item i (clamped) with the highlight and nudge effects, no bump.
function List:select(i)
    i = max(1, min(#self.items, i))
    local old = self.sel
    self.sel = i
    if i ~= old then fxSelect(self, old, 0) end
end

-- Up/down from a repeater. Returns true if the selection stepped.
function List:navigate(rep)
    return self:move(rep:vertical())
end

-- The row was chosen: blink it inverted and give it a kick.
function List:confirm()
    local fx = self.fx
    self.flashT = fx.flash
    if fx.flash > 0 then self.nudgeW:kick(3) end
end

-- Start the entrance: rows slide in one after another, the first after
-- `delay` frames (default 0). The clock runs while the list is drawn.
function List:enter(delay)
    self.enterT = -(delay or 0)
    self.fillT = self.fx.fill
end

-- Index of the first visible row.
function List:first()
    return UI.window(self.sel, #self.items, self.visible)
end

-- Advance every animation one frame. draw() calls this, so only call it
-- yourself when you do not draw (tests, hidden lists).
function List:update()
    fxUpdate(self)
    local first = self:first()
    -- The bar glides, but never outside the rows (it would otherwise start
    -- from y = 0 on a fresh list).
    local sp = self.spring
    sp:update(self.y + (self.sel - first) * self.rowH)
    local lo, hi = self.y, self.y + (self.visible - 1) * self.rowH
    if sp.value < lo then sp.value = lo elseif sp.value > hi then sp.value = hi end
    self.by = floor(sp.value + 0.5)
    self.sbSpring:update(first - 1)
    return first
end

-- One pass over the visible rows. Rows outside [yMin, yMax) are skipped (the
-- white pass only needs the ones the bar overlaps).
local function listRows(self, first, bumpY, yMin, yMax)
    local x, y, rowH, items, label = self.x, self.y, self.rowH, self.items, self.label
    for i = first, min(#items, first + self.visible - 1) do
        local ry = y + (i - first) * rowH + bumpY
        if ry + rowH > yMin and ry < yMax then
            local p = fxEnter(self, i - first)
            if p > 0 then
                local text = label and label(items[i], i) or items[i]
                gfx.drawText(text, x + 6 + floor(fxOffset(self, i) + 0.5) + fxSlide(self, p), ry)
            end
        end
    end
end

-- Draws the rows and the sliding bar; returns the first visible index.
-- The bar's y chases the selection through the spring. Rows are drawn black,
-- then the bar, then the rows again in white clipped to the bar, so text is
-- readable wherever the bar is while it slides, fills or nudges.
function List:draw()
    local first = self:update()
    if not gfx then return first end
    local w, rowH = self.w, self.rowH
    local bumpY = floor(self.bumpW.pos + 0.5)
    local ps = fxEnter(self, self.sel - first)
    local bx, by = self.x + fxSlide(self, ps), self.by - 1 + bumpY
    local bw = floor(w * fxFill(self) + 0.5)
    if UI.font.body then gfx.setFont(UI.font.body) end
    gfx.setImageDrawMode(gfx.kDrawModeCopy)
    if fxFlashing(self) then
        if ps > 0 then
            gfx.setColor(gfx.kColorWhite)
            gfx.fillRect(bx, by, bw, rowH)
            gfx.setColor(gfx.kColorBlack)
            gfx.drawRect(bx, by, bw, rowH)
        end
        listRows(self, first, bumpY, -1e9, 1e9)
    else
        listRows(self, first, bumpY, -1e9, 1e9)
        if ps > 0 then
            gfx.setColor(gfx.kColorBlack)
            gfx.fillRect(bx, by, bw, rowH)
            gfx.setClipRect(bx, by, bw, rowH)
            gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
            listRows(self, first, bumpY, by, by + rowH)
            gfx.setImageDrawMode(gfx.kDrawModeCopy)
            gfx.clearClipRect()
        end
    end
    local n = #self.items
    if self.scrollbar and n > self.visible then
        UI.scrollbar(self.x + w + 2, self.y - 1, 4, self.visible * rowH, self.sbSpring.value, self.visible, n)
    end
    return first
end

-- ---------------------------------------------------------------------------
-- pure core + draw: grid
-- ---------------------------------------------------------------------------

-- Row-major cells, `cols` to a row, scrolling by whole rows. Left/right wrap
-- within a row and up/down wrap through the rows, like the list does.
local Grid = {}
Grid.__index = Grid

-- opts: cols (default 3), visible (rows shown, default 8), items (strings to
-- draw), smooth (scroll spring frames, default 3), and the effect settings
-- above (a row's entrance is staggered by its row).
function UI.grid(opts)
    local g = setmetatable({}, Grid)
    g.cols = opts.cols or 3
    g.visible = opts.visible or 8
    g.items = opts.items or {}
    g.sel = 1
    g.top = 0              -- first row on screen, 0-based
    g.spring = UI.spring(0, opts.smooth or 3)   -- follows `top`, in rows
    fxInit(g, opts)
    return g
end

function Grid:count() return #self.items end

function Grid:rows()
    local n = #self.items
    return n == 0 and 0 or (n - 1) // self.cols + 1
end

function Grid:setItems(items)
    self.items = items
    self.sel = min(self.sel, max(1, #items))
    self:follow()
end

-- Keep the selected row inside the window.
function Grid:follow()
    local row = (self.sel - 1) // self.cols
    if row < self.top then self.top = row end
    if row >= self.top + self.visible then self.top = row - self.visible + 1 end
end

-- Step the selection by (dx, dy) cells. Returns true if either was nonzero.
-- A short last row clamps to its final cell. Wrapping past the first or last
-- row bumps the grid.
function Grid:move(dx, dy)
    local n = #self.items
    if n == 0 or (dx == 0 and dy == 0) then return false end
    local cols, rows = self.cols, self:rows()
    local old = self.sel
    local row, col = (old - 1) // cols, (old - 1) % cols
    local wrapDir = 0
    if dy ~= 0 then
        local r = row + dy
        if r < 0 or r >= rows then wrapDir = dy > 0 and 1 or -1 end
        row = r % rows
    end
    if dx ~= 0 then col = (col + dx) % cols end
    self.sel = min(n, row * cols + col + 1)
    if self.sel ~= old then fxSelect(self, old, wrapDir)
    elseif wrapDir ~= 0 and self.fx.bump > 0 then self.bumpW:kick(-wrapDir * self.fx.bump) end
    self:follow()
    return true
end

-- Up/down/left/right from a repeater. Returns true if the selection stepped.
function Grid:navigate(rep)
    return self:move(rep:horizontal(), rep:vertical())
end

-- Move by whole rows without wrapping (crank). Returns true if it moved;
-- pushing against the first or last row bumps the grid and returns false.
function Grid:scroll(rows)
    local n = #self.items
    if n == 0 or rows == 0 then return false end
    local cols, old = self.cols, self.sel
    local cur = (old - 1) // cols
    local row = max(0, min(self:rows() - 1, cur + rows))
    if row == cur then
        if self.fx.bump > 0 then self.bumpW:kick(rows > 0 and -self.fx.bump or self.fx.bump) end
        return false
    end
    self.sel = min(n, row * cols + (old - 1) % cols + 1)
    fxSelect(self, old, 0)
    self:follow()
    return true
end

-- The cell was chosen: blink it inverted and give it a kick.
function Grid:confirm()
    local fx = self.fx
    self.flashT = fx.flash
    if fx.flash > 0 then self.nudgeW:kick(3) end
end

-- Start the entrance, row by row from the top; see List:enter.
function Grid:enter(delay)
    self.enterT = -(delay or 0)
    self.fillT = self.fx.fill
end

-- Advance every animation one frame (draw() calls this). The scroll spring
-- may trail for the other rows, but never so far that the selected row
-- leaves the window: its value is clamped each frame to keep the row inside.
function Grid:update()
    fxUpdate(self)
    local sp = self.spring
    sp:update(self.top)
    local row = (self.sel - 1) // self.cols
    local lo, hi = row - self.visible + 1, row
    if sp.value < lo then sp.value = lo elseif sp.value > hi then sp.value = hi end
end

-- Highlight rectangle for a cell whose text may be wider than the cell:
-- grows to `need` px so the selected text is always readable, and slides left
-- if that would pass `right`. Returns x, w.
function UI.cellBar(x, w, need, right)
    local bw = max(w, need)
    local bx = x
    if bx + bw > right then bx = right - bw end
    return bx, bw
end

-- Intersect a rect with the clip area and set it as the clip rect. False
-- (and nothing set) when they do not overlap.
local function clipTo(x, y, w, h, cx, cy, cw, ch)
    local x2, y2 = min(x + w, cx + cw), min(y + h, cy + ch)
    x, y = max(x, cx), max(y, cy)
    if x2 <= x or y2 <= y then return false end
    gfx.setClipRect(x, y, x2 - x, y2 - y)
    return true
end

-- Draws visible rows at (x, y) clipped to the grid, with the rows gliding to
-- their scroll position, and a scroll bar to the right when there is more
-- than fits. Cell width colW, row height rowH. Each cell's text is clipped to
-- its own column; the selected cell widens to show its whole text, on top of
-- its neighbours.
function Grid:draw(x, y, colW, rowH)
    self:update()
    if not gfx then return end
    local rows = self:rows()
    local y0 = y - floor(self.spring.value * rowH + 0.5) + floor(self.bumpW.pos + 0.5)
    local cols, items, sel, top = self.cols, self.items, self.sel, self.top
    local flashing = fxFlashing(self)
    local gx, gy, gw, gh = x - 6, y - 4, cols * colW + 6, self.visible * rowH + 4
    if UI.font.body then gfx.setFont(UI.font.body) end
    gfx.setColor(gfx.kColorBlack)
    gfx.setImageDrawMode(gfx.kDrawModeCopy)
    local selX, selY
    for i = 1, #items do
        local row, col = (i - 1) // cols, (i - 1) % cols
        local cy = y0 + row * rowH
        if cy > gy - rowH and cy < gy + gh then
            local p = fxEnter(self, max(0, row - top))
            if p > 0 then
                local cx = x + col * colW + fxSlide(self, p)
                if i == sel then
                    selX, selY = cx, cy
                elseif clipTo(cx - 2, cy - 1, colW - 2, rowH, gx, gy, gw, gh) then
                    gfx.drawText(items[i], cx + 2 + floor(fxOffset(self, i) + 0.5), cy)
                end
            end
        end
    end
    if selX then
        local text = items[sel]
        local tw = gfx.getTextSize(text)
        local bx, bw = UI.cellBar(selX - 2, colW - 2, tw + 8, gx + gw)
        bw = floor(bw * fxFill(self) + 0.5)
        if clipTo(bx, selY - 1, bw, rowH, gx, gy, gw, gh) then
            local tx = bx + 4 + floor(fxOffset(self, sel) + 0.5)
            if fxFlashing(self) then
                gfx.setColor(gfx.kColorWhite)
                gfx.fillRect(bx, selY - 1, bw, rowH)
                gfx.setColor(gfx.kColorBlack)
                gfx.drawRect(bx, selY - 1, bw, rowH)
                gfx.drawText(text, tx, selY)
            else
                gfx.fillRect(bx, selY - 1, bw, rowH)
                gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
                gfx.drawText(text, tx, selY)   -- clipped to the bar as it grows
                gfx.setImageDrawMode(gfx.kDrawModeCopy)
            end
        end
    end
    gfx.clearClipRect()
    if rows > self.visible then
        UI.scrollbar(x + cols * colW, y, 4, self.visible * rowH, self.spring.value, self.visible, rows)
    end
end

-- ---------------------------------------------------------------------------
-- device shell: panels, bars, text, meters
-- ---------------------------------------------------------------------------

-- Scroll bar: an outlined track of w x h with a filled thumb.
function UI.scrollbar(x, y, w, h, top, visible, total)
    if not gfx then return end
    local off, size = UI.thumb(h, top, visible, total)
    gfx.setColor(gfx.kColorBlack)
    gfx.drawRect(x, y, w, h)
    gfx.fillRect(x, y + off, w, size)
end

-- White box with a double black border. `scale` (optional, see UI.popScale)
-- draws it grown or shrunk around its centre, for a pop-open.
function UI.panel(x, y, w, h, scale)
    if not gfx then return end
    if scale then
        if scale <= 0 then return end
        local nw, nh = floor(w * scale + 0.5), floor(h * scale + 0.5)
        x, y = x + floor((w - nw) / 2), y + floor((h - nh) / 2)
        w, h = nw, nh
        if w < 8 or h < 8 then
            gfx.setColor(gfx.kColorBlack)
            gfx.fillRect(x, y, max(w, 1), max(h, 1))
            return
        end
    end
    gfx.setColor(gfx.kColorWhite)
    gfx.fillRect(x, y, w, h)
    gfx.setColor(gfx.kColorBlack)
    gfx.setLineWidth(2)
    gfx.drawRect(x, y, w, h)
    gfx.drawRect(x + 3, y + 3, w - 6, h - 6)
    gfx.setLineWidth(1)
end

-- Black title bar across the top, optional right-aligned `sub`.
function UI.header(text, sub)
    if not gfx then return end
    gfx.setColor(gfx.kColorBlack)
    gfx.fillRect(0, 0, W, 22)
    if UI.font.title then gfx.setFont(UI.font.title) end
    gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
    gfx.drawText(text, 8, 3)
    if sub then
        if UI.font.body then gfx.setFont(UI.font.body) end
        local w = gfx.getTextSize(sub)
        gfx.drawText(sub, W - w - 8, 5)
    end
    gfx.setImageDrawMode(gfx.kDrawModeCopy)
end

-- White hint bar across the bottom with a rule above it.
function UI.footer(text)
    if not gfx then return end
    gfx.setColor(gfx.kColorWhite)
    gfx.fillRect(0, H - 18, W, 18)
    gfx.setColor(gfx.kColorBlack)
    gfx.drawLine(0, H - 18, W, H - 18)
    if UI.font.body then gfx.setFont(UI.font.body) end
    gfx.drawText(text, 8, H - 15)
end

-- Black text with a white outline, readable over any background. Nine
-- drawText calls, so keep it to a few lines.
function UI.outlined(text, x, y)
    if not gfx then return end
    gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
    for dx = -1, 1 do
        for dy = -1, 1 do
            if dx ~= 0 or dy ~= 0 then gfx.drawText(text, x + dx, y + dy) end
        end
    end
    gfx.setImageDrawMode(gfx.kDrawModeCopy)
    gfx.drawText(text, x, y)
end

-- Level meters with a falling peak tick. Levels are plain numbers 0..top
-- (default 15) in a table you reuse each frame, so nothing is allocated here.
local Meters = {}
Meters.__index = Meters

local numCache = {}
local function numStr(c)
    local s = numCache[c]
    if not s then s = tostring(c); numCache[c] = s end
    return s
end

-- opts: top (full-scale level, default 15), decay (peak fall per frame,
-- default 0.5), labels (names to show under the bars when there are exactly
-- #labels bars and they are wide enough, otherwise 1..n).
function UI.meters(opts)
    opts = opts or {}
    return setmetatable({ top = opts.top or 15, decay = opts.decay or 0.5,
                          labels = opts.labels, peak = {} }, Meters)
end

-- Fold this frame's level for bar c into its peak. Pure; draw calls it.
function Meters:track(c, v)
    local p = self.peak[c] or 0
    p = max(v, p - self.decay)
    self.peak[c] = p
    return p
end

-- Draws n bars into `width` px starting at (x, y), each h tall. `cursor` is
-- the bar to underline; `muted[c]` crosses a bar out. Needs the body font set
-- for the labels.
function Meters:draw(levels, n, x, y, h, width, cursor, muted)
    local step = floor((width or 120) / n)
    local bw = min(22, step - 2)
    local labels = self.labels
    local named = labels and #labels == n and step >= 30
    local top = self.top
    if gfx and UI.font.body then gfx.setFont(UI.font.body) end
    for c = 1, n do
        local v = levels[c] or 0
        local p = self:track(c, v)
        if gfx then
            local bx = x + (c - 1) * step
            gfx.setColor(gfx.kColorBlack)
            gfx.drawRect(bx, y, bw, h)
            local fill = floor((h - 4) * v / top)
            gfx.fillRect(bx + 2, y + h - 2 - fill, bw - 4, fill)
            local py = y + h - 2 - floor((h - 4) * p / top)
            gfx.drawLine(bx + 2, py, bx + bw - 3, py)
            if muted and muted[c] then
                gfx.drawLine(bx, y, bx + bw, y + h)
                gfx.drawLine(bx + bw, y, bx, y + h)
            end
            if cursor == c then gfx.fillRect(bx, y + h + 16, bw, 2) end
            gfx.drawText(named and labels[c] or numStr(c), bx, y + h + 3)
        end
    end
end

return UI
