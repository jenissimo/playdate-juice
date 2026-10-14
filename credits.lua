-- credits.lua -- end credits and title cards for Playdate (playdate-juice).
--
-- A script -- a plain Lua table of titles, headings, role/name pairs, name
-- grids, paragraphs, logos and cards -- becomes a timed presentation: a roll
-- that scrolls up the screen and stops on the rows you ask it to, handing over
-- to centred cards that dissolve in and out. Rows slide or type themselves in
-- as they enter and dither away at the edges instead of being cut by the bezel.
--
-- Three decisions shape this file:
--
-- 1. EVERYTHING IS A FUNCTION OF ONE CLOCK. The script is compiled once, in
--    Credits.new, into a timeline of linear pieces, and what is on screen at
--    frame t is computed from t alone. That is what lets the crank scrub the
--    credits back and forth, A fast-forward and B skip to the last card with
--    no state to unwind, and it is what makes the whole thing testable on the
--    host: a test asks where a row is at frame 300 instead of playing 300
--    frames and looking. It is also why reveals hang off a row's position and
--    not a timer -- crank back and a heading un-types itself.
--
-- 2. ONE BIT HAS NO ALPHA. A row leaving through an edge, or fading into a
--    card, is drawn into a scratch row image and put on screen with drawFaded
--    (a Bayer dither), so it fades over ANY backdrop -- an animated Backgrounds
--    loop, a starfield -- rather than needing a flat paper colour to paint a
--    gradient over. Each faded draw consumes the scratch immediately, so one
--    scratch serves every row of a frame: it is allocated in new(), and the
--    draw loop allocates nothing.
--
-- 3. FITTING THE MUSIC IS ARITHMETIC. Holds and cards take a fixed number of
--    frames; the rest is scroll distance over speed. Given `fit` (the song's
--    length in frames) new() solves for the speed that lands the last row on
--    the last bar, instead of somebody tuning a speed by ear for an hour.
--
-- Text goes through font:drawText, never gfx.drawText: the latter parses
-- *bold* and _italic_ markup, and a credits list is exactly where a handle
-- like "pixel_witch" turns half italic and loses its underscore.
--
-- API
--   local roll = Credits.new(script, opts)
--   roll:update()       once a frame: built-in controls, then one frame of clock
--   roll:draw()         the current frame (a silent no-op with no SDK)
--   roll.done           true at the end; roll:onEnd(fn) fires once
--   roll:advance(n)     move the clock n frames (negative rewinds), firing cues
--   roll:seek(frame)    jump without firing cues;  roll:skip(), roll:restart()
--   roll.t, roll.duration, roll.speed, roll.rate, roll:progress(), roll:scroll()
--
-- A script is a list of entries (a bare string is { text = s }):
--   { title = "NYANDOKU", sub = "a cat puzzle" }  pixel-doubled unless fonts.title
--   { heading = "Music" }                         centred, with side rules
--   { role = "Composer", name = "Ann" }           or names = { "Ann", "Bo" }
--   { name = "Ann" }                              one centred name
--   { names = { ... }, columns = 3 }              a grid; columns is optional
--   { text = "A paragraph..." }                   word-wrapped
--   { image = "images/logo", ink = true }         ink: tinted to the text colour
--   { rule = true }                               a divider
--   { space = 40 }                                extra room
--   { card = "THE END" } / { card = { entries } } a centred card: in, hold, out
-- Any entry also takes:
--   gap = px          space above it (default per kind: Credits.GAPS)
--   align = "left" | "center" | "right"
--   reveal = "slide" | "type" | "fade" | "none"   (default per kind: Credits.REVEALS)
--   hold = frames     roll: stop with it centred; card: time fully shown.
--                     hold = true: stop here for good -- it must be the end.
--                     The last card stays by default; give it a number to leave.
--   on = fn(roll, entry, x, y)   fires as it reaches the centre line (a card:
--                     as it starts) -- a jingle, a shake, a burst of particles
--
-- opts:
--   speed = 1         px per frame; or
--   fit = frames      solve the speed so the whole thing lasts exactly this long
--   style = "split"   role/name layout: "split" (film: role | name),
--                     "leader" (role ..... name), "stack" (role over name)
--   fonts = { title=, sub=, heading=, role=, name=, text= }  fonts or paths
--   font = f          one font for every style `fonts` leaves out
--   titleScale = 2    pixel-doubling for titles (1 once fonts.title is given)
--   invert = false    white text on black
--   background = fn   fn(roll) paints the backdrop; false: draw over the frame
--   margin = 24, gutter = 16, rules = true (heading side rules)
--   fade = 24         the edge band rows dither through, px (0: a hard cut)
--   reveal = nil      the roll's reveal for entries that do not set one
--   card = { fadeIn = 15, hold = 60, fadeOut = 12, stagger = 4 }
--   controls = true   crank scrubs, A fast-forwards, B skips to the last card
--   fast = 4, crank = 0.5 (frames per crank degree)
--   onType = fn(roll) a frame on which a typing row revealed letters
--   metrics = {...}   host tests: width(style, s), height(style), image(entry)

Credits = Credits or {}

local pd  = rawget(_G, "playdate")
local gfx = pd and pd.graphics
local u8  = rawget(_G, "utf8")

local W <const> = 400
local H <const> = 240
local floor <const> = math.floor
local ceil <const> = math.ceil
local max <const> = math.max
local min <const> = math.min

Credits.SCREEN_W, Credits.SCREEN_H = W, H

-- ============================================================== pure section
-- Everything down to "device section" is plain Lua: layout, the timeline and
-- the clock. This is the half the host tests cover.

Credits._ready = false

local SLIDE <const> = 40        -- px a sliding row travels
local ROW_GAP <const> = 2       -- between the rows of one entry
local TYPE_RATE <const> = 0.75  -- letters a frame, a typing row in a card

-- Space above each kind of entry; none above the first of a roll or a card.
Credits.GAPS = {
    title = 24, heading = 22, role = 4, name = 4, names = 8,
    text = 12, image = 16, rule = 14,
}

-- How each kind enters a roll unless told otherwise. A heading types because
-- it is read; names slide because they are scanned; a grid of fifty backers
-- sliding at once is noise, so it only fades at the edges. Cards dissolve.
Credits.REVEALS = {
    title = "slide", heading = "type", role = "slide", name = "slide",
    names = "none", text = "none", image = "none", rule = "slide",
}

local REVEAL_OK <const> = { slide = true, type = true, fade = true, none = true }

local function clamp01(v)
    if v < 0 then return 0 end
    if v > 1 then return 1 end
    return v
end

local function outCubic(t) local u = 1 - t; return 1 - u * u * u end
Credits.outCubic = outCubic

-- utf8.len, but total: a byte string that is not valid UTF-8 counts its
-- bytes, so a stray Latin-1 name degrades to odd glyphs rather than a crash.
local function ulen(s)
    return (u8 and u8.len(s)) or #s
end

-- The first n characters of s. Never cuts a multi-byte character in half: a
-- typewriter that does shows a broken glyph for one frame per letter of
-- every name with an accent in it.
local function uprefix(s, n)
    if not u8 then return s:sub(1, n) end
    local stop = u8.offset(s, n + 1)
    if not stop then return s end
    return s:sub(1, stop - 1)
end
Credits.ulen, Credits.uprefix = ulen, uprefix

-- Greedy word wrap; "\n" starts a new paragraph. A single word wider than the
-- line gets a line to itself instead of being split: in a credits list a name
-- broken in two reads as a typo.
function Credits.wrap(text, width, measure)
    local lines = {}
    for para in (text .. "\n"):gmatch("(.-)\n") do
        local line = nil
        for word in para:gmatch("%S+") do
            local candidate = line and (line .. " " .. word) or word
            if line and measure(candidate) > width then
                lines[#lines + 1] = line
                line = word
            else
                line = candidate
            end
        end
        lines[#lines + 1] = line or ""
    end
    return lines
end

-- Stand-in font metrics for the host: a 7 px advance and a 15 px line, near
-- enough the system font that a host-tested layout is the device's layout.
Credits.HOST_METRICS = {
    width  = function(style, s) return 7 * ulen(s) end,
    height = function(style) return 15 end,
    image  = function(e) return e.w or 32, e.h or 32, nil end,
}

local function kindOf(e)
    if e.card ~= nil then return "card" end
    if e.title then return "title" end
    if e.heading then return "heading" end
    if e.role then return "role" end
    if e.names then return "names" end
    if e.name then return "name" end
    if e.text then return "text" end
    if e.image then return "image" end
    if e.rule then return "rule" end
    if e.space then return "space" end
    return nil
end
Credits.kindOf = kindOf

local function place(w, align, margin)
    if align == "left" then return margin end
    if align == "right" then return W - margin - w end
    return floor((W - w) / 2)
end

-- side: which way a sliding part comes in from (-1 left, 1 right).
-- dy: bottom-aligns a part in a row taller than its own font, which is the
-- nearest a layout without baseline metrics gets to sharing a baseline.
local function newPart(style, text, x, w, side, dy)
    return { style = style, text = text, x = x, w = w, n = ulen(text),
             side = side, dy = dy or 0 }
end

local function newRow(e, h, reveal, side)
    return { y = 0, h = h, parts = {}, chars = 0, entry = e,
             reveal = reveal, side = side }
end

local function addPart(row, part)
    row.parts[#row.parts + 1] = part
    row.chars = row.chars + part.n
end

local function put(rows, row, y)
    row.y = y
    rows[#rows + 1] = row
    return y + row.h
end

-- Lays a list of entries out top-down from y = 0. Returns the rows (sorted by
-- y, which the draw loop's binary search relies on), one block per entry (its
-- row span, for holds and cues) and the total height.
local function layoutEntries(list, ctx)
    local m, margin = ctx.m, ctx.margin
    local inner = W - 2 * margin
    local rows, blocks = {}, {}
    local y, first, flip = 0, true, -1

    for idx = 1, #list do
        local e = list[idx]
        if type(e) == "string" then e = { text = e } end
        if type(e) ~= "table" then
            error(("credits: %s entry %d is a %s, not a table"):format(ctx.where, idx, type(e)), 0)
        end
        local k = kindOf(e)
        if not k then
            error(("credits: %s entry %d is none of title, heading, role, name, names, "
                .. "text, image, rule, space, card"):format(ctx.where, idx), 0)
        end
        if k == "card" then
            error(("credits: %s entry %d: a card cannot hold a card"):format(ctx.where, idx), 0)
        end
        if k == "space" then
            y = y + e.space
        else
            local reveal = e.reveal or ctx.reveal or Credits.REVEALS[k]
            if not REVEAL_OK[reveal] then
                error(("credits: %s entry %d: no reveal '%s'"):format(ctx.where, idx, tostring(reveal)), 0)
            end
            if not first then y = y + (e.gap or Credits.GAPS[k]) end
            first = false
            local i0 = #rows + 1

            if k == "title" then
                local scale = e.scale or ctx.titleScale
                local text = tostring(e.title)
                local w = m.width("title", text) * scale
                local row = newRow(e, m.height("title") * scale, reveal, -1)
                row.scale = scale
                addPart(row, newPart("title", text, place(w, e.align, margin), w, -1))
                y = put(rows, row, y)
                if e.sub then
                    local s = tostring(e.sub)
                    local sw = m.width("sub", s)
                    local sub = newRow(e, m.height("sub"), reveal, 1)
                    addPart(sub, newPart("sub", s, place(sw, e.align, margin), sw, 1))
                    y = put(rows, sub, y + ROW_GAP + 2)
                end

            elseif k == "heading" then
                local text = tostring(e.heading)
                local w, h = m.width("heading", text), m.height("heading")
                local x = place(w, e.align, margin)
                local row = newRow(e, h, reveal, flip)
                flip = -flip
                addPart(row, newPart("heading", text, x, w, row.side))
                if ctx.rules and e.rules ~= false and (e.align or "center") == "center" then
                    local len = min(48, x - 8 - margin)
                    if len >= 6 then
                        row.rules = { left = x - 8, right = x + w + 8, len = len, cy = floor(h / 2) }
                    end
                end
                y = put(rows, row, y)

            elseif k == "role" then
                local names = e.names or { e.name }
                local role = tostring(e.role)
                local rw, rh, nh = m.width("role", role), m.height("role"), m.height("name")
                local h = max(rh, nh)
                local style = e.style or ctx.style
                if style == "split" then
                    -- Film credits: the role ends just left of the split line
                    -- and the name starts just right of it. A role or a name
                    -- too wide for its half falls back to stacking -- clipped
                    -- text at the bezel is worse than a different layout.
                    local rx = ctx.split - floor(ctx.gutter / 2)
                    local nx = rx + ctx.gutter
                    local fits = rw <= rx - margin
                    for i = 1, #names do
                        if m.width("name", tostring(names[i])) > W - margin - nx then fits = false end
                    end
                    if fits then
                        for i = 1, #names do
                            local nm = tostring(names[i])
                            local row = newRow(e, h, reveal, 1)
                            if i == 1 then addPart(row, newPart("role", role, rx - rw, rw, -1, h - rh)) end
                            addPart(row, newPart("name", nm, nx, m.width("name", nm), 1, h - nh))
                            if i > 1 then y = y + ROW_GAP end
                            y = put(rows, row, y)
                        end
                    else
                        style = "stack"
                    end
                elseif style == "leader" then
                    for i = 1, #names do
                        local nm = tostring(names[i])
                        local nw = m.width("name", nm)
                        local nxr = W - margin - nw
                        local row = newRow(e, h, reveal, 1)
                        if i == 1 then
                            addPart(row, newPart("role", role, margin, rw, -1, h - rh))
                            local x1, x2 = margin + rw + 6, nxr - 6
                            if x2 - x1 >= 6 then row.dots = { x1 = x1, x2 = x2, cy = h - 4 } end
                        end
                        addPart(row, newPart("name", nm, nxr, nw, 1, h - nh))
                        if i > 1 then y = y + ROW_GAP end
                        y = put(rows, row, y)
                    end
                end
                if style == "stack" then
                    local row = newRow(e, rh, reveal, -1)
                    addPart(row, newPart("role", role, place(rw, e.align, margin), rw, -1))
                    y = put(rows, row, y)
                    for i = 1, #names do
                        local nm = tostring(names[i])
                        local nw = m.width("name", nm)
                        local nrow = newRow(e, nh, reveal, 1)
                        addPart(nrow, newPart("name", nm, place(nw, e.align, margin), nw, 1))
                        y = put(rows, nrow, y + ROW_GAP)
                    end
                end

            elseif k == "name" then
                local nm = tostring(e.name)
                local nw = m.width("name", nm)
                local row = newRow(e, m.height("name"), reveal, flip)
                flip = -flip
                addPart(row, newPart("name", nm, place(nw, e.align, margin), nw, row.side))
                y = put(rows, row, y)

            elseif k == "names" then
                local list2, widths, widest = e.names, {}, 0
                local n = #list2
                for i = 1, n do
                    widths[i] = m.width("name", tostring(list2[i]))
                    if widths[i] > widest then widest = widths[i] end
                end
                local cols = e.columns or min(4, floor(inner / (widest + 16)))
                cols = max(1, min(cols, max(n, 1)))
                local cell = floor(inner / cols)
                local h = m.height("name")
                for r = 1, (n + cols - 1) // cols do
                    local from = (r - 1) * cols + 1
                    local to = min(n, from + cols - 1)
                    -- a short last row is centred as a group, not left-packed
                    local left = margin + floor((inner - (to - from + 1) * cell) / 2)
                    local row = newRow(e, h, reveal, flip)
                    flip = -flip
                    for i = from, to do
                        local c = i - from
                        addPart(row, newPart("name", tostring(list2[i]),
                            left + c * cell + floor((cell - widths[i]) / 2), widths[i],
                            c % 2 == 0 and -1 or 1))
                    end
                    if r > 1 then y = y + ROW_GAP end
                    y = put(rows, row, y)
                end

            elseif k == "text" then
                local lines = Credits.wrap(tostring(e.text), e.width or inner,
                    function(s) return m.width("text", s) end)
                local h = m.height("text")
                for i = 1, #lines do
                    local w = m.width("text", lines[i])
                    local row = newRow(e, h, reveal, flip)
                    flip = -flip
                    addPart(row, newPart("text", lines[i], place(w, e.align, margin), w, row.side))
                    if i > 1 then y = y + ROW_GAP end
                    y = put(rows, row, y)
                end

            elseif k == "image" then
                local w, h, img = m.image(e)
                local row = newRow(e, h, reveal, flip)
                flip = -flip
                row.image, row.img, row.x, row.w = true, img, place(w, e.align, margin), w
                y = put(rows, row, y)

            elseif k == "rule" then
                local row = newRow(e, 7, reveal, 1)
                row.divider = { cx = floor(W / 2), half = floor(min(e.width or 120, inner) / 2), cy = 3 }
                y = put(rows, row, y)
            end

            if #rows >= i0 then
                blocks[#blocks + 1] = { entry = e, i0 = i0, i1 = #rows, y0 = rows[i0].y, y1 = y }
            end
        end
    end
    return rows, blocks, y
end

-- The frame at which a roll's scroll first reaches `target` (scroll only ever
-- decreases, so the first crossing is the only one).
local function timeAtScroll(pcs, target)
    for i = 1, #pcs do
        local pc = pcs[i]
        if pc.s0 ~= pc.s1 and pc.s0 >= target and target >= pc.s1 then
            return pc.t0 + (pc.s0 - target) / (pc.s0 - pc.s1) * (pc.t1 - pc.t0)
        end
    end
    return pcs[#pcs].t1
end

-- Script -> plan: segments (each a roll or a card) laid on one timeline.
-- A roll's scroll is the screen y of its content top: it starts at H (the
-- content just below the screen) and ends at -height (just above), or with
-- its hold = true block centred. Pure: hand it host metrics and assert away.
function Credits.layout(script, opts, m)
    if type(script) ~= "table" or #script == 0 then
        error("credits: the script is empty", 2)
    end
    opts = opts or {}
    m = m or Credits.HOST_METRICS
    local style = opts.style or "split"
    if style ~= "split" and style ~= "leader" and style ~= "stack" then
        error("credits: no style '" .. tostring(style) .. "' (split, leader, stack)", 2)
    end
    if opts.reveal ~= nil and not REVEAL_OK[opts.reveal] then
        error("credits: no reveal '" .. tostring(opts.reveal) .. "'", 2)
    end
    local co = opts.card or {}
    local ctx = {
        m = m, margin = opts.margin or 24, gutter = opts.gutter or 16,
        style = style, split = opts.split or floor(W / 2),
        titleScale = opts.titleScale or ((opts.fonts and opts.fonts.title) and 1 or 2),
        rules = opts.rules ~= false,
    }

    -- Consecutive non-card entries are one roll; every card is its own segment.
    local segs, cur = {}, nil
    for i = 1, #script do
        local e = script[i]
        if type(e) == "table" and e.card ~= nil then
            cur = nil
            segs[#segs + 1] = { kind = "card", entry = e }
        else
            if not cur then
                cur = { kind = "roll", entries = {} }
                segs[#segs + 1] = cur
            end
            cur.entries[#cur.entries + 1] = e
        end
    end

    -- Pass 1: lay out, and total what is fixed (holds, cards) against what
    -- moves (scroll distance), so `fit` can solve for the speed.
    local fixed, dist, maxTextH = 0, 0, 1
    for si = 1, #segs do
        local seg, last = segs[si], si == #segs
        if seg.kind == "roll" then
            ctx.reveal, ctx.where = opts.reveal, "roll"
            seg.rows, seg.blocks, seg.height = layoutEntries(seg.entries, ctx)
            for bi = 1, #seg.blocks do
                local b = seg.blocks[bi]
                local hold = b.entry.hold
                if hold == true then
                    if not last or bi ~= #seg.blocks then
                        error("credits: hold = true ends the credits, so nothing may follow it", 2)
                    end
                    seg.stop = b
                elseif hold ~= nil then
                    if type(hold) ~= "number" or hold < 0 then
                        error("credits: hold must be a frame count or true", 2)
                    end
                    fixed = fixed + hold
                end
            end
            local stop = seg.stop
            seg.sEnd = stop and (H / 2 - (stop.y0 + stop.y1) / 2) or -seg.height
            dist = dist + (H - seg.sEnd)
        else
            local e = seg.entry
            local content = e.card
            if type(content) == "string" then content = { { title = content } } end
            if type(content) ~= "table" then
                error("credits: card must be a string or a list of entries", 2)
            end
            ctx.reveal, ctx.where = e.reveal or "fade", "card"
            seg.rows, seg.blocks, seg.height = layoutEntries(content, ctx)
            seg.top = floor((H - seg.height) / 2)
            seg.fadeIn = max(1, e.fadeIn or co.fadeIn or 15)
            seg.fadeOut = max(1, e.fadeOut or co.fadeOut or 12)
            if e.hold ~= nil and e.hold ~= true and (type(e.hold) ~= "number" or e.hold < 0) then
                error("credits: hold must be a frame count or true", 2)
            end
            if e.hold == true or (e.hold == nil and last) then
                if not last then error("credits: only the last card can stay (hold = true)", 2) end
                seg.stay = true
            end
            seg.hold = seg.stay and 0 or (e.hold or co.hold or 60)
            -- Rows come in staggered; a typing row holds the next one back
            -- until it has finished, the way a typewriter would.
            local stagger = e.stagger or co.stagger or 4
            local at, inEnd, prev = 0, 0, nil
            for ri = 1, #seg.rows do
                local row = seg.rows[ri]
                local dur = seg.fadeIn
                if row.reveal == "type" then dur = max(dur, ceil(row.chars / TYPE_RATE)) end
                if prev then at = at + ((prev.reveal == "type") and prev.dur or stagger) end
                row.ct0, row.dur = at, dur
                inEnd = max(inEnd, at + dur)
                prev = row
            end
            seg.inEnd = inEnd
            seg.span = inEnd + seg.hold + (seg.stay and 0 or seg.fadeOut)
            fixed = fixed + seg.span
        end
        for ri = 1, #seg.rows do
            local row = seg.rows[ri]
            if not row.image and (row.scale or 1) == 1 and row.h > maxTextH then maxTextH = row.h end
        end
    end

    local speed = opts.speed or 1
    if opts.fit and dist > 0 then
        local free = opts.fit - fixed
        if free <= 0 then
            error(("credits: fit is %d frames, but the holds and cards alone take %d")
                :format(floor(opts.fit), ceil(fixed)), 2)
        end
        speed = dist / free
    end
    if speed <= 0 then error("credits: speed must be positive", 2) end

    -- Pass 2: lay every segment on the clock and find each cue's frame.
    local t, cues = 0, {}
    for si = 1, #segs do
        local seg = segs[si]
        seg.t0 = t
        if seg.kind == "roll" then
            local pcs, s = {}, H
            for bi = 1, #seg.blocks do
                local b = seg.blocks[bi]
                if type(b.entry.hold) == "number" then
                    local target = H / 2 - (b.y0 + b.y1) / 2
                    local dt = (s - target) / speed
                    pcs[#pcs + 1] = { t0 = t, t1 = t + dt, s0 = s, s1 = target }
                    t, s = t + dt, target
                    pcs[#pcs + 1] = { t0 = t, t1 = t + b.entry.hold, s0 = s, s1 = s }
                    t = t + b.entry.hold
                end
            end
            local dt = (s - seg.sEnd) / speed
            pcs[#pcs + 1] = { t0 = t, t1 = t + dt, s0 = s, s1 = seg.sEnd }
            t = t + dt
            seg.pieces = pcs
            for bi = 1, #seg.blocks do
                local b = seg.blocks[bi]
                if b.entry.on then
                    cues[#cues + 1] = { time = timeAtScroll(pcs, H / 2 - (b.y0 + b.y1) / 2),
                                        entry = b.entry, x = W / 2, y = H / 2 }
                end
            end
        else
            if seg.entry.on then
                cues[#cues + 1] = { time = t, entry = seg.entry, x = W / 2, y = H / 2 }
            end
            for bi = 1, #seg.blocks do
                local b = seg.blocks[bi]
                if b.entry.on then
                    cues[#cues + 1] = { time = t + seg.rows[b.i0].ct0, entry = b.entry,
                                        x = W / 2, y = seg.top + (b.y0 + b.y1) / 2 }
                end
            end
            t = t + seg.span
        end
        seg.t1 = t
    end
    table.sort(cues, function(a, b) return a.time < b.time end)

    local final = segs[#segs]
    return {
        segments = segs, duration = t, speed = speed, cues = cues,
        skipTo = final.kind == "card" and final.t0 or t,
        maxTextH = maxTextH,
        fade = opts.fade or 24, span = opts.revealSpan or SLIDE,
    }
end

-- ---- sampling: what the clock means right now -------------------------------

local function segmentAt(plan, t)
    local segs = plan.segments
    for i = 1, #segs do
        if t < segs[i].t1 then return segs[i] end
    end
    return segs[#segs]
end

local function scrollAt(seg, t)
    local pcs = seg.pieces
    for i = 1, #pcs do
        local pc = pcs[i]
        if t <= pc.t1 then
            local span = pc.t1 - pc.t0
            if span <= 0 then return pc.s1 end
            local f = (t - pc.t0) / span
            if f < 0 then f = 0 end
            return pc.s0 + (pc.s1 - pc.s0) * f
        end
    end
    return pcs[#pcs].s1
end

-- First row whose bottom is below `top` (rows are sorted by y).
local function firstVisible(rows, top)
    local lo, hi = 1, #rows + 1
    while lo < hi do
        local mid = (lo + hi) // 2
        local r = rows[mid]
        if r.y + r.h > top then hi = mid else lo = mid + 1 end
    end
    return lo
end

-- 0 as a roll row's top crosses the bottom edge, 1 once it is `span` px up.
-- Position, not time: that is what makes a reveal scrub backwards.
local function rollP(plan, y) return clamp01((H - y) / plan.span) end

-- 1 in the middle of the screen, falling to 0 as the row's centre reaches an
-- edge over `fade` px.
local function edgeAlpha(plan, y, h)
    local fade = plan.fade
    if fade <= 0 then return 1 end
    local cy = y + h * 0.5
    local d = cy < H - cy and cy or H - cy
    return clamp01(d / fade)
end

local function cardP(seg, row, t)
    return clamp01((t - seg.t0 - row.ct0) / row.dur)
end

local function cardAlpha(seg, row, t, p)
    local out = seg.stay and 1 or clamp01((seg.t1 - t) / seg.fadeOut)
    local reveal = row.reveal
    if reveal == "type" or reveal == "none" then return p > 0 and out or 0 end
    return min(p, out)
end

Credits._scrollAt, Credits._segmentAt = scrollAt, segmentAt
Credits._edgeAlpha, Credits._cardP, Credits._cardAlpha = edgeAlpha, cardP, cardAlpha

-- Letters showing on typing rows right now: the onType sound fires on frames
-- where this goes up.
local function typedCount(plan, t)
    local seg, n = segmentAt(plan, t), 0
    local rows = seg.rows
    if seg.kind == "roll" then
        local s = floor(scrollAt(seg, t) + 0.5)
        for i = firstVisible(rows, -s), #rows do
            local row = rows[i]
            local y = s + row.y
            if y >= H then break end
            if row.reveal == "type" then n = n + floor(rollP(plan, y) * row.chars) end
        end
    else
        for i = 1, #rows do
            local row = rows[i]
            if row.reveal == "type" then n = n + floor(cardP(seg, row, t) * row.chars) end
        end
    end
    return n
end

-- ---- the clock -------------------------------------------------------------

local Roll = {}
Roll.__index = Roll
Credits.Roll = Roll

-- Moves the clock; negative rewinds. Cues fire for frames in (from, t] while
-- moving forward, so a cue at frame 0 fires on the very first advance and a
-- rewind past a cue re-arms it.
function Roll:advance(dt)
    local prev = self.t
    local t = prev + (dt or 1)
    if t < 0 then t = 0 end
    if t > self.duration then t = self.duration end
    self.t = t
    if t > prev then
        local from, cues = self._cueFrom, self.cues
        for i = 1, #cues do
            local c = cues[i]
            if c.time > from and c.time <= t then c.entry.on(self, c.entry, c.x, c.y) end
        end
    end
    self._cueFrom = t
    if self.onType then
        local n = typedCount(self, t)
        if t > prev and n > self._typed then self.onType(self) end
        self._typed = n
    end
    self.done = t >= self.duration
    if self.done and not self._ended then
        self._ended = true
        if self._onEnd then self._onEnd(self) end
    elseif not self.done then
        self._ended = false
    end
    return t
end

-- Jumps without firing anything on the way: a seek is an edit, not playback.
function Roll:seek(frame)
    local t = max(0, min(frame or 0, self.duration))
    self.t, self._cueFrom = t, t
    self._typed = self.onType and typedCount(self, t) or 0
    self.done = t >= self.duration
    self._ended = self.done
    return t
end

-- To the last card (or the end): what B does. The cue AT the target still
-- fires on the next advance -- skipping to "Thanks for playing" should still
-- play its jingle.
function Roll:skip()
    if self.t >= self.skipTo then return self.t end
    self:seek(self.skipTo)
    self._cueFrom = self.skipTo - 0.5
    self._ended = false
    return self.t
end

function Roll:restart()
    self:seek(0)
    self._cueFrom = -1
    self._ended = false
    return self
end

function Roll:onEnd(fn) self._onEnd = fn; return self end
function Roll:progress() return self.duration > 0 and self.t / self.duration or 1 end

-- The content top's screen y while a roll is on, nil during a card: for a
-- backdrop that wants to drift with the credits.
function Roll:scroll()
    local seg = segmentAt(self, self.t)
    if seg.kind ~= "roll" then return nil end
    return scrollAt(seg, self.t)
end

function Credits.load()
    Credits._ready = gfx ~= nil
    return Credits._ready
end

-- ============================================================ device section
-- From here down only runs with an SDK. new() is where every allocation
-- happens: fonts, images, pre-rendered titles, the one scratch row.

local BAYER

local function resolveFonts(opts)
    local f = opts.fonts or {}
    local function get(style, variant)
        local v = f[style] or opts.font
        if type(v) == "string" then
            local font = gfx.font.new(v)
            if not font then error("credits: no font at " .. v, 4) end
            return font
        end
        return v or gfx.getSystemFont(variant)
    end
    return {
        title = get("title", "bold"), sub = get("sub", "italic"),
        heading = get("heading", "bold"), role = get("role", "normal"),
        name = get("name", "bold"), text = get("text", "normal"),
    }
end

-- A missing image degrades to an empty row of its declared size, the way
-- Transitions degrades a missing paw: credits that crash over a logo are
-- worse than credits without it.
local function deviceMetrics(fonts)
    local cache = {}
    return {
        width  = function(style, s) return fonts[style]:getTextWidth(s) end,
        height = function(style) return fonts[style]:getHeight() end,
        image  = function(e)
            local img = e.image
            if type(img) == "string" then
                local path = img
                img = cache[path]
                if img == nil then
                    img = gfx.image.new(path) or false
                    if not img then print("credits: no image at " .. path) end
                    cache[path] = img
                end
            end
            if not img then return e.w or 0, e.h or 0, nil end
            local w, h = img:getSize()
            return w, h, img
        end,
    }
end

local function rasterize(font, text, scale, mode)
    local w, h = max(1, font:getTextWidth(text)), max(1, font:getHeight())
    local img = gfx.image.new(w, h, gfx.kColorClear)
    gfx.pushContext(img)
    gfx.setImageDrawMode(mode)
    font:drawText(text, 0, 0)
    gfx.popContext()
    if scale == 1 then return img end
    return img:scaledImage(scale)
end

local function tint(src, mode)
    local w, h = src:getSize()
    local img = gfx.image.new(w, h, gfx.kColorClear)
    gfx.pushContext(img)
    gfx.setImageDrawMode(mode)
    src:draw(0, 0)
    gfx.popContext()
    return img
end

local function prepare(self, fonts)
    BAYER = gfx.image.kDitherTypeBayer8x8
    local inv = self.invert
    self.ink = inv and gfx.kColorWhite or gfx.kColorBlack
    self.paper = inv and gfx.kColorBlack or gfx.kColorWhite
    -- Glyphs are black on clear, so black ink is a plain copy and white ink is
    -- a fill; tinting an image needs FillBlack, or its white pixels survive.
    self.inkMode = inv and gfx.kDrawModeFillWhite or gfx.kDrawModeCopy
    local tintMode = inv and gfx.kDrawModeFillWhite or gfx.kDrawModeFillBlack
    for si = 1, #self.segments do
        local rows = self.segments[si].rows
        for ri = 1, #rows do
            local row = rows[ri]
            for pi = 1, #row.parts do
                local part = row.parts[pi]
                part.font = fonts[part.style]
            end
            if (row.scale or 1) ~= 1 then
                -- Pixel-doubled once, here; drawn as an image from then on.
                local p = row.parts[1]
                row.img = rasterize(p.font, p.text, row.scale, self.inkMode)
                row.image, row.x = true, p.x
            elseif row.image and row.img and row.entry.ink then
                row.img = tint(row.img, tintMode)
            end
        end
    end
    self.scratch = gfx.image.new(W, self.maxTextH, gfx.kColorClear)
    self._device = true
end

function Credits.new(script, opts)
    opts = opts or {}
    Credits.load()
    local device = Credits._ready and not opts.metrics
    local fonts = device and resolveFonts(opts) or nil
    local metrics = opts.metrics or (device and deviceMetrics(fonts)) or Credits.HOST_METRICS
    local self = setmetatable(Credits.layout(script, opts, metrics), Roll)
    self.invert = opts.invert or false
    self.background = opts.background or nil
    self.clear = opts.background ~= false
    self.controls = opts.controls ~= false
    self.fast = opts.fast or 4
    self.crankFrames = opts.crank or 0.5
    self.onType = opts.onType
    self.rate = 1
    self.t, self._cueFrom, self._typed = 0, -1, 0
    self.done, self._ended = false, false
    if device then prepare(self, fonts) end
    return self
end

-- One frame: the built-in controls (crank scrubs, A fast-forwards, B skips),
-- then the clock. `rate` = 0 pauses the roll and leaves the crank working.
function Roll:update()
    local dt = self.rate
    if self.controls and pd then
        if pd.buttonJustPressed(pd.kButtonB) then self:skip() end
        if pd.buttonIsPressed(pd.kButtonA) then dt = dt * self.fast end
        local crank = pd.getCrankChange()
        if crank ~= 0 then dt = dt + crank * self.crankFrames end
    end
    return self:advance(dt)
end

local function prefix(part, n)
    local cache = part.pre
    if not cache then cache = {}; part.pre = cache end
    local s = cache[n]
    if not s then s = uprefix(part.text, n); cache[n] = s end
    return s
end

local function paintText(self, row, y, off, grow, budget)
    local parts = row.parts
    for i = 1, #parts do
        if budget <= 0 then break end
        local part = parts[i]
        local text = part.text
        if budget < part.n then text = prefix(part, budget) end
        budget = budget - part.n
        part.font:drawText(text, part.x + floor(off * part.side), y + part.dy)
    end
    local r, d, dv = row.rules, row.dots, row.divider
    if not (r or d or dv) then return end
    gfx.setColor(self.ink)
    if r then
        local len = floor(r.len * grow)
        if len > 0 then
            gfx.fillRect(r.left - len, y + r.cy, len, 1)
            gfx.fillRect(r.right, y + r.cy, len, 1)
        end
    end
    if d then
        for x = d.x1, d.x1 + floor((d.x2 - d.x1) * grow), 3 do gfx.fillRect(x, y + d.cy, 1, 1) end
    end
    if dv then
        local half = floor(dv.half * grow)
        if half > 0 then gfx.fillRect(dv.cx - half, y + dv.cy, half * 2 + 1, 1) end
        gfx.fillRect(dv.cx - 1, y + dv.cy - 2, 3, 5)
        gfx.fillRect(dv.cx - 2, y + dv.cy - 1, 5, 3)
    end
end

-- p: reveal progress 0..1, a: alpha 0..1.
local function drawRow(self, row, y, p, a)
    if a <= 0 then return end
    local reveal = row.reveal
    local off, grow, budget = 0, 1, row.chars
    if reveal == "slide" then
        grow = outCubic(p)
        off = (1 - grow) * SLIDE
    elseif reveal == "type" then
        grow = p
        budget = floor(p * row.chars)
    end
    if row.image then
        local img = row.img
        if not img then return end
        local x = row.x + floor(off * row.side)
        gfx.setImageDrawMode(gfx.kDrawModeCopy)
        if a >= 1 then img:draw(x, y) else img:drawFaded(x, y, a, BAYER) end
        gfx.setImageDrawMode(self.inkMode)
    elseif a >= 1 then
        paintText(self, row, y, off, grow, budget)
    else
        local s = self.scratch
        gfx.pushContext(s)
        gfx.clear(gfx.kColorClear)
        gfx.setImageDrawMode(self.inkMode)
        paintText(self, row, 0, off, grow, budget)
        gfx.popContext()
        s:drawFaded(0, y, a, BAYER)
    end
end

local function drawRoll(self, seg)
    local s = floor(scrollAt(seg, self.t) + 0.5)
    local rows = seg.rows
    for i = firstVisible(rows, -s), #rows do
        local row = rows[i]
        local y = s + row.y
        if y >= H then break end
        drawRow(self, row, y, rollP(self, y), edgeAlpha(self, y, row.h))
    end
end

local function drawCard(self, seg)
    local t, rows = self.t, seg.rows
    for i = 1, #rows do
        local row = rows[i]
        local p = cardP(seg, row, t)
        drawRow(self, row, seg.top + row.y, p, cardAlpha(seg, row, t, p))
    end
end

function Roll:draw()
    if not self._device then return end
    local bg = self.background
    if bg then bg(self) elseif self.clear then gfx.clear(self.paper) end
    gfx.setImageDrawMode(self.inkMode)
    local seg = segmentAt(self, self.t)
    if seg.kind == "roll" then drawRoll(self, seg) else drawCard(self, seg) end
    gfx.setImageDrawMode(gfx.kDrawModeCopy)
    gfx.setColor(gfx.kColorBlack)
end

return Credits
