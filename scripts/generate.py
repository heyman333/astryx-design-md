#!/usr/bin/env python3
"""Reads the facebook/astryx repository and emits design.md and llms.txt
at this repository's root.

Usage:
    python3 scripts/generate.py                    # clones astryx into a temp dir
    ASTRYX_DIR=/path/to/astryx python3 scripts/generate.py   # use existing clone

Standard library only — Python 3.9+.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/facebook/astryx"
BLOB = f"{REPO_URL}/blob/main"
TREE = f"{REPO_URL}/tree/main"

# ---------------------------------------------------------------- clone/read


def get_astryx_dir() -> Path:
    env = os.environ.get("ASTRYX_DIR")
    if env:
        d = Path(env).resolve()
        if not (d / "package.json").exists():
            raise SystemExit(f"ASTRYX_DIR={d} does not look like the astryx repo")
        return d
    d = Path(tempfile.mkdtemp(prefix="astryx-"))
    subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(d)], check=True)
    return d


repo = get_astryx_dir()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


sha = git("rev-parse", "HEAD")
commit_date = git("log", "-1", "--format=%cs", "HEAD")


def read(p: str) -> str:
    return (repo / p).read_text(encoding="utf-8")


# ---------------------------------------------------------------- packages


def read_packages() -> list:
    out = []
    for name in sorted(os.listdir(repo / "packages")):
        pj = repo / "packages" / name / "package.json"
        if not pj.exists():
            continue
        j = json.loads(pj.read_text(encoding="utf-8"))
        desc = j.get("description", "")
        out.append(
            {
                "dir": f"packages/{name}",
                "name": j["name"],
                "version": j.get("version", ""),
                "description": desc,
                "has_readme": (repo / "packages" / name / "README.md").exists(),
                "canary": "@canary" in desc or "never released as a stable" in desc,
            }
        )
    return out


# ---------------------------------------------------------------- themes


def read_themes() -> list:
    d = repo / "packages/themes"
    if not d.exists():
        return []
    return sorted(n.name for n in d.iterdir() if n.is_dir())


# ---------------------------------------------------------------- components

# Parse {Name}.doc.mjs files with regex (some import modules, so no evaluation).
STR = r"(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\")"


def first_match(src: str, field: str) -> str:
    m = re.search(field + r":\s*" + STR, src)
    if not m:
        return ""
    s = m.group(1) if m.group(1) is not None else (m.group(2) or "")
    return s.replace("\\'", "'").replace('\\"', '"')


def title_case(s: str) -> str:
    return re.sub(r"\b\w", lambda m: m.group().upper(), s)


# --- minimal JS-object-literal scanner (string/comment aware) for llms-full ---

_LIT = r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`(?:[^`\\]|\\.)*`"


def _skip_ws_comments(s: str, i: int) -> int:
    n = len(s)
    while i < n:
        if s[i] in " \t\r\n":
            i += 1
        elif s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j + 1
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            break
    return i


def _match_bracket(s: str, i: int) -> int:
    """s[i] is an opening bracket; return index of its matching close, or -1."""
    close = {"{": "}", "[": "]", "(": ")"}[s[i]]
    open_ch = s[i]
    depth = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in "'\"`":
            q = c
            i += 1
            while i < n and s[i] != q:
                i += 2 if s[i] == "\\" else 1
        elif s.startswith("//", i):
            j = s.find("\n", i)
            i = n - 1 if j < 0 else j
        elif s.startswith("/*", i):
            j = s.find("*/", i)
            i = n - 1 if j < 0 else j + 1
        elif c == open_ch:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _skip_value(s: str, i: int, n: int) -> int:
    """Advance past one value; stop at the top-level comma (or n)."""
    while i < n:
        c = s[i]
        if c in "'\"`":
            q = c
            i += 1
            while i < n and s[i] != q:
                i += 2 if s[i] == "\\" else 1
        elif c in "{[(":
            j = _match_bracket(s, i)
            if j < 0:
                return n
            i = j
        elif c == ",":
            return i
        elif s.startswith("//", i):
            j = s.find("\n", i)
            i = n - 1 if j < 0 else j
        i += 1
    return i


def _object_items(obj_src: str) -> list:
    """(key, raw value source) pairs at the top level of `{...}` source."""
    items = []
    i, n = 1, len(obj_src) - 1
    key_re = re.compile(r"(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_$][\w$]*))\s*:")
    while True:
        i = _skip_ws_comments(obj_src, i)
        if i >= n:
            break
        m = key_re.match(obj_src, i)
        if not m:
            i = _skip_value(obj_src, i, n) + 1
            continue
        key = m.group(1) or m.group(2) or m.group(3)
        i = _skip_ws_comments(obj_src, m.end())
        start = i
        i = _skip_value(obj_src, i, n)
        items.append((key, obj_src[start:i].strip().rstrip(",").strip()))
        if i < n and obj_src[i] == ",":
            i += 1
    return items


def _array_objects(arr_src: str) -> list:
    """Top-level `{...}` chunks inside `[...]` source."""
    out = []
    i, n = 1, len(arr_src) - 1
    while i < n:
        i = _skip_ws_comments(arr_src, i)
        if i >= n:
            break
        if arr_src[i] == "{":
            j = _match_bracket(arr_src, i)
            if j < 0:
                break
            out.append(arr_src[i : j + 1])
            i = j + 1
        else:
            i = _skip_value(arr_src, i, n) + 1
    return out


def _as_str(v: str) -> str:
    """Join JS string-literal concatenations into one Python string."""
    parts = re.findall(_LIT, v or "")
    out = []
    for p in parts:
        out.append(
            p[1:-1]
            .replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\`", "`")
            .replace("\\n", " ")
        )
    return "".join(out)


def _parse_props(arr_src: str) -> list:
    res = []
    for o in _array_objects(arr_src):
        d = dict(_object_items(o))
        name = _as_str(d.get("name", ""))
        if not name:
            continue
        default_raw = d.get("default", "")
        res.append(
            {
                "name": name,
                "type": _as_str(d.get("type", "")),
                "default": _as_str(default_raw) or default_raw,
                "required": "true" in d.get("required", ""),
                "description": _as_str(d.get("description", "")),
            }
        )
    return res


def parse_full_doc(src: str) -> dict:
    """Parse the (English) docs object of a {Name}.doc.mjs file."""
    m = re.search(r"export const docs\s*=\s*\{", src)
    if not m:
        return {}
    end = _match_bracket(src, m.end() - 1)
    if end < 0:
        return {}
    d = dict(_object_items(src[m.end() - 1 : end + 1]))
    out = {"do": [], "dont": [], "props": [], "params": [], "returns": [], "units": []}
    out["import_path"] = _as_str(d.get("importPath", ""))
    for key in ("params", "returns"):
        if d.get(key, "").startswith("["):
            out[key] = _parse_props(d[key])
    usage = d.get("usage", "")
    if usage.startswith("{"):
        u = dict(_object_items(usage))
        bps = u.get("bestPractices", "")
        if bps.startswith("["):
            for o in _array_objects(bps):
                oi = dict(_object_items(o))
                desc = _as_str(oi.get("description", ""))
                if desc:
                    key = "do" if "true" in oi.get("guidance", "") else "dont"
                    out[key].append(desc)
    if d.get("props", "").startswith("["):
        out["props"] = _parse_props(d["props"])
    if d.get("components", "").startswith("["):
        for o in _array_objects(d["components"]):
            oi = dict(_object_items(o))
            uname = _as_str(oi.get("name", ""))
            if not uname:
                continue
            uprops = oi.get("props", "")
            out["units"].append(
                {
                    "name": uname,
                    "description": _as_str(oi.get("description", "")),
                    "props": _parse_props(uprops) if uprops.startswith("[") else [],
                }
            )
    return out


def read_components() -> list:
    src_dir = repo / "packages/core/src"
    comps = []
    for d in sorted(os.listdir(src_dir)):
        full = src_dir / d
        if not full.is_dir() or d.startswith("__"):
            continue
        for f in sorted(os.listdir(full)):
            if not f.endswith(".doc.mjs"):
                continue
            src = (full / f).read_text(encoding="utf-8")
            name = first_match(src, "name")
            if not name:
                continue
            category = title_case(first_match(src, "category"))
            group = first_match(src, "group") or name
            usage_idx = src.find("usage:")
            description = first_match(src[usage_idx:], "description") if usage_idx >= 0 else ""
            comps.append(
                {
                    "name": name,
                    "group": group,
                    "category": category,
                    "description": description,
                    "dir": d,
                    "path": f"packages/core/src/{d}/{f}",
                    "sub": False,
                    "full": parse_full_doc(src),
                }
            )
    return comps


# ---------------------------------------------------------------- collect

packages = read_packages()
themes = read_themes()
components = read_components()

# Subcomponent docs (e.g. Dialog/DialogHeader) omit `category`; inherit it from
# the categorized doc in the same source directory, falling back to a catch-all.
dir_category = {}
for c in components:
    if c["category"] and c["dir"] not in dir_category:
        dir_category[c["dir"]] = c["category"]
for c in components:
    if not c["category"]:
        c["category"] = dir_category.get(c["dir"], "Other Subcomponents & Hooks")
        c["sub"] = True

by_category = {}
for c in components:
    by_category.setdefault(c["category"], []).append(c)
categories = sorted(by_category)

groups = {c["group"] for c in components}

apps = sorted(n.name for n in (repo / "apps").iterdir() if n.is_dir())

root_pkg = json.loads(read("package.json"))

stamp = (
    f"> Auto-generated from [facebook/astryx]({REPO_URL}) — commit "
    f"[`{sha[:7]}`]({REPO_URL}/commit/{sha}) ({commit_date}). Do not edit by hand; "
    "run `python3 scripts/generate.py` to regenerate."
)

# ---------------------------------------------------------------- design.md


def design_md() -> str:
    lines = []
    push = lines.append
    push("# Astryx Design System — Design Overview")
    push("")
    push(stamp)
    push("")
    push("## What Astryx is")
    push("")
    push(
        "Astryx is Meta's open source design system, built on **React 19+** and **StyleX**, "
        "and designed to be used the same way by people and AI agents. It grew inside Meta over "
        "eight years, where it powers 13,000+ internal apps, and is currently published in **Beta**. "
        "Consumers import pre-built CSS and typed React components — no build plugin or styling "
        "library adoption is required."
    )
    push("")
    push("Key design commitments (from the project README):")
    push("")
    push("- **Open internals** — building blocks are exported directly; `swizzle` ejects a component's full source into your project when you need to own it.")
    push("- **No styling lock-in** — styles are authored in StyleX but overridable with `className` from Tailwind, CSS Modules, or plain CSS.")
    push("- **Customize without wrapping** — a theme is a set of CSS custom-property overrides, not a component fork.")
    push("- **Built for people and agents** — API, docs, and CLI are designed together; agents and humans consume the same reference.")
    push("- **Guidance over enforcement** — components render what you pass; design opinions live in docs, not runtime guardrails.")
    push('- **Earned by measurement** — conventions are tested (including "vibeability" tests that measure how well LLMs generate correct Astryx code).')
    push("")
    push("## Repository architecture")
    push("")
    push("A pnpm monorepo (Node 22+, pnpm 11):")
    push("")
    push("| Directory | Purpose |")
    push("| --- | --- |")
    push(f"| [`packages/`]({TREE}/packages) | Published packages: core, cli, build, themes (+ canary: lab, charts, vega, richtext) |")
    push(f"| [`apps/`]({TREE}/apps) | {len(apps)} apps: docsite, Storybook, sandbox, and framework example apps ({', '.join(apps)}) |")
    push(f"| [`internal/`]({TREE}/internal) | Internal tooling: test utils, eslint plugin, StyleX capability scanner, vibe tests |")
    push(f"| [`scripts/`]({TREE}/scripts) | Repo maintenance and release scripts |")
    push("")
    push("## Packages")
    push("")
    push("| Package | Version | Description |")
    push("| --- | --- | --- |")
    for p in packages:
        link = (
            f"[`{p['name']}`]({BLOB}/{p['dir']}/README.md)"
            if p["has_readme"]
            else f"[`{p['name']}`]({TREE}/{p['dir']})"
        )
        canary = " (canary)" if p["canary"] else ""
        desc = p["description"].replace("|", "\\|")
        push(f"| {link} | {p['version']}{canary} | {desc} |")
    push("")
    push("## Styling architecture")
    push("")
    theme_list = ", ".join(f"`theme-{t}`" for t in themes)
    push(
        "Components are authored with [StyleX](https://stylexjs.com). Consumers get pre-built CSS "
        "(`astryx.css`) plus typed React components; StyleX is invisible at the consumption layer. "
        "Theming works through CSS custom properties: each theme package "
        f"({theme_list}) overrides the same token set, and light/dark "
        "mode is built in. Source builds are available through `@astryxdesign/build` (Babel, PostCSS, "
        "Vite plugins) for apps that want to compile StyleX themselves."
    )
    push("")
    push("Notable StyleX conventions used across the codebase (see `CLAUDE.md` in the repo):")
    push("")
    push("- Parent→child state styling via `stylex.when.ancestor/descendant/sibling` markers instead of CSS nesting.")
    push("- Dialog entry animations via `@starting-style`, container-responsive layout via `@container`.")
    push("- Runtime values via style functions in `stylex.create`, never inline styles.")
    push("- Link elements resolve through `useLinkComponent()` / `LinkProvider` so framework routers (Next.js, React Router) can be swapped in.")
    push("")
    push("## Component library")
    push("")
    push(
        f"`@astryxdesign/core` currently documents **{len(components)} components** across "
        f"**{len(groups)} component groups** and **{len(categories)} categories**. Each component "
        "directory contains the implementation (`{Name}.tsx`), colocated tests, and a `{Name}.doc.mjs` "
        "structured doc (props, anatomy, best practices) consumed by the CLI and docsite."
    )
    push("")
    for cat in categories:
        comp_list = sorted(by_category[cat], key=lambda c: (c["sub"], c["name"].casefold()))
        push(f"### {cat} ({len(comp_list)})")
        push("")
        for c in comp_list:
            desc = f" — {c['description']}" if c["description"] else ""
            tag = " *(subcomponent/hook)*" if c["sub"] else ""
            push(f"- [**{c['name']}**]({BLOB}/{c['path']}){tag}{desc}")
        push("")
    push("## Documentation & tooling model")
    push("")
    push("- **File headers** — each source file carries a structured JSDoc header (`@input`, `@output`, `@position`) with `SYNC:` reminders to keep docs aligned with code.")
    push("- **Component docs** — `{Name}.doc.mjs` files export a typed `ComponentDoc` object (props, variants, anatomy, best practices).")
    push("- **CLI** — `@astryxdesign/cli` serves those docs to humans and agents alike: `astryx docs principles|tokens|theme`, `astryx component <Name> --dense`, `astryx template <name>`, `astryx swizzle <Name>`, `astryx upgrade --apply`.")
    push("- **Vibe tests** — `internal/vibe-tests` measures how reliably LLMs produce correct Astryx code from the agent docs, including 10-turn degradation curves.")
    push("")
    push("## External resources")
    push("")
    push("- Docs site: <https://astryx.atmeta.com>")
    push("- Storybook: <https://facebook.github.io/astryx/storybook/>")
    push("- Sandbox: <https://facebook.github.io/astryx/sandbox/>")
    push(f"- Contributing wiki: <{REPO_URL}/wiki/Contributing>")
    push("")
    return "\n".join(lines)


# ---------------------------------------------------------------- llms.txt

SUMMARY = (
    "> Astryx is Meta's open source design system for React 19+, built on StyleX and designed "
    "for both people and AI agents. It ships {n} documented components, "
    "seven themes, page templates, and a CLI as one cohesive system. Consumers import pre-built "
    "CSS and typed React components — no build plugin required."
)

KEY_FACTS = [
    "- Requires React 19+; `react` and `react-dom` are peer dependencies of `@astryxdesign/core`.",
    "- Install: `npm install @astryxdesign/core @astryxdesign/theme-neutral @stylexjs/stylex` plus `npm install -D @astryxdesign/cli`.",
    "- Styles are authored in StyleX but overridable with plain `className` (Tailwind, CSS Modules, plain CSS).",
    "- A theme is a set of CSS custom-property overrides; themes: {themes}.",
    "- `astryx swizzle <Name>` ejects a component's source into your project for deep customization.",
    "- CLI bootstrap for agents: `astryx docs principles --dense`, `astryx docs tokens --dense`, `astryx docs theme --dense`, `astryx component --list`, `astryx component <Name> --dense`.",
    "- Inputs are controlled: pass `value` + `onChange` (no `defaultValue`/`defaultChecked`). Wrap the app in `<Theme theme={{neutralTheme}}>` (theme object from `@astryxdesign/theme-*/built`).",
    '- Layout spacing uses a numeric scale: `gap={{4}}` / `padding={{6}}` (steps 0–10), not `gap="md"`. Components have no `style` prop — use `xstyle` or size props (`width`, `maxWidth`).',
]


def push_key_facts(push) -> None:
    push("Key facts:")
    push("")
    for fact in KEY_FACTS:
        push(fact.format(themes=", ".join(themes)))
    push("")


def llms_txt() -> str:
    lines = []
    push = lines.append
    push("# Astryx")
    push("")
    push(SUMMARY.format(n=len(components)))
    push("")
    push(f"Generated from commit `{sha[:7]}` ({commit_date}) of {REPO_URL}.")
    push("")
    push_key_facts(push)
    push("## Docs")
    push("")
    push(f"- [README]({BLOB}/README.md): Project overview, install, packages, principles")
    push(f"- [CLAUDE.md]({BLOB}/CLAUDE.md): AI/agent context — doc standards, StyleX capability matrix, CLI bootstrap commands")
    push(f"- [CONTRIBUTING]({BLOB}/CONTRIBUTING.md): Contributor guide (Node 22+, pnpm 11)")
    push(f"- [Wiki]({REPO_URL}/wiki): API conventions, design conventions, architecture, research")
    push("- [Docs site](https://astryx.atmeta.com): Published documentation")
    push("- [Storybook](https://facebook.github.io/astryx/storybook/): Live component stories")
    push("")
    push("## Packages")
    push("")
    for p in packages:
        url = f"{BLOB}/{p['dir']}/README.md" if p["has_readme"] else f"{TREE}/{p['dir']}"
        push(f"- [{p['name']}]({url}): {p['description']}")
    push("")
    push("## Components")
    push("")
    push(
        f"{len(components)} documented components in `packages/core/src/`. Each has a "
        "`{Name}.doc.mjs` structured doc with props, anatomy, and best practices. By category:"
    )
    push("")
    for cat in categories:
        names = ", ".join(c["name"] for c in by_category[cat])
        push(f"- {cat}: {names}")
    push("")
    push("## Optional")
    push("")
    push("- [llms-full.txt](llms-full.txt): Full per-component reference — props, types, defaults, and do/don't guidance for every component, generated from the same commit")
    push(f"- [Themes source]({TREE}/packages/themes): Seven theme packages ({', '.join(themes)})")
    push(f"- [Example apps]({TREE}/apps): {', '.join(apps)}")
    push(f"- [Internal tooling]({TREE}/internal): test utils, eslint plugin, StyleX capability scanner, vibe tests")
    push(f"- [Security policy]({BLOB}/SECURITY.md): Reporting vulnerabilities")
    push(f"- [License]({BLOB}/LICENSE): MIT")
    push("")
    return "\n".join(lines)


# ---------------------------------------------------------------- llms-full.txt


def fmt_prop(p: dict) -> str:
    line = f"- `{p['name']}`: {p['type'] or '—'}"
    if p["required"]:
        line += " (required)"
    if p["default"]:
        line += f" = {p['default']}"
    if p["description"]:
        line += f" — {p['description']}"
    return line


def llms_full_txt() -> str:
    doc_names = {c["name"] for c in components}
    lines = []
    push = lines.append
    push("# Astryx — Full Component Reference")
    push("")
    push(SUMMARY.format(n=len(components)))
    push(">")
    push(
        "> This llms-full.txt adds the complete per-component reference — import path, usage "
        "guidance, and every prop with its type, default, and description — so agents can write "
        "correct Astryx code without repository access or CLI calls. For the short index, see llms.txt."
    )
    push("")
    push(f"Generated from commit `{sha[:7]}` ({commit_date}) of {REPO_URL}.")
    push("")
    push_key_facts(push)
    push(
        "Every component below is importable from its subpath (shown per component) and also "
        "from the package root `@astryxdesign/core`. Entries marked (subcomponent/hook) compose "
        "with their parent component."
    )
    push("")
    for cat in categories:
        comp_list = sorted(by_category[cat], key=lambda c: (c["sub"], c["name"].casefold()))
        push(f"## {cat}")
        push("")
        for c in comp_list:
            full = c.get("full", {})
            # Some docs (e.g. Stack) keep the main component's props in a
            # same-named entry of their `components` array — promote it.
            main_props = full.get("props", [])
            main_desc = c["description"]
            for unit in full.get("units", []):
                if unit["name"] == c["name"]:
                    main_props = main_props or unit["props"]
                    main_desc = main_desc or unit["description"]
            tag = " (subcomponent/hook)" if c["sub"] else ""
            push(f"### {c['name']}{tag}")
            push("")
            import_path = full.get("import_path") or f"@astryxdesign/core/{c['dir']}"
            push(f"Import: `import {{{c['name']}}} from '{import_path}';`")
            if main_desc:
                push("")
                push(main_desc)
            if full.get("do"):
                push("")
                push("Do:")
                for g in full["do"]:
                    push(f"- {g}")
            if full.get("dont"):
                push("")
                push("Don't:")
                for g in full["dont"]:
                    push(f"- {g}")
            if main_props:
                push("")
                push("Props:")
                for p in main_props:
                    push(fmt_prop(p))
            if full.get("params"):
                push("")
                push("Parameters:")
                for p in full["params"]:
                    push(fmt_prop(p))
            if full.get("returns"):
                push("")
                push("Returns:")
                for p in full["returns"]:
                    push(fmt_prop(p))
            for unit in full.get("units", []):
                # Skip the promoted self-entry and units that have their own
                # doc file (those are emitted as separate entries).
                if unit["name"] == c["name"] or unit["name"] in doc_names:
                    continue
                if not (unit["props"] or unit["description"]):
                    continue
                push("")
                push(f"#### {unit['name']}")
                if unit["description"]:
                    push("")
                    push(unit["description"])
                if unit["props"]:
                    push("")
                    push("Props:")
                    for p in unit["props"]:
                        push(fmt_prop(p))
            push("")
    return "\n".join(lines)


# ---------------------------------------------------------------- write

(ROOT / "design.md").write_text(design_md(), encoding="utf-8")
(ROOT / "llms.txt").write_text(llms_txt(), encoding="utf-8")
(ROOT / "llms-full.txt").write_text(llms_full_txt(), encoding="utf-8")
n_props = sum(
    len(c.get("full", {}).get("props", []))
    + sum(len(u["props"]) for u in c.get("full", {}).get("units", []))
    for c in components
)
print(
    f"Wrote design.md, llms.txt, llms-full.txt (astryx @ {sha[:7]}, {len(components)} components, "
    f"{n_props} props, root pkg v{root_pkg.get('version', 'n/a')})"
)
