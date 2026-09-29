#!/usr/bin/env python3
"""Generate the Webflow embed bundle from the standalone site.

The site is served two ways: as its own GitHub Pages page, and pasted into a
Webflow Code Embed. The Webflow copy needs three things the standalone site
does not:

  1. Namespaced classes. Webflow's theme defines .line, .btn, .container,
     .card, .hero, .gallery, .h2 and .text-center, and we share all eight
     names. Scoping under #blend-vegas is NOT enough: specificity only picks a
     winner when both stylesheets declare the same property, so wherever ours
     is silent Webflow's rule applies unopposed. (This shipped a broken hero
     once: Webflow's `.line { height: 1px }` is a divider style, our title
     lines never declared a height, and all three rendered 1px tall.)
  2. Scoped selectors, so our global resets (*, html/body, img, a, button)
     cannot reach the Webflow nav.
  3. Absolute asset URLs, because a relative path resolves against
     overthetopxp.com, not our host.

Run after any change to index.html, styles.css or script.js:

    python3 build-embed.py

Writes embed.css and embed.js (commit + push these so Pages serves them) and
prints the markup to paste into the Code Embed.
"""

import io
import os
import re
import sys

BASE = "https://gabrielgalarza.github.io/the-blend-coffee-and-rb-las-vegas/"
SCOPE = "#blend-vegas"
PREFIX = "b-"
OUT = "webflow-embed.html"

# Classes toggled from JS that may not appear as selectors in styles.css.
RUNTIME_CLASSES = {"is-open"}

ROOT = os.path.dirname(os.path.abspath(__file__))


def read(name):
    return io.open(os.path.join(ROOT, name), encoding="utf-8").read()


def write(name, text):
    io.open(os.path.join(ROOT, name), "w", encoding="utf-8").write(text)


def class_names(css):
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = set(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", bare)) | RUNTIME_CLASSES
    # Longest first so `.card` never eats the front of `.card__title`.
    return sorted(found, key=len, reverse=True)


def add_prefix(text, names):
    for n in names:
        text = re.sub(r"\." + re.escape(n) + r"(?![\w-])", "." + PREFIX + n, text)
    return text


def split_blocks(s):
    """Split CSS into (prelude, body) pairs, brace-matched so nested at-rules survive."""
    out, i, n, start = [], 0, len(s), 0
    while i < n:
        if s[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                j += 1
            out.append((s[start:i], s[i + 1:j - 1]))
            start = j
            i = j
        else:
            i += 1
    if s[start:].strip():
        out.append((s[start:], None))
    return out


def scope_selector(sel):
    parts = []
    for one in [x.strip() for x in sel.split(",") if x.strip()]:
        if one in (":root", "html", "body"):
            parts.append(SCOPE)
        elif one == "*":
            parts.append(SCOPE + ", " + SCOPE + " *")
        else:
            parts.append(SCOPE + " " + one)
    return ", ".join(parts)


def scope_css(s):
    res = []
    for prelude, body in split_blocks(s):
        if body is None:
            res.append(prelude)
            continue
        # Peel leading comments BEFORE classifying, or a commented at-rule
        # gets scoped into invalid "#blend-vegas @media {...}".
        m = re.match(r"^(\s*(?:/\*.*?\*/\s*)*)(.*)$", prelude, re.S)
        lead, sel = m.group(1), m.group(2).strip()
        if sel.startswith(("@keyframes", "@-webkit-keyframes", "@font-face")):
            res.append(lead + sel + "{" + body + "}")
        elif sel.startswith(("@media", "@supports")):
            res.append(lead + sel + "{" + scope_css(body) + "}")
        else:
            res.append(lead + scope_selector(sel) + "{" + body + "}")
    return "".join(res)


def main():
    html, css, js = read("index.html"), read("styles.css"), read("script.js")
    names = class_names(css)
    nameset = set(names)

    write("embed.css", scope_css(add_prefix(css, names)))

    out_js = add_prefix(js, names)
    for n in RUNTIME_CLASSES:
        out_js = re.sub(
            r"(['\"])" + re.escape(n) + r"\1",
            lambda m, n=n: m.group(1) + PREFIX + n + m.group(1),
            out_js,
        )
    write("embed.js", out_js)

    body = html[html.index("<body>") + len("<body>"):html.index("</body>")]
    # The Webflow site has its own nav; ours would stack a second one on top.
    body = re.sub(r'<header class="nav">.*?</header>\s*', "", body, flags=re.S)
    body = re.sub(r'<script src="script\.js\?v=\d+"></script>\s*', "", body)
    body = re.sub(
        r'(class=")([^"]*)(")',
        lambda m: m.group(1)
        + " ".join((PREFIX + t if t in nameset else t) for t in m.group(2).split())
        + m.group(3),
        body,
    )
    body = re.sub(
        r'(src|href)="(images/|logos/)',
        lambda m: '%s="%s%s' % (m.group(1), BASE, m.group(2)),
        body,
    )

    # Bump the query string so browsers drop the previously cached bundle.
    ver = re.search(r"styles\.css\?v=(\d+)", html)
    ver = ver.group(1) if ver else "1"

    snippet = (
        "<!-- The Blend Vegas -->\n"
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        "family=Archivo+Black&family=Inter:wght@400;500;600;700;800;900&display=swap\">\n"
        '<link rel="stylesheet" href="%sembed.css?v=%s">\n\n'
        '<div id="blend-vegas">\n%s\n</div>\n\n'
        '<script src="%sembed.js?v=%s"></script>\n'
    ) % (BASE, ver, body.strip(), BASE, ver)
    write(OUT, snippet)

    leftovers = sorted(
        {t for m in re.finditer(r'class="([^"]*)"', snippet) for t in m.group(1).split()
         if not t.startswith(PREFIX)}
    )
    print("embed.css  %6.1f KB" % (os.path.getsize(os.path.join(ROOT, "embed.css")) / 1024))
    print("embed.js   %6.1f KB" % (os.path.getsize(os.path.join(ROOT, "embed.js")) / 1024))
    print("%s  %d chars (Webflow Code Embed limit is 50,000)" % (OUT, len(snippet)))
    if leftovers:
        print("WARNING un-namespaced classes:", leftovers)
        return 1
    if "SWEATPALS_WAITLIST_URL" in snippet:
        print("WARNING waitlist URL is still the placeholder")
    if SCOPE + " @" in read("embed.css"):
        print("WARNING mangled at-rule in embed.css")
        return 1
    print("ok - paste %s into the Webflow Code Embed, and push embed.css/embed.js" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
