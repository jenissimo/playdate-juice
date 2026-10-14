-- lint_comic.lua -- check a Panels comicData table before the simulator does.
--
-- Panels ignores every key it does not know, so a misspelt `scrolltrigger`,
-- or an AUTO-only key in a MANUAL sequence, is a feature that silently never
-- happens; a wrong image path is a nil that surfaces as a crash somewhere
-- else. This runs the data file under host Lua with stand-ins for `playdate`
-- and `Panels` (constant tables are strict, so `Panels.Input.AA` fails at its
-- own line), then walks the table against every property of Panels 2.2,
-- including the ones only the source documents.
--
--   lua lint_comic.lua Source/comicData.lua [--source Source] [--var comicData]
--                      [--images images/] [--audio audio/] [--no-hints] [--cutscene]
--
-- --source  the game's Source folder (default: the data file's folder); file
--           checks are relative to it, as are `import`s inside the data file
-- --cutscene the comic runs through Panels.startCutscene: background colour
--           changes between sequences are errors (they crash there)
-- Exit status 1 when there are errors.
--
-- Also a module: `Lint.check(comicData, opts) -> report` is what the repo's
-- host tests drive (test/comics_lint_test.lua).

local Lint = {}

-- ---------------------------------------------------------------- constants
-- Values copied from Panels 2.2 (modules/*.lua) and the Playdate SDK, so a
-- file that writes playdate.kButtonA where Panels.Input.A is meant still passes.

local BUTTON = { LEFT = 1, RIGHT = 2, UP = 4, DOWN = 8, B = 16, A = 32 }
local COLOR = { BLACK = 0, WHITE = 1, CLEAR = 2 }
local VARIANT = { NORMAL = 0, BOLD = 1, ITALIC = 2 }
local ALIGN = { LEFT = 0, RIGHT = 1, CENTER = 2 }

local P = {
    Input = { A = BUTTON.A, B = BUTTON.B, UP = BUTTON.UP, DOWN = BUTTON.DOWN,
              LEFT = BUTTON.LEFT, RIGHT = BUTTON.RIGHT },
    Color = { WHITE = COLOR.WHITE, BLACK = COLOR.BLACK, CLEAR = COLOR.CLEAR },
    Effect = { SHAKE_UNISON = 1, SHAKE_INDIVIDUAL = 2, BLINK = 3, TYPE_ON = 4,
               SHAKE = 2, SHAKE_LAYER = 2 },
    ScrollType = { AUTO = 1, MANUAL = 2 },
    ScrollAxis = { VERTICAL = 1, HORIZONTAL = 2 },
    ScrollDirection = { TOP_DOWN = 1, TOP_TO_BOTTOM = 1, BOTTOM_UP = 2, BOTTOM_TO_TOP = 2,
                        L_TO_R = 3, LEFT_TO_RIGHT = 3, R_TO_L = 4, RIGHT_TO_LEFT = 4, NONE = 5 },
    Font = { NORMAL = VARIANT.NORMAL, BOLD = VARIANT.BOLD, ITALIC = VARIANT.ITALIC },
    TextAlignment = { LEFT = ALIGN.LEFT, RIGHT = ALIGN.RIGHT, CENTER = ALIGN.CENTER },
    ControlSize = { LARGE = 40, MEDIUM = 30, SMALL = 20 },
}
P.Audio = { TypingSound = { DEFAULT = "default", NONE = "none" } }
Lint.Panels = P

local function names(t)
    local out = {}
    for k, v in pairs(t) do out[v] = out[v] or k end
    return out
end
local INPUT_NAME, COLOR_NAME = names(P.Input), names(P.Color)
local AXIS_NAME, TYPE_NAME = names(P.ScrollAxis), names(P.ScrollType)
local DIR_NAME = { [1] = "TOP_DOWN", [2] = "BOTTOM_UP", [3] = "LEFT_TO_RIGHT", [4] = "RIGHT_TO_LEFT", [5] = "NONE" }
local SIZE_NAME, ALIGN_NAME = names(P.ControlSize), names(P.TextAlignment)

local EASINGS = { linear = true }
for _, base in ipairs({ "Quad", "Cubic", "Quart", "Quint", "Sine", "Expo", "Circ", "Elastic", "Back", "Bounce" }) do
    for _, pre in ipairs({ "in", "out", "inOut", "outIn" }) do EASINGS[pre .. base] = true end
end

-- ------------------------------------------------------------------ schema
-- key -> type name; every table kind lists every key Panels reads.

local SCHEMA = {
    sequence = {
        panels = "panels", title = "string", axis = "axis", direction = "direction",
        scrollType = "scrollType", autoAdvanceWithCrank = "boolean", autoAdvanceTicks = "count",
        audio = "seqAudio", advanceControl = "input", advanceControlSize = "controlSize",
        showAdvanceControl = "boolean", advanceControlPosition = "point",
        advanceControls = "advanceControls", showAdvanceControls = "boolean",
        backgroundColor = "color", foregroundColor = "color", endSequence = "boolean",
        rapidAdvance = "boolean", transitionDuration = "ms", transitionEase = "function",
        delay = "ms", defaultFrame = "frame", font = "font", fontFamily = "fontFamily",
        backControl = "input", preventBacktracking = "boolean", id = "string", nextSequence = "target",
    },
    panel = {
        layers = "layers", frame = "frame", borderless = "boolean", backgroundColor = "color",
        parallaxDistance = "number", effect = "panelEffect", audio = "panelAudio",
        font = "font", fontFamily = "fontFamily", lineHeightAdjustment = "number",
        color = "color", invertTextColor = "boolean", transitionOffset = "number",
        choiceList = "choiceList", panels = "subPanels",
        advanceControl = "input", showAdvanceControl = "boolean", advanceControlSize = "controlSize",
        advanceControlPosition = "point", advanceControlPositions = "points",
        advanceControlSequence = "inputs", advanceDelay = "ms", preventBacktracking = "boolean",
        autoAdvance = "ms", backControl = "input",
        renderFunction = "function", updateFunction = "function", setupFunction = "function",
        resetFunction = "function", advanceFunction = "function", targetSequenceFunction = "function",
        name = "any",
    },
    layer = {
        image = "image", images = "imageList", imageTable = "imageTable", text = "string", img = "any",
        x = "number", y = "number", parallax = "unit", opacity = "unit", animate = "animate",
        exit = "animate", effect = "layerEffect", transitionOffset = "number", pixelLock = "count",
        renderCondition = "renderCondition", stencil = "image", name = "any", visible = "boolean",
        manuallySetImageIndex = "boolean", advanceControl = "input",
        scrollTrigger = "trigger", trigger = "input", delay = "ms", reduceFlashingDelay = "ms",
        startDelay = "ms", loop = "boolean",
        background = "color", font = "font", fontFamily = "fontFamily", color = "color",
        invertTextColor = "boolean", rect = "rect", lineHeightAdjustment = "number",
        alignment = "alignment", border = "number", borderRadius = "number", margin = "margins",
    },
    frame = { x = "number", y = "number", width = "number", height = "number", margin = "number", gap = "number" },
    seqAudio = { file = "audio", loop = "boolean", continuePrevious = "boolean", volume = "unit" },
    panelAudio = { file = "audio", loop = "boolean", scrollTrigger = "trigger", pan = "unit", volume = "unit",
                   triggerSequence = "inputs", repeats = "count" },
    animAudio = { file = "audio", delay = "ms", loop = "boolean" },
    animate = { x = "number", y = "number", opacity = "unit", scrollTrigger = "trigger", autoStart = "boolean",
                trigger = "input", triggerSequence = "inputs", delay = "ms", duration = "ms",
                ease = "function", audio = "animAudio" },
    point = { x = "number", y = "number", delay = "ms" },
    advanceControl = { input = "input", target = "target", x = "number", y = "number", anchor = "boolean" },
    panelEffect = { type = "any", strength = "number" },
    layerEffect = { type = "any", strength = "number", durations = "durations", delay = "ms",
                    reduceFlashingDurations = "durations", audio = "animAudio", duration = "ms",
                    scrollTrigger = "trigger" },
    durations = { on = "ms", off = "ms" },
    renderCondition = { var = "string", value = "any", valueNot = "any" },
    rect = { width = "number", height = "number" },
    margins = { top = "number", right = "number", bottom = "number", left = "number" },
    choiceList = { buttons = "buttons", x = "number", y = "number", width = "number", height = "number",
                   color = "color", borderRadius = "number", spacing = "number", fontFamily = "fontFamily",
                   onSelectionChange = "function", buttonRenderFunction = "function" },
    button = { label = "string", target = "target", var = "choiceVar", selected = "boolean" },
    choiceVar = { key = "string", value = "any" },
}

local AUTO_ONLY_PANEL = { "advanceControl", "showAdvanceControl", "advanceControlSize",
    "advanceControlPosition", "advanceControlPositions", "advanceControlSequence", "advanceDelay",
    "preventBacktracking", "autoAdvance", "advanceFunction", "backControl" }
local TEXT_ONLY = { "background", "font", "fontFamily", "color", "invertTextColor", "rect",
    "lineHeightAdjustment", "alignment", "border", "borderRadius", "margin" }
local TABLE_ONLY = { "scrollTrigger", "trigger", "delay", "reduceFlashingDelay", "startDelay", "loop" }
local IMAGES_ONLY = { "manuallySetImageIndex", "advanceControl" }

-- ------------------------------------------------------------------- report

local function editDistance(a, b)
    local la, lb = #a, #b
    if math.abs(la - lb) > 2 then return 3 end
    local prev, cur = {}, {}
    for j = 0, lb do prev[j] = j end
    for i = 1, la do
        cur[0] = i
        for j = 1, lb do
            local cost = a:sub(i, i) == b:sub(j, j) and 0 or 1
            cur[j] = math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        end
        prev, cur = cur, prev
    end
    return prev[lb]
end

local function suggest(key, known)
    local best, bestD = nil, 3
    local lk = key:lower()
    for k in pairs(known) do
        local d = (k:lower() == lk) and 0 or editDistance(key, k)
        if d < bestD then best, bestD = k, d end
    end
    return best
end

local function newReport()
    local r = { items = {}, errors = 0, warnings = 0, hints = 0,
                stats = { sequences = 0, panels = 0, layers = 0, words = 0 } }
    function r.add(level, where, msg)
        r.items[#r.items + 1] = { level = level, where = where, msg = msg }
        if level == "error" then r.errors = r.errors + 1
        elseif level == "warn" then r.warnings = r.warnings + 1
        else r.hints = r.hints + 1 end
    end
    return r
end

-- -------------------------------------------------------------- the walker

local Walker = {}
Walker.__index = Walker

local STUB = {}       -- values that came out of a stand-in; never judged

local function isStub(v) return type(v) == "table" and getmetatable(v) == STUB end

function Walker:err(where, msg) self.report.add("error", where, msg) end
function Walker:warn(where, msg) self.report.add("warn", where, msg) end
function Walker:hint(where, msg) if self.hints then self.report.add("hint", where, msg) end end

local function at(where, key) return where .. " › " .. key end

function Walker:file(where, kind, path)
    if not self.files or type(path) ~= "string" then return end
    -- The SDK finds an image with or without ".png" (checked in the 3.1
    -- simulator), so that is only stripped for the lookup. Panels strips a
    -- ".fnt" itself but prints a complaint on every load.
    if path:match("%.fnt$") then
        self:hint(where, ("'%s': Panels strips .fnt but prints a warning each time it loads it"):format(path))
    end
    path = path:gsub("%.png$", ""):gsub("%.gif$", ""):gsub("%.fnt$", "")
    local exists = self.files
    if kind == "image" then
        local base = self.imageFolder .. path
        if not (exists(base .. ".png") or exists(base .. ".gif")) then
            self:err(where, ("image '%s' not found (looked for %s.png/.gif)"):format(path, base))
        end
    elseif kind == "imageTable" then
        local base = self.imageFolder .. path
        if not (exists(base .. "-1.png") or exists(base .. ".gif") or self.globTable(base)) then
            self:err(where, ("image table '%s' not found (%s-table-W-H.png, %s-1.png… or .gif)"):format(path, base, base))
        end
    elseif kind == "audio" then
        local base = self.audioFolder .. path:gsub("%.wav$", "")
        if not (exists(base .. ".wav") or exists(base .. ".mp3") or exists(base .. ".aif") or exists(base .. ".aiff")) then
            self:err(where, ("audio '%s' not found (looked for %s.wav/.mp3/.aif)"):format(path, base))
        end
    elseif kind == "font" then
        if not exists(self.source .. path .. ".fnt") then
            self:err(where, ("font '%s' not found (%s.fnt)"):format(path, self.source .. path))
        end
    end
end

function Walker:value(where, typ, v)
    if v == nil or isStub(v) or typ == "any" then return end
    local t = type(v)
    local function want(what) self:err(where, ("expected %s, got %s %s"):format(what, t, tostring(v))) end

    if typ == "string" or typ == "boolean" or typ == "function" then
        if t ~= typ then want("a " .. typ) end
    elseif typ == "number" then
        if t ~= "number" then want("a number") end
    elseif typ == "ms" then
        if t ~= "number" then want("milliseconds (a number)")
        elseif v < 0 then self:err(where, "a negative duration")
        elseif v > 0 and v < 10 then self:warn(where, ("%s ms — Panels times are milliseconds, not seconds or frames"):format(v)) end
    elseif typ == "count" then
        if math.type(v) ~= "integer" or v < 0 then want("a whole number") end
    elseif typ == "unit" then
        if t ~= "number" then want("a number 0..1")
        elseif v < 0 or v > 1 then self:warn(where, ("%s is outside 0..1"):format(v)) end
    elseif typ == "trigger" then
        if t ~= "number" then want("a scroll point 0..1")
        elseif v < 0 or v > 1 then self:err(where, ("scroll point %s never happens: scroll runs 0..1"):format(v)) end
    elseif typ == "input" then
        if not INPUT_NAME[v] then want("a Panels.Input value") end
    elseif typ == "inputs" then
        if t ~= "table" then want("a list of Panels.Input values")
        else for i, b in ipairs(v) do self:value(at(where, i), "input", b) end end
    elseif typ == "color" then
        if not COLOR_NAME[v] then want("a Panels.Color value") end
    elseif typ == "axis" then
        if not AXIS_NAME[v] then want("a Panels.ScrollAxis value") end
    elseif typ == "direction" then
        if not DIR_NAME[v] then want("a Panels.ScrollDirection value") end
    elseif typ == "scrollType" then
        if not TYPE_NAME[v] then want("a Panels.ScrollType value") end
    elseif typ == "controlSize" then
        if not SIZE_NAME[v] then want("a Panels.ControlSize value") end
    elseif typ == "alignment" then
        if not ALIGN_NAME[v] then want("a Panels.TextAlignment value") end
    elseif typ == "target" then
        if t ~= "string" and t ~= "number" then want("a sequence id or index")
        else self.targets[#self.targets + 1] = { where = where, target = v } end
    elseif typ == "image" then
        if t ~= "string" then want("an image path") else self:file(where, "image", v) end
    elseif typ == "imageList" then
        if t ~= "table" or #v == 0 then want("a list of image paths")
        else for i, p in ipairs(v) do self:value(at(where, i), "image", p) end end
    elseif typ == "imageTable" then
        if t ~= "string" then want("an image table path") else self:file(where, "imageTable", v) end
    elseif typ == "audio" then
        if t ~= "string" then want("an audio path") else self:file(where, "audio", v) end
    elseif typ == "font" then
        if t ~= "string" and t ~= "userdata" then want("a font path")
        elseif t == "string" then self:file(where, "font", v) end
    elseif typ == "fontFamily" then
        if t ~= "table" then want("a font family table") else
            for k, p in pairs(v) do
                if not (k == VARIANT.NORMAL or k == VARIANT.BOLD or k == VARIANT.ITALIC) then
                    self:err(at(where, tostring(k)), "font family keys are Panels.Font.NORMAL/BOLD/ITALIC")
                end
                self:value(at(where, tostring(k)), "font", p)
            end
        end
    elseif typ == "panels" then
        -- walked by the caller
    elseif typ == "layers" then
        if t ~= "table" then want("a list of layers") end
    elseif typ == "points" then
        if t ~= "table" then want("a list of {x, y, delay}")
        else for i, p in ipairs(v) do self:table(at(where, i), "point", p) end end
    elseif typ == "advanceControls" then
        if t ~= "table" then want("a list of {input, target, x, y}") else
            for i, c in ipairs(v) do
                self:table(at(where, i), "advanceControl", c)
                if type(c) == "table" and c.input == nil then self:err(at(where, i), "advance control without input") end
            end
        end
    elseif typ == "buttons" then
        if t ~= "table" or #v == 0 then want("a list of buttons") else
            for i, b in ipairs(v) do
                self:table(at(where, i), "button", b)
                if type(b) == "table" and b.label == nil then self:err(at(where, i), "a button needs a label") end
            end
        end
    elseif typ == "subPanels" then
        if t ~= "table" then want("a list of panels")
        else for i, p in ipairs(v) do self:panel(at(where, "sub-panel " .. i), p, self.seqType) end end
    elseif SCHEMA[typ] then
        self:table(where, typ, v)
    end
end

-- Known keys get their type checked; unknown ones are the silent typos.
function Walker:table(where, kind, t)
    if isStub(t) then return end
    if type(t) ~= "table" then
        self:err(where, ("expected a table (%s), got %s"):format(kind, type(t)))
        return
    end
    local schema = SCHEMA[kind]
    for k, v in pairs(t) do
        if type(k) == "string" then
            local typ = schema[k]
            if typ then
                self:value(at(where, k), typ, v)
            else
                local s = suggest(k, schema)
                self:warn(where, ("unknown key '%s'%s — Panels ignores it"):format(k, s and (", did you mean '" .. s .. "'?") or ""))
            end
        end
    end
end

local function has(t, keys)
    for _, k in ipairs(keys) do if t[k] ~= nil then return k end end
end

function Walker:layer(where, l, seqType, panel)
    if isStub(l) then return end
    if type(l) ~= "table" then self:err(where, "a layer must be a table"); return end
    self.report.stats.layers = self.report.stats.layers + 1
    self:table(where, "layer", l)

    local kinds = {}
    for _, k in ipairs({ "image", "images", "imageTable", "text", "img" }) do
        if l[k] ~= nil then kinds[#kinds + 1] = k end
    end
    if #kinds == 0 then
        self:err(where, "a layer needs one of image, images, imageTable, text (or img)")
    elseif #kinds > 1 then
        self:err(where, "one layer, one kind: " .. table.concat(kinds, " + ") .. " — split it into layers")
    end
    local kind = kinds[1]

    if kind ~= "text" then
        local k = has(l, TEXT_ONLY)
        if k and kind then self:warn(at(where, k), "text-layer property on a " .. kind .. " layer — ignored") end
    end
    if kind ~= "imageTable" then
        local k = has(l, TABLE_ONLY)
        if k and kind then self:warn(at(where, k), "imageTable property on a " .. kind .. " layer — ignored (did you mean animate." .. k .. "?)") end
    end
    if kind ~= "images" then
        local k = has(l, IMAGES_ONLY)
        if k and kind then self:warn(at(where, k), "multi-image property on a " .. kind .. " layer — ignored") end
    end
    if l.stencil ~= nil and kind ~= "image" and kind ~= "images" then
        self:warn(at(where, "stencil"), "stencil works on image layers")
    end
    if l.exit ~= nil and seqType ~= P.ScrollType.AUTO then
        self:warn(at(where, "exit"), "exit animations only run in AUTO sequences")
    end

    local e = l.effect
    if type(e) == "table" and not isStub(e) then
        local ew = at(where, "effect")
        if e.type == P.Effect.BLINK then
            if type(e.durations) ~= "table" or e.durations.on == nil or e.durations.off == nil then
                self:err(ew, "BLINK needs durations = { on = ms, off = ms }")
            end
            if e.reduceFlashingDurations == nil then
                self:hint(ew, "BLINK without reduceFlashingDurations ignores the Reduce Flashing setting")
            end
        elseif e.type == P.Effect.TYPE_ON then
            if kind ~= "text" then self:err(ew, "TYPE_ON works on text layers only") end
        elseif e.type == P.Effect.SHAKE then
            -- fine
        elseif e.type == P.Effect.SHAKE_UNISON then
            self:err(ew, "SHAKE_UNISON is a PANEL effect; a layer takes Panels.Effect.SHAKE")
        else
            self:err(ew, "effect.type must be Panels.Effect.SHAKE, BLINK or TYPE_ON")
        end
    end

    for _, which in ipairs({ "animate", "exit" }) do
        local a = l[which]
        if type(a) == "table" and not isStub(a) then
            if a.x == nil and a.y == nil and a.opacity == nil then
                self:warn(at(where, which), "animates nothing: give it x, y or opacity")
            end
            if a.trigger ~= nil and seqType == P.ScrollType.MANUAL then
                self:hint(at(where, which), "a button-triggered animation in a MANUAL sequence can be scrolled past unseen")
            end
            if a.opacity ~= nil then self.opacityLayers = self.opacityLayers + 1 end
        end
    end
    if kind == "imageTable" and type(l.delay) == "number" and l.delay < 100 and l.reduceFlashingDelay == nil then
        self:hint(where, "a fast imageTable without reduceFlashingDelay ignores the Reduce Flashing setting")
    end
    if kind == "text" and type(l.text) == "string" then
        local words = select(2, l.text:gsub("%S+", ""))
        self.report.stats.words = self.report.stats.words + words
        self.words[panel] = (self.words[panel] or 0) + words
    end
end

function Walker:panel(where, p, seqType)
    if isStub(p) then return end
    if type(p) ~= "table" then self:err(where, "a panel must be a table"); return end
    self.report.stats.panels = self.report.stats.panels + 1
    self:table(where, "panel", p)
    if seqType ~= P.ScrollType.AUTO then
        local k = has(p, AUTO_ONLY_PANEL)
        if k then self:warn(at(where, k), "AUTO-only property in a MANUAL sequence — ignored") end
    end
    if p.layers == nil and p.renderFunction == nil then
        self:err(where, "a panel needs layers (or a renderFunction)")
    end
    local e = p.effect
    if type(e) == "table" and not isStub(e) and e.type ~= P.Effect.SHAKE_UNISON and e.type ~= P.Effect.SHAKE_INDIVIDUAL then
        self:err(at(where, "effect"), "a panel effect is SHAKE_UNISON or SHAKE_INDIVIDUAL (BLINK and TYPE_ON go on layers)")
    end
    local f = p.frame
    if type(f) == "table" and not isStub(f) then
        if type(f.width) == "number" and f.width < 1 or type(f.height) == "number" and f.height < 1 then
            self:err(at(where, "frame"), "a frame needs a positive width and height")
        end
    end
    if type(p.audio) == "table" and p.audio.file == nil and not isStub(p.audio) then
        self:err(at(where, "audio"), "audio needs a file")
    end
    self.opacityLayers = 0
    if type(p.layers) == "table" and not isStub(p.layers) then
        for i, l in ipairs(p.layers) do self:layer(at(where, "layer " .. i), l, seqType, p) end
    end
    if self.opacityLayers > 3 then
        self:hint(where, self.opacityLayers .. " opacity animations in one panel: each is a dithered redraw every frame")
    end
    if (self.words[p] or 0) > 30 then
        self:hint(where, ("%d words on one panel — 400×240 holds 20–30 before the art disappears; split it"):format(self.words[p]))
    end
end

function Walker:sequence(i, s, nextBg)
    local title = type(s) == "table" and type(s.title) == "string" and (" '" .. s.title .. "'") or ""
    local where = "seq " .. i .. title
    if type(s) ~= "table" or isStub(s) then self:err(where, "a sequence must be a table"); return end
    self.report.stats.sequences = self.report.stats.sequences + 1
    self:table(where, "sequence", s)
    local seqType = s.scrollType or P.ScrollType.MANUAL
    self.seqType = seqType

    if type(s.panels) ~= "table" or #s.panels == 0 then
        self:err(where, "a sequence needs a non-empty panels list")
        return
    end
    if seqType ~= P.ScrollType.AUTO then
        for _, k in ipairs({ "rapidAdvance", "autoAdvanceWithCrank" }) do
            if s[k] ~= nil then self:warn(at(where, k), "AUTO-only sequence property in a MANUAL sequence — ignored") end
        end
    end
    if s.direction == P.ScrollDirection.NONE and s.advanceControl == nil and s.advanceControls == nil then
        self:warn(where, "direction = NONE has no default advance button: set advanceControl (and showAdvanceControl = false with autoAdvance)")
    end
    if s.direction == P.ScrollDirection.NONE and seqType ~= P.ScrollType.AUTO then
        self:warn(where, "direction = NONE in a MANUAL sequence: panels cannot be scrolled to — use scrollType = AUTO")
    end
    if type(s.audio) == "table" and not isStub(s.audio) and s.audio.continuePrevious and s.audio.file == nil then
        self:hint(at(where, "audio"), "continuePrevious without file: a chapter-menu jump here starts in silence")
    end
    if type(s.id) == "string" then
        if self.ids[s.id] then self:err(at(where, "id"), ("id '%s' is also used by seq %d"):format(s.id, self.ids[s.id])) end
        self.ids[s.id] = i
    end

    local sizes, silent, timed = {}, 0, 0
    for j, p in ipairs(s.panels) do
        self:panel(at(where, "panel " .. j), p, seqType)
        if type(p) == "table" and not isStub(p) then
            local f = p.frame or {}
            sizes[tostring(f.width) .. "x" .. tostring(f.height)] = true
            if (self.words[p] or 0) == 0 then silent = silent + 1 end
            if p.autoAdvance then timed = timed + 1 end
        end
    end
    local n, distinct = #s.panels, 0
    for _ in pairs(sizes) do distinct = distinct + 1 end
    if n >= 6 and distinct == 1 then
        self:hint(where, "every panel is the same size: panel length is time — vary it to pace the beats")
    end
    if n >= 5 and silent == 0 then
        self:hint(where, "no silent panel: a panel without words is where the reader lingers")
    end
    if n >= 3 and timed == n then
        self:hint(where, "every panel auto-advances: the reader never sets the pace (fine for a cutscene beat)")
    end

    local bg = s.backgroundColor or P.Color.WHITE
    if nextBg ~= nil and nextBg ~= bg then
        local msg = ("background %s → %s at the next sequence: crashes Panels.startCutscene (Panels.lua:971, transitionFader); fine with Panels.start")
            :format(COLOR_NAME[bg] or tostring(bg), COLOR_NAME[nextBg] or tostring(nextBg))
        if self.cutscene then self:err(where, msg) else self:warn(where, msg) end
    end
end

--- Checks a comicData table. opts:
---   files = fn(path) -> bool (nil skips file checks), globTable = fn(base) -> bool,
---   source = "Source/", imageFolder = "Source/images/", audioFolder = "Source/audio/",
---   hints = true, cutscene = false
function Lint.check(data, opts)
    opts = opts or {}
    local w = setmetatable({
        report = newReport(), hints = opts.hints ~= false, cutscene = opts.cutscene,
        files = opts.files, globTable = opts.globTable or function() return false end,
        source = opts.source or "", imageFolder = opts.imageFolder or "images/",
        audioFolder = opts.audioFolder or "audio/",
        ids = {}, targets = {}, opacityLayers = 0, words = {},
    }, Walker)
    if type(data) ~= "table" or #data == 0 then
        w:err("comicData", "must be a non-empty list of sequences")
        return w.report
    end
    for k in pairs(data) do
        if type(k) ~= "number" then
            w:err("comicData", ("top-level key '%s': comicData is a plain list of sequences"):format(tostring(k)))
        end
    end
    for i, s in ipairs(data) do
        local nxt = data[i + 1]
        local nextBg = type(nxt) == "table" and not isStub(nxt) and (nxt.backgroundColor or P.Color.WHITE) or nil
        w:sequence(i, s, nextBg)
    end
    for _, t in ipairs(w.targets) do
        if type(t.target) == "number" then
            if t.target < 1 or t.target > #data then
                w:err(t.where, ("sequence index %d is out of range 1..%d"):format(t.target, #data))
            end
        elseif not w.ids[t.target] then
            local s = suggest(t.target, w.ids)
            w:err(t.where, ("no sequence has id '%s'%s"):format(t.target, s and (", did you mean '" .. s .. "'?") or ""))
        end
    end
    return w.report
end

-- ----------------------------------------------------------- loading a file
-- Stand-ins: just enough of `playdate` and `Panels` for a data file to run.
-- Anything else it touches at load time (a juice module, an image.new) is a
-- stub that swallows every use; values made from stubs are never judged.

local function makeStub(name, seen)
    local stub = setmetatable({}, STUB)
    STUB.__index = function(_, k) if type(k) == "string" then return stub end end
    STUB.__call = function() return stub end
    for _, mm in ipairs({ "__add", "__sub", "__mul", "__div", "__mod", "__pow", "__unm",
                          "__idiv", "__concat", "__band", "__bor", "__bxor", "__shl", "__shr", "__bnot" }) do
        STUB[mm] = function() return stub end
    end
    STUB.__lt = function() return false end
    STUB.__le = function() return false end
    STUB.__len = function() return 0 end
    STUB.__tostring = function() return "<stub>" end
    return stub
end

local function strict(t, name)
    return setmetatable(t, { __index = function(_, k)
        error(("%s.%s does not exist"):format(name, tostring(k)), 2)
    end })
end

function Lint.environment(source, onLog)
    local stub = makeStub()
    local stubbed = {}
    local captured = nil

    local panels = { vars = {}, persistentVars = {}, credits = {} }
    for k, v in pairs(P) do panels[k] = v end
    for _, k in ipairs({ "Input", "Color", "Effect", "ScrollType", "ScrollAxis", "ScrollDirection",
                         "Font", "TextAlignment", "ControlSize" }) do
        local copy = {}
        for kk, vv in pairs(P[k]) do copy[kk] = vv end
        panels[k] = strict(copy, "Panels." .. k)
    end
    panels.Settings = { path = "libraries/panels/", imageFolder = "images/", audioFolder = "audio/" }
    panels.start = function(d) captured = d end
    panels.startCutscene = function(d) captured = d end
    panels.renderLayerInPanel = function() end
    panels.update = function() end
    panels.haltCutscene = function() end

    local ease = {}
    for k in pairs(EASINGS) do ease[k] = function(t, b, c, d) return b end end
    local graphics = setmetatable({
        kColorBlack = COLOR.BLACK, kColorWhite = COLOR.WHITE, kColorClear = COLOR.CLEAR, kColorXOR = 3,
        font = setmetatable({ kVariantNormal = VARIANT.NORMAL, kVariantBold = VARIANT.BOLD,
                              kVariantItalic = VARIANT.ITALIC }, { __index = function() return stub end }),
    }, { __index = function() return stub end })
    local playdate = setmetatable({
        kButtonLeft = BUTTON.LEFT, kButtonRight = BUTTON.RIGHT, kButtonUp = BUTTON.UP,
        kButtonDown = BUTTON.DOWN, kButtonB = BUTTON.B, kButtonA = BUTTON.A,
        graphics = graphics,
        easingFunctions = strict(ease, "playdate.easingFunctions"),
    }, { __index = function() return stub end })

    local env
    env = setmetatable({
        playdate = playdate, Panels = panels,
        kTextAlignment = { left = ALIGN.LEFT, right = ALIGN.RIGHT, center = ALIGN.CENTER },
        import = function(path)
            if path:match("^CoreLibs/") or path:match("[Pp]anels/Panels$") then return end
            local file = source .. path:gsub("%.lua$", "") .. ".lua"
            local chunk = loadfile(file, "t", env)
            if not chunk then
                if onLog then onLog("import '" .. path .. "' not found at " .. file .. " — skipped") end
                return
            end
            chunk()
        end,
    }, { __index = function(_, k)
        local v = _G[k]
        if v ~= nil then return v end
        if not stubbed[k] then
            stubbed[k] = true
            if onLog then onLog("global '" .. tostring(k) .. "' is stubbed (not defined while loading)") end
        end
        return stub
    end })
    return env, function() return captured end
end

-- Playdate Lua has `+=` and friends; host Lua cannot parse them. Functions in
-- a data file are never run here, so turning `a += b` into `a = a + b` only
-- has to parse, not to keep precedence. Comments are left alone, which is
-- also what keeps a `--=====` banner from being read as `-=`.
function Lint.desugar(src)
    return (src:gsub("[^\n]+", function(line)
        local code, comment = line:match("^(.-)(%-%-.*)$")
        if not code then code, comment = line, "" end
        code = code:gsub("([%w_][%w_%.]*)%s*([%+%-%*/%%])=([^=])", "%1 = %1 %2%3")
        return code .. comment
    end))
end

function Lint.load(path, source, var, onLog)
    local f = io.open(path, "rb")
    if not f then return nil, "cannot open " .. path end
    local src = f:read("a")
    f:close()
    return Lint.loadString(src, path, source, var, onLog)
end

-- Runs data-file source in the stand-in environment and finds the comic:
-- --var, else what it handed Panels.start/startCutscene, else what it
-- returned, else a global comicData, else any global list of sequences.
function Lint.loadString(src, name, source, var, onLog)
    local env, captured = Lint.environment(source or "", onLog)
    local chunk, err = load(Lint.desugar(src), "@" .. name, "t", env)
    if not chunk then return nil, err end
    local ok, ret = pcall(chunk)
    if not ok then return nil, ret end
    local data = (var and rawget(env, var)) or captured() or (type(ret) == "table" and ret) or rawget(env, "comicData")
    if not data then
        for k, v in pairs(env) do
            -- rawget: the stand-ins answer every index, so playdate[1].panels "exists"
            local first = type(v) == "table" and rawget(v, 1)
            if type(first) == "table" and not isStub(first) and rawget(first, "panels") then
                data = v
                if onLog then onLog("using global '" .. k .. "' as the comic data") end
                break
            end
        end
    end
    if not data then return nil, "no comic data found: return it, name it comicData, or pass --var" end
    return data, nil, env
end

-- ---------------------------------------------------------------- the CLI

local function fileExists(p)
    local f = io.open(p, "rb")
    if f then f:close(); return true end
    return false
end

local function listDir(dir)
    local windows = package.config:sub(1, 1) == "\\"
    local cmd = windows and ('dir /b "' .. dir:gsub("/", "\\") .. '" 2>nul') or ("ls -1 '" .. dir .. "' 2>/dev/null")
    local p = io.popen(cmd)
    if not p then return nil end
    local out = {}
    for line in p:lines() do out[#out + 1] = line end
    p:close()
    return out
end

function Lint.main(argv)
    local path, opts = nil, { hints = true }
    local i = 1
    while i <= #argv do
        local a = argv[i]
        if a == "--source" then opts.source = argv[i + 1]; i = i + 1
        elseif a == "--var" then opts.var = argv[i + 1]; i = i + 1
        elseif a == "--images" then opts.images = argv[i + 1]; i = i + 1
        elseif a == "--audio" then opts.audio = argv[i + 1]; i = i + 1
        elseif a == "--no-hints" then opts.hints = false
        elseif a == "--cutscene" then opts.cutscene = true
        elseif a == "-h" or a == "--help" then path = nil; break
        else path = a end
        i = i + 1
    end
    if not path then
        print("usage: lua lint_comic.lua <comicData.lua> [--source DIR] [--var NAME] [--images DIR] [--audio DIR] [--no-hints] [--cutscene]")
        return 2
    end
    local function slash(d) d = d:gsub("\\", "/"); if d ~= "" and d:sub(-1) ~= "/" then d = d .. "/" end; return d end
    local source = slash(opts.source or (path:gsub("\\", "/"):match("^(.*)/") or "."))
    local notes = {}
    local data, err, env = Lint.load(path, source, opts.var, function(m) notes[#notes + 1] = m end)
    for _, n in ipairs(notes) do print("note   " .. n) end
    if not data then
        print("ERROR  " .. tostring(err))
        return 1
    end
    local settings = env and rawget(env, "Panels") and rawget(env, "Panels").Settings or {}
    local imageFolder = source .. slash(opts.images or settings.imageFolder or "images/")
    local audioFolder = source .. slash(opts.audio or settings.audioFolder or "audio/")

    local cache = {}
    local function globTable(base)
        local dir, stem = base:match("^(.*)/([^/]*)$")
        if not dir then dir, stem = ".", base end
        if cache[dir] == nil then cache[dir] = listDir(dir) or false end
        local list = cache[dir]
        if not list then return true end          -- cannot list: do not accuse
        local pat = "^" .. stem:gsub("%p", "%%%0") .. "%-table%-%d+%-%d+%.png$"
        for _, name in ipairs(list) do if name:match(pat) then return true end end
        return false
    end
    local files = nil
    local listed = listDir(imageFolder:sub(1, -2))
    if listed and #listed > 0 then
        files = fileExists
    else
        print("note   no images folder at " .. imageFolder .. " — file checks skipped (pass --source/--images)")
    end

    local report = Lint.check(data, {
        files = files, globTable = globTable, source = source,
        imageFolder = imageFolder, audioFolder = audioFolder,
        hints = opts.hints, cutscene = opts.cutscene,
    })
    local label = { error = "ERROR ", warn = "warn  ", hint = "hint  " }
    for _, it in ipairs(report.items) do print(label[it.level] .. " " .. it.where .. ": " .. it.msg) end
    local s = report.stats
    print(("%d sequences, %d panels, %d layers, %d words — %d errors, %d warnings, %d hints")
        :format(s.sequences, s.panels, s.layers, s.words, report.errors, report.warnings, report.hints))
    return report.errors > 0 and 1 or 0
end

-- Run as a script, stay quiet as a module.
local script = arg and arg[0] or ""
if script:match("lint_comic%.lua$") then os.exit(Lint.main(arg)) end

return Lint
