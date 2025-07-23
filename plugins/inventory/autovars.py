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
                    group_vars_data = yaml.safe_load(f) or {}
                    if not isinstance(group_vars_data, dict):
                        raise AnsibleError(f"Expected dict in {gv_path}, got {type(group_vars_data)}")
                    all_vars.update(group_vars_data)
                any_found = True

        if not any_found:
            self.display.v("[autovars] No group_vars/all.yaml found.")

        hostnames = list(self.inventory.hosts.keys())
        if not hostnames:
            raise AnsibleError("[autovars] No hosts found in inventory to inject vars into.")

        for host in hostnames:
            for k, v in all_vars.items():
                self.inventory.set_variable(host, k, v)

    def _parse_group_hierarchy(self, group_name, group_data):
        self.inventory.add_group(group_name)

        for host in group_data.get("hosts", {}):
            self.inventory.add_host(host, group=group_name)

        for child_name, child_data in group_data.get("children", {}).items():
            self._parse_group_hierarchy(child_name, child_data)

        vars_dict = group_data.get("vars", {})
        if vars_dict:
            for k, v in vars_dict.items():
                self.inventory.set_variable(group_name, k, v)
