"""Targeted text edits for the server-side ``.img.xml`` mirror."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import quoteattr


TAG_BY_TYPE = {
    "SubProperty": "imgdir",
    "Null": "null",
    "Short": "short",
    "Int": "int",
    "Long": "long",
    "Float": "float",
    "Double": "double",
    "String": "string",
    "Vector": "vector",
    "UOL": "uol",
    "Canvas": "canvas",
    "Sound": "sound",
    "Convex": "extended",
    "Video": "canvas",
    "RawData": "extended",
}

_TOKEN_RE = re.compile(r"<!--.*?-->|<\?.*?\?>|<![^>]*>|</?[^>]+>", re.DOTALL)
_START_RE = re.compile(r"<\s*([^\s/>]+)")


@dataclass
class XmlNodeSpan:
    tag: str
    name: Optional[str]
    start: int
    start_end: int
    end_start: int
    end: int
    self_closing: bool
    parent: Optional["XmlNodeSpan"] = None
    children: List["XmlNodeSpan"] = field(default_factory=list)


def _attrs_from_token(token: str) -> Tuple[str, Dict[str, str]]:
    match = _START_RE.match(token)
    if not match:
        raise ValueError(f"invalid XML start tag: {token[:40]!r}")
    tag = match.group(1)
    probe = token if token.rstrip().endswith("/>") else token.rstrip()[:-1] + "/>"
    element = ET.fromstring(probe)
    return tag, dict(element.attrib)


def scan_xml(text: str) -> XmlNodeSpan:
    stack: List[XmlNodeSpan] = []
    root: Optional[XmlNodeSpan] = None
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token.startswith(("<!--", "<?", "<!")):
            continue
        if token.startswith("</"):
            if not stack:
                raise ValueError("unexpected XML closing tag")
            node = stack.pop()
            close_name = token[2:-1].strip()
            if close_name != node.tag:
                raise ValueError(f"XML tag mismatch: {node.tag} / {close_name}")
            node.end_start = match.start()
            node.end = match.end()
            continue
        tag, attrs = _attrs_from_token(token)
        self_closing = token.rstrip().endswith("/>")
        parent = stack[-1] if stack else None
        node = XmlNodeSpan(
            tag=tag,
            name=attrs.get("name"),
            start=match.start(),
            start_end=match.end(),
            end_start=match.start() if self_closing else -1,
            end=match.end() if self_closing else -1,
            self_closing=self_closing,
            parent=parent,
        )
        if parent:
            parent.children.append(node)
        elif root is None:
            root = node
        else:
            raise ValueError("XML contains multiple roots")
        if not self_closing:
            stack.append(node)
    if stack:
        raise ValueError(f"unclosed XML tag: {stack[-1].tag}")
    if root is None:
        raise ValueError("XML has no root element")
    ET.fromstring(text)
    return root


def _find_node(root: XmlNodeSpan, path: Sequence[str]) -> XmlNodeSpan:
    current = root
    for index, part in enumerate(path):
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            label = "/".join(path[:index + 1])
            if not matches:
                raise KeyError(label)
            raise ValueError(f"duplicate XML nodes at {label}")
        current = matches[0]
    return current


def _replace_attr(token: str, key: str, value: str) -> str:
    attr_re = re.compile(rf"(\s{re.escape(key)}\s*=\s*)(['\"]).*?\2", re.DOTALL)
    if attr_re.search(token):
        return attr_re.sub(lambda match: match.group(1) + quoteattr(value), token, count=1)
    suffix = "/>" if token.rstrip().endswith("/>") else ">"
    cut = token.rfind(suffix)
    return token[:cut] + f" {key}={quoteattr(value)}" + token[cut:]


def _line_indent(text: str, offset: int) -> str:
    line_start = text.rfind("\n", 0, offset) + 1
    return text[line_start:offset] if text[line_start:offset].strip() == "" else ""


def _serialized_node(kind: str, name: str, values: dict) -> str:
    tag = TAG_BY_TYPE.get(kind)
    if tag is None:
        raise ValueError(f"unsupported XML property type: {kind}")
    attrs = [f"name={quoteattr(name)}"]
    if kind == "Vector":
        attrs.extend((f'x={quoteattr(str(values["x"]))}', f'y={quoteattr(str(values["y"]))}'))
    elif kind not in ("SubProperty", "Null"):
        attrs.append(f'value={quoteattr(str(values["value"]))}')
    return f"<{tag} {' '.join(attrs)}/>"


def _remove_span_with_indent(text: str, node: XmlNodeSpan) -> Tuple[int, int]:
    start = node.start
    line_start = text.rfind("\n", 0, start) + 1
    if text[line_start:start].strip() == "":
        start = line_start
    end = node.end
    if end < len(text) and text[end] == "\n":
        end += 1
    return start, end


def mutate_xml(
    text: str,
    operation: str,
    path: Sequence[str],
    *,
    name: Optional[str] = None,
    kind: Optional[str] = None,
    values: Optional[dict] = None,
) -> str:
    root = scan_xml(text)
    values = values or {}
    if operation == "add":
        if not name or not kind:
            raise ValueError("name and kind are required for add")
        parent = _find_node(root, path)
        if parent.tag not in ("imgdir", "canvas"):
            raise ValueError("XML parent is not a container")
        if any(child.name == name for child in parent.children):
            raise FileExistsError("/".join((*path, name)))
        child_text = _serialized_node(kind, name, values)
        indent = _line_indent(text, parent.start) + "  "
        if parent.self_closing:
            opening = text[parent.start:parent.start_end].rstrip()
            opening = opening[:-2].rstrip() + ">"
            replacement = f"{opening}\n{indent}{child_text}\n{_line_indent(text, parent.start)}</{parent.tag}>"
            result = text[:parent.start] + replacement + text[parent.end:]
        else:
            close_line_start = text.rfind("\n", 0, parent.end_start) + 1
            if text[close_line_start:parent.end_start].strip() == "":
                insert_at = close_line_start
            else:
                insert_at = parent.end_start
            insertion = f"{indent}{child_text}\n"
            result = text[:insert_at] + insertion + text[insert_at:]
    else:
        node = _find_node(root, path)
        expected_tag = TAG_BY_TYPE.get(kind) if kind else None
        if expected_tag and node.tag != expected_tag:
            raise ValueError(
                f"XML node type {node.tag!r} does not match IMG type {kind!r}"
            )
        if operation == "remove":
            start, end = _remove_span_with_indent(text, node)
            result = text[:start] + text[end:]
        elif operation == "rename":
            if not name:
                raise ValueError("name is required for rename")
            if node.parent and name != node.name and any(child.name == name for child in node.parent.children):
                raise FileExistsError("/".join((*path[:-1], name)))
            token = text[node.start:node.start_end]
            replacement = _replace_attr(token, "name", name)
            result = text[:node.start] + replacement + text[node.start_end:]
        elif operation == "edit":
            token = text[node.start:node.start_end]
            if node.tag == "vector":
                token = _replace_attr(token, "x", str(values["x"]))
                token = _replace_attr(token, "y", str(values["y"]))
            elif node.tag in ("imgdir", "canvas", "null"):
                raise ValueError(f"{node.tag} XML nodes have no editable value")
            else:
                token = _replace_attr(token, "value", str(values["value"]))
            result = text[:node.start] + token + text[node.start_end:]
        else:
            raise ValueError(f"unsupported operation: {operation}")
    scan_xml(result)
    return result
