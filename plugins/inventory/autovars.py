from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os
import yaml
from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleError

DOCUMENTATION = r'''
name: autovars
plugin_type: inventory
short_description: Inventory plugin that loads vars from parent group_vars/all.yaml
description:
  - Recursively searches for group_vars/all.yaml up to 3 levels above and injects its variables into all parsed hosts.
options:
  plugin:
    description: The name of the plugin
    required: true
    choices: ['autovars']
'''

class InventoryModule(BaseInventoryPlugin):
    NAME = 'autovars'

    def verify_file(self, path):
        return os.path.basename(path) == 'inventory.yaml'

    def parse(self, inventory, loader, path, cache=True):
        self.loader = loader
        self.inventory = inventory
        basedir = os.path.dirname(path)
        data = loader.load_from_file(path)
        if not isinstance(data, dict):
            raise AnsibleError(f"Expected dict in {path}, got {type(data)}")
        for group_name, group_data in data.items():
            if not isinstance(group_data, dict):
                continue
            self._parse_group_hierarchy(group_name, group_data)
        all_vars = {}
        any_found = False

        for level in reversed(range(4)):
            gv_path = os.path.abspath(
                os.path.join(basedir, *(['..'] * level), 'group_vars', 'all.yaml')
            )
            if os.path.exists(gv_path):
                self.display.v(f"[autovars] Loading vars from {gv_path}")
                with open(gv_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    if not isinstance(data, dict):
                        raise AnsibleError(f"Expected dict in {gv_path}, got {type(data)}")
                    all_vars.update(data)
                any_found = True

        if not any_found:
            self.display.v("[autovars] No group_vars/all.yaml found.")

        hostnames = list(self.inventory.hosts.keys())
        if not hostnames:
            raise AnsibleError("[autovars] No hosts found in inventory to inject vars into.")

        for host in hostnames:
            for k, v in all_vars.items():
                self.inventory.set_variable(host, k, v)
