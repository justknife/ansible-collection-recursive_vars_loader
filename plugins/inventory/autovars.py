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

        project_root = os.path.abspath(os.getcwd())  # предполагаем, что ansible запускается из корня проекта
        current_dir = basedir
        all_vars = {}
        any_found = False

        while True:
            gv_path = os.path.join(current_dir, 'group_vars', 'all.yaml')
            if os.path.exists(gv_path):
                self.display.v(f"[autovars] Loading vars from {gv_path}")
                with open(gv_path, 'r', encoding='utf-8') as f:
                    group_vars_data = yaml.safe_load(f) or {}
                    if not isinstance(group_vars_data, dict):
                        raise AnsibleError(f"Expected dict in {gv_path}, got {type(group_vars_data)}")
                    all_vars.update(group_vars_data)
                    any_found = True

            # стоп, если достигли inventories или вышли за пределы корня
            if os.path.basename(current_dir) == 'inventories':
                break
            if not os.path.commonpath([current_dir, project_root]) == project_root:
                self.display.v(f"[autovars] Reached outside project root: {project_root}. Stopping.")
                break

            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break

            current_dir = parent_dir

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

        hosts_dict = group_data.get("hosts", {})
        for host, host_data in hosts_dict.items():
            self.inventory.add_host(host, group=group_name)
            if isinstance(host_data, dict):
                for var_key, var_value in host_data.items():
                    self.inventory.set_variable(host, var_key, var_value)

        for child_name, child_data in group_data.get("children", {}).items():
            self._parse_group_hierarchy(child_name, child_data)
            self.inventory.add_child(group_name, child_name)

        vars_dict = group_data.get("vars", {})
        if vars_dict:
            for k, v in vars_dict.items():
                self.inventory.set_variable(group_name, k, v)
