---
name: fnv-fomod
description: Create a FOMOD installer (info.xml + ModuleConfig.xml) for a Fallout New Vegas mod that needs install-time choices. Use ONLY when the user must pick between options; most mods need no FOMOD.
argument-hint: "[the install options the mod offers]"
---

# FOMOD Installer (FNV)

A FOMOD is an **interactive installer** read by the mod managers (MO2/Vortex/FOMM). Use one **only when the player must make a choice at install time** — e.g. a texture mod offering several brightness variants, optional add-ons, or mutually-exclusive compatibility patches.

> **Most mods do NOT need a FOMOD.** If a mod just ships its files (one version, no choices), don't make one — packaging the files is enough. A FOMOD exists to present *options*.

## Layout
```
<ModRoot>/
  fomod/
    info.xml           # metadata (Name/Author/Version/Description)
    ModuleConfig.xml   # the installer logic
    image.png          # optional header/banner
  options/
    default/ ...       # the files each choice installs (any folder names you reference)
    variantB/ ...
  core/ ...            # (optional) files installed for everyone
```
The `source=` paths in ModuleConfig.xml are **relative to the mod root** (the folder containing `fomod/`).

## ModuleConfig.xml structure
```
<config …ModConfig5.0.xsd>
  <moduleName>…</moduleName>
  <requiredInstallFiles> … </requiredInstallFiles>      (optional — installed for everyone)
  <installSteps order="Explicit">
    <installStep name="…">
      <optionalFileGroups order="Explicit">
        <group name="…" type="SelectExactlyOne">          (selection rule — see types)
          <plugins order="Explicit">
            <plugin name="…">
              <description>…</description>
              <image path="fomod/…png"/>                  (optional)
              <files><folder source="options/x" destination="" priority="0"/></files>
              <conditionFlags><flag name="F">On</flag></conditionFlags>   (optional)
              <typeDescriptor><type name="Recommended"/></typeDescriptor>  (default state)
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
  <conditionalFileInstalls> … </conditionalFileInstalls>  (optional — install by flag/condition)
</config>
```
- **Group `type`** (selection rule): `SelectExactlyOne`, `SelectAtMostOne`, `SelectAtLeastOne`, `SelectAll`, `SelectAny`.
- **Plugin `<type name=>`** (default state): `Required`, `Optional`, `Recommended`, `NotUsable`, `CouldBeUsable`. For conditional defaults use `<dependencyType><patterns><pattern><dependencies>…` instead of a flat `<type>`.
- **Files:** `<file source=… destination=… priority=…/>` or `<folder source=… destination=… priority=…/>` (`destination=""` = mod root).
- **Conditions/flags:** a plugin can set `conditionFlags`; `conditionalFileInstalls` then installs files based on `<flagDependency flag= value=>` or `<fileDependency file="X.esp" state="Active|Inactive|Missing"/>` (combine with `dependencies operator="And|Or"`). Steps can also be shown conditionally via `<visible>`.

## Workflow
1. **Confirm a FOMOD is warranted** — what choices does the mod offer? If none, stop and just package the files.
2. **Lay out source folders** — one per option (e.g. `options/bright`, `options/dark`) + any `core/` always-files.
3. **Scaffold:** `bash tools/automod-cli.sh fomod init "<ModRoot>/fomod" --name "My Mod" --author X --version 1.0 --desc "…" --json`
4. **Author** `ModuleConfig.xml` for the real steps/groups/options (the skeleton is a `SelectExactlyOne` example). Reference `fomod types` for the valid enums.
5. **Validate:** `bash tools/automod-cli.sh fomod validate "<ModRoot>/fomod/ModuleConfig.xml" --json` — checks well-formedness, group/plugin type enums, and that every `source=` folder exists.
6. **Test in a mod manager** — install the packaged mod through MO2/Vortex, click through the options, confirm the right files land.

## Worked example — map brightness
`SelectExactlyOne` group "Map Brightness" with plugins **Bright** (`options/bright`), **Default** (`options/default`, `Recommended`), **Dark** (`options/dark`) — installer shows radio buttons, installs the chosen folder.

## Notes
- The validator is **structural sanity, not full XSD** — it catches the common mistakes (bad enums, unbalanced tags, missing source folders), not every schema nuance.
- Keep `source=` paths and folder casing consistent; managers are usually case-insensitive but be tidy.
