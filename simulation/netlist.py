"""Small reader for the S-expression netlist exported by KiCad.

Only the export's data is consumed. No schematic editing or third-party parser
is required. Physical pin pairs are used so changing a displayed label does not
change which connection is checked.
"""

import json
import re
from pathlib import Path


def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack, roots = [], []
    for token in tokens:
        if token == "(":
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
        elif token == ")":
            if not stack:
                raise ValueError("Unmatched closing parenthesis")
            stack.pop()
        else:
            if not stack:
                raise ValueError("Value outside an expression")
            stack[-1].append(json.loads(token) if token.startswith('"')
                             else token)
    if stack or len(roots) != 1:
        raise ValueError("Expected one balanced export expression")
    return roots[0]


def children(node, key):
    return [part for part in node
            if isinstance(part, list) and part and part[0] == key]


def field(node, key):
    matches = children(node, key)
    if len(matches) != 1:
        raise ValueError(f"Expected one {key!r} field; got {len(matches)}")
    return matches[0]


class Netlist:
    def __init__(self, path):
        root = parse(Path(path).read_text())
        self.pin_net = {}
        self.members = {}
        self.spice_names = {}
        for net in children(field(root, "nets"), "net"):
            name = field(net, "name")[1]
            self.spice_names[name] = (
                "0" if name == "GND" else "n" + field(net, "code")[1])
            self.members[name] = set()
            for pin in children(net, "node"):
                pair = (field(pin, "ref")[1], field(pin, "pin")[1])
                if pair in self.pin_net:
                    raise ValueError(f"Pin appears on multiple nets: {pair}")
                self.pin_net[pair] = name
                self.members[name].add(".".join(pair))
        self.values = {
            field(component, "ref")[1]: field(component, "value")[1]
            for component in children(field(root, "components"), "comp")
        }

    def node(self, ref, pin):
        """SPICE node connected to a physical component pin."""
        return self.spice_names[self.pin_net[(ref, str(pin))]]

    def connections(self, ref, pin):
        return self.members[self.pin_net[(ref, str(pin))]]
