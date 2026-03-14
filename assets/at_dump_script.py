import pyatspi
import xml.etree.ElementTree as ET
import sys
import subprocess
import time

from playwright.sync_api import sync_playwright


sys.setrecursionlimit(3000)


def dump_playwright():
    root = ET.Element("browser-page")
    
    offset_x, offset_y = -3, 165

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

        contexts = browser.contexts
        if not contexts:
            return root

        page = contexts[0].pages[0]

        selectors = """
        a[href],
        button,
        input,
        textarea,
        select,
        [role=button],
        [role=link],
        [role=textbox],
        [role=checkbox],
        [role=radio],
        [contenteditable=true]
        """

        loc = page.locator(selectors)

        count = min(loc.count(), 200)

        for i in range(count):
            try:
                el = loc.nth(i)
                if not el.is_visible():
                    continue

                bbox = el.bounding_box()
                if not bbox:
                    continue

                role = el.evaluate("""
                    el => el.getAttribute('role') || el.tagName.toLowerCase()
                """)

                name = el.evaluate("""
                    el =>
                        el.getAttribute('aria-label') ||
                        el.innerText ||
                        el.value ||
                        el.textContent ||
                        ''
                """)

                node = ET.Element(str(role).replace(" ", "-"))
                node.set("name", str(name)[:200])
                
                screen_x = int(offset_x + bbox["x"])
                screen_y = int(offset_y + bbox["y"])

                node.set("screencoord", f"({screen_x}, {screen_y})")
                node.set("size", f"({int(bbox['width'])}, {int(bbox['height'])})")

                node.set("visible", "true")
                node.set("enabled", "true")

                root.append(node)

            except:
                pass

    return root


def _build_tree(accessible):
    role_name = accessible.getRoleName() if accessible else "unknown"
    tag_name = role_name.replace(" ", "-")
    node = ET.Element(tag_name)

    try:
        if accessible.name:
            node.set('name', str(accessible.name))
        if accessible.description:
            node.set('description', str(accessible.description))
    except:
        pass

    try:
        state_set = accessible.getState()
        node.set('visible', 'true'
                 if state_set.contains(pyatspi.STATE_VISIBLE) else 'false')
        node.set('showing', 'true'
                 if state_set.contains(pyatspi.STATE_SHOWING) else 'false')
        node.set('enabled', 'true'
                 if state_set.contains(pyatspi.STATE_ENABLED) else 'false')
    except:
        pass

    try:
        extents = accessible.queryComponent().getExtents(
            pyatspi.DESKTOP_COORDS)
        node.set('screencoord', f"({extents.x}, {extents.y})")
        node.set('size', f"({extents.width}, {extents.height})")
    except:
        pass

    for i in range(min(accessible.getChildCount(), 80)):
        try:
            child = accessible.getChildAtIndex(i)
            if child:
                node.append(_build_tree(child))
        except:
            pass

    return node


def dump_atspi():
    desktop = pyatspi.Registry.getDesktop(0)
    if desktop:
        return _build_tree(desktop)
    else:
        return ET.Element("error")


def main():
    root = ET.Element("hybrid-ui-tree")

    pw_tree = dump_playwright()
    root.append(pw_tree)

    atspi_tree = dump_atspi()
    root.append(atspi_tree)

    print(ET.tostring(root, encoding="unicode"))

if __name__ == "__main__":
    main()
