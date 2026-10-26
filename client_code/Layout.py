"""Page building blocks on top of the Craftify standard page (iPac patterns)."""

from anvil import *
from routing import router
import anvil.google.auth, anvil.google.drive
from anvil.google.drive import app_files

GAP_NONE = {"spacing_above": "none", "spacing_below": "none"}


def esc(value):
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def flat(component):
    """Drop Anvil's default spacing so the CSS grid/stack gaps are the only gaps."""
    try:
        component.spacing_above = "none"
        component.spacing_below = "none"
    except Exception:
        pass
    return component


def stack(*children):
    page = flat(HtmlTemplate(html="@theme:bc-stack.html"))
    for child in children:
        add(page, child)
    return page


def grid(columns="repeat(auto-fit, minmax(180px, 1fr))", *children):
    panel = flat(HtmlTemplate(html="@theme:bc-grid.html"))
    panel.dom_nodes["grid"].style.gridTemplateColumns = columns
    for child in children:
        add(panel, child)
    return panel


def add(container, child):
    if child is None:
        return None
    container.add_component(flat(child), slot="default")
    return child


def page_header(title, eyebrow="", description="", actions=()):
    head = flat(HtmlTemplate(html="@theme:page-header.html"))
    head.dom_nodes["eyebrow"].textContent = eyebrow or ""
    head.dom_nodes["title"].textContent = title or ""
    head.dom_nodes["description"].textContent = description or ""
    if not actions:
        head.dom_nodes["actions"].classList.add("is-empty")
    for action in actions:
        head.add_component(flat(action), slot="actions")
    return head


def section(title, subtitle="", padded=True, actions=()):
    card = flat(HtmlTemplate(html="@theme:table-section.html"))
    card.dom_nodes["title"].textContent = title or ""
    card.dom_nodes["subtitle"].textContent = subtitle or ""
    if padded:
        card.dom_nodes["body"].classList.add("is-padded")
    for action in actions:
        card.add_component(flat(action), slot="actions")
    return card


def body(card, *children):
    for child in children:
        card.add_component(flat(child), slot="body")
    return card


def field(label, component, hint=""):
    box = flat(HtmlTemplate(html="@theme:bc-field.html"))
    box.dom_nodes["label"].textContent = label or ""
    box.dom_nodes["hint"].textContent = hint or ""
    box.add_component(flat(component), slot="input")
    return box


def html(markup):
    return flat(HtmlTemplate(html=markup))


def note(text, tone="muted"):
    return html('<p class="bc-note bc-note-%s">%s</p>' % (tone, esc(text)))


def button(text, handler=None, primary=False, icon=""):
    btn = Button(text=text, icon=icon, role="primary-color" if primary else None)
    flat(btn)
    btn.align = "left"
    if handler is not None:
        btn.set_event_handler("click", handler)
    return btn


def definition_list(pairs):
    items = "".join(
        '<div><dt>%s</dt><dd>%s</dd></div>' % (esc(label), esc(value)) for label, value in pairs
    )
    return html('<dl class="bc-dl">%s</dl>' % items)


def empty_state(message, action_text="", handler=None):
    card = section("Nothing here yet")
    body(card, note(message))
    if action_text and handler is not None:
        body(card, button(action_text, handler, primary=True))
    return card


PAGE_PATHS = {
    "dashboard": "/dashboard",
    "tracker": "/tracker",
    "progress": "/progress",
    "checkin": "/checkin",
    "plan": "/plan",
    "profile": "/profile",
}


def navigate(page, **kwargs):
    from craftify_library.CraftifyRouting import navigate as routing_navigate

    week = kwargs.pop("week", None)
    if page == "checkin" and week is not None:
        routing_navigate(path="/checkin/:week", params={"week": week}, form_properties=kwargs)
        return
    routing_navigate(path=PAGE_PATHS.get(page) or "/dashboard", form_properties=kwargs)
