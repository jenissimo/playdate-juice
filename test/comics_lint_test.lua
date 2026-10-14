-- Host tests for .claude/skills/comics/scripts/lint_comic.lua, the comicData checker
-- the comics skill runs before the simulator. Every finding it reports is a
-- mistake Panels itself would swallow silently (or crash on, later).
local A = require("assert")
package.path = package.path .. ";./.claude/skills/comics/scripts/?.lua"
local Lint = require("lint_comic")
local P = Lint.Panels

local function find(report, level, needle)
    for _, it in ipairs(report.items) do
        if it.level == level and (it.where .. ": " .. it.msg):find(needle, 1, true) then return it end
    end
end

local function panel(layers, extra)
    local p = { layers = layers }
    for k, v in pairs(extra or {}) do p[k] = v end
    return p
end

-- ---------------------------------------------------------------------------
-- a clean comic is clean
-- ---------------------------------------------------------------------------

local good = {
    { title = "One", scrollType = P.ScrollType.AUTO, backgroundColor = P.Color.BLACK,
      panels = {
          panel({ { image = "s1/bg", parallax = 0.4 }, { text = "Night.", effect = { type = P.Effect.TYPE_ON } } },
                { autoAdvance = 1500, frame = { width = 600, gap = 20 } }),
          panel({ { image = "s1/door", animate = { x = -100, duration = 300, trigger = P.Input.A } } },
                { advanceControl = P.Input.A }),
      } },
    { id = "end", backgroundColor = P.Color.BLACK,
      panels = { panel({ { imageTable = "s2/walk", loop = true, delay = 120 } }) } },
}
local r = Lint.check(good)
A.eq(r.errors, 0, "lint: a clean comic has no errors")
A.eq(r.warnings, 0, "lint: ...and no warnings")
A.eq(r.stats.sequences, 2, "lint: counts sequences")
A.eq(r.stats.panels, 3, "lint: counts panels")
A.eq(r.stats.layers, 4, "lint: counts layers")

-- ---------------------------------------------------------------------------
-- the silent mistakes
-- ---------------------------------------------------------------------------

r = Lint.check({ { panels = { panel({ { image = "a", animate = { x = 10, scrolltrigger = 0.5 } } }) } } })
A.truthy(find(r, "warn", "did you mean 'scrollTrigger'"), "lint: a misspelt key is caught, with the right spelling")

r = Lint.check({ { panels = { panel({ { image = "a", text = "b" } }) } } })
A.truthy(find(r, "error", "one layer, one kind"), "lint: two kinds in one layer is an error")

r = Lint.check({ { panels = { panel({ {} }) } } })
A.truthy(find(r, "error", "a layer needs one of"), "lint: an empty layer is an error")

r = Lint.check({ { panels = { panel({ { image = "a", effect = { type = P.Effect.TYPE_ON } } }) } } })
A.truthy(find(r, "error", "TYPE_ON works on text layers only"), "lint: TYPE_ON on an image")

r = Lint.check({ { panels = { panel({ { image = "a", effect = { type = P.Effect.BLINK } } }) } } })
A.truthy(find(r, "error", "BLINK needs durations"), "lint: BLINK without durations")

r = Lint.check({ { panels = { panel({ { text = "a" } }, { effect = { type = P.Effect.BLINK } }) } } })
A.truthy(find(r, "error", "panel effect is SHAKE_UNISON or SHAKE_INDIVIDUAL"), "lint: layer effects on a panel")

r = Lint.check({ { panels = { panel({ { text = "a" } }, { autoAdvance = 1000 }) } } })
A.truthy(find(r, "warn", "AUTO-only property in a MANUAL sequence"), "lint: AUTO-only keys in a MANUAL sequence")

r = Lint.check({ { scrollType = P.ScrollType.AUTO, panels = { panel({ { text = "a" } }, { autoAdvance = 2 }) } } })
A.truthy(find(r, "warn", "milliseconds"), "lint: autoAdvance = 2 was meant as seconds")

r = Lint.check({ { panels = { panel({ { image = "a", animate = { y = 0, scrollTrigger = 1.5 } } }) } } })
A.truthy(find(r, "error", "never happens"), "lint: a scroll trigger past 1 never fires")

r = Lint.check({ { panels = { panel({ { image = "a", font = "f" } }) } } })
A.truthy(find(r, "warn", "text-layer property on a image layer"), "lint: text properties on an image layer")

r = Lint.check({ { panels = { panel({ { image = "a", delay = 300 } }) } } })
A.truthy(find(r, "warn", "did you mean animate.delay"), "lint: imageTable keys on an image layer")

r = Lint.check({ { panels = { panel({ { image = "a", advanceControl = "A" } }) } } })
A.truthy(find(r, "error", "Panels.Input value"), "lint: a string where a button belongs")

-- ---------------------------------------------------------------------------
-- what the simulator taught us
-- ---------------------------------------------------------------------------

local twoColours = {
    { backgroundColor = P.Color.BLACK, panels = { panel({ { text = "a" } }) } },
    { backgroundColor = P.Color.WHITE, panels = { panel({ { text = "b" } }) } },
}
A.truthy(find(Lint.check(twoColours), "warn", "transitionFader"),
    "lint: a background change between sequences is flagged")
A.truthy(find(Lint.check(twoColours, { cutscene = true }), "error", "crashes Panels.startCutscene"),
    "lint: ...and is an error for a cutscene")

r = Lint.check({ { direction = P.ScrollDirection.NONE, scrollType = P.ScrollType.AUTO,
                   panels = { panel({ { text = "a" } }) } } })
A.truthy(find(r, "warn", "no default advance button"), "lint: NONE without an advance control")

-- ---------------------------------------------------------------------------
-- branching
-- ---------------------------------------------------------------------------

r = Lint.check({
    { id = "start", panels = { panel({ { text = "a" } }) },
      advanceControls = { { input = P.Input.A, target = "rom" }, { input = P.Input.B, target = 9 } } },
    { id = "room", panels = { panel({ { text = "b" } }) } },
    { id = "room", panels = { panel({ { text = "c" } }) } },
})
A.truthy(find(r, "error", "no sequence has id 'rom', did you mean 'room'"), "lint: a mistyped target")
A.truthy(find(r, "error", "index 9 is out of range"), "lint: an index past the end")
A.truthy(find(r, "error", "also used by seq 2"), "lint: duplicate ids")

r = Lint.check({ title = "x", { panels = { panel({ { text = "a" } }) } } })
A.truthy(find(r, "error", "plain list of sequences"), "lint: keys at the top level")
A.truthy(find(Lint.check(nil), "error", "non-empty list"), "lint: no comic at all")

-- ---------------------------------------------------------------------------
-- files: checked through an injected lookup, so no fixtures on disk
-- ---------------------------------------------------------------------------

local disk = { ["Source/images/s1/bg.png"] = true, ["Source/audio/door.wav"] = true,
               ["Source/fonts/Sasser.fnt"] = true }
local opts = {
    files = function(p) return disk[p] == true end,
    globTable = function(base) return base == "Source/images/walk" end,
    source = "Source/", imageFolder = "Source/images/", audioFolder = "Source/audio/",
}
r = Lint.check({ { panels = {
    panel({ { image = "s1/bg" }, { image = "s1/missing" }, { image = "s1/bg.png" },
            { imageTable = "walk" }, { imageTable = "run" },
            { text = "a", font = "fonts/Sasser" }, { text = "b", font = "fonts/Nope" } },
          { audio = { file = "door", scrollTrigger = 0.5 } }),
} } }, opts)
A.truthy(find(r, "error", "image 's1/missing' not found"), "lint: a missing image")
A.falsy(find(r, "error", "s1/bg.png"), "lint: an image path with .png is found too (the SDK accepts it)")
A.falsy(find(r, "error", "image 's1/bg' not found"), "lint: a present image passes")
A.falsy(find(r, "error", "image table 'walk'"), "lint: a -table-W-H image table is found")
A.truthy(find(r, "error", "image table 'run' not found"), "lint: a missing image table")
A.falsy(find(r, "error", "audio 'door'"), "lint: present audio passes")
A.truthy(find(r, "error", "font 'fonts/Nope' not found"), "lint: a missing font")

-- ---------------------------------------------------------------------------
-- loading a data file: strict constants, Playdate syntax, stand-ins
-- ---------------------------------------------------------------------------

local data, err = Lint.loadString([[
comicData = { { panels = { { layers = { { text = "x", animate = { y = 1, trigger = Panels.Input.AA } } } } } } }
]], "typo.lua")
A.falsy(data, "lint: a misspelt constant fails the load")
A.truthy(err and err:find("Panels.Input.AA does not exist", 1, true), "lint: ...naming it")
A.truthy(err and err:find("typo.lua:1", 1, true), "lint: ...at its line")

data, err = Lint.loadString([[
--======== a banner the desugarer must not touch
local bg = Backgrounds.indexOf("Starfield")
local n = 0
local function render(panel, offset) n += 1; Backgrounds.draw(bg) end
local ease = playdate.easingFunctions.outBack
return { { scrollType = Panels.ScrollType.AUTO, panels = {
    { renderFunction = render, layers = {}, frame = { width = Credits.SCREEN_W * 2 } },
} } }
]], "juicy.lua")
A.truthy(data, "lint: a data file with +=, juice globals and easings loads (" .. tostring(err) .. ")")
r = Lint.check(data or {})
A.eq(r.errors, 0, "lint: values made from stand-ins are not judged")

data = Lint.loadString([[
local d = { { panels = { { layers = { { text = "y" } } } } } }
Panels.startCutscene(d, function() end)
]], "cut.lua")
A.truthy(data and data[1].panels, "lint: finds the table handed to Panels.startCutscene")

A.falsy(Lint.loadString("x = 1", "none.lua"), "lint: no comic data is reported")
A.eq(Lint.desugar("a.b *= 2 -- c -= 1"), "a.b = a.b * 2 -- c -= 1", "lint: desugar leaves comments alone")
