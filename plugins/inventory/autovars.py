from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os
import yaml

from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.errors import AnsibleError

DOCUMENTATION = r'''
name: autovars
plugin_type: inventory
short_description: Inventory plugin that loads vars from nearby group_vars YAML files
description:
  - Recursively searches for group_vars/*.yaml up to the inventories root or project root.
    Only allowed file names (without extension) will be processed.
options:
  plugin:
    description: The name of the plugin
    required: true
    choices: ['autovars']
  allowed_group_files:
    description: >
      List of allowed base names (without .yaml) in group_vars that will be loaded.
      Example: ['all', 'main', 'project1']
    required: false
    type: list
    elements: str
    default: ['all', 'main']
  project_name:
    description: >
      Optional override of project name to use when deciding which group_vars files to load.
      If not specified, it will be inferred as the second directory under "inventories".
    required: false
    type: str
'''

class InventoryModule(BaseInventoryPlugin):
    NAME = 'autovars'

    def verify_file(self, path):
        return os.path.basename(path) == 'inventory.yaml'

    def parse(self, inventory, loader, path, cache=True):
        self.loader = loader
        self.inventory = inventory
        basedir = os.path.dirname(path)

        # load inventory file for manual param parsing
        config_data = loader.load_from_file(path) or {}

        configured_project_name = config_data.get("project_name")
        configured_names = config_data.get("allowed_group_files", ["all", "main"])
        allowed_names = set(n.lower() for n in configured_names)

        # infer project name from inventory path
        inventory_parts = os.path.normpath(path).split(os.sep)
        try:
            inventories_index = inventory_parts.index("inventories")
            inferred_project_name = inventory_parts[inventories_index + 2]
        except (ValueError, IndexError):
            inferred_project_name = None

        project_name = (configured_project_name or inferred_project_name)
        if project_name:
            allowed_names.add(project_name.lower())

        self.display.v(f"[autovars] Project name: {project_name}")
        self.display.v(f"[autovars] Allowed group_var base names: {sorted(allowed_names)}")

        # parse inventory structure
        if not isinstance(config_data, dict):
            raise AnsibleError(f"Expected dict in {path}, got {type(config_data)}")

        for group_name, group_data in config_data.items():
            if group_name in ("plugin", "allowed_group_files", "project_name"):
                continue
            if not isinstance(group_data, dict):
                continue
            self._parse_group_hierarchy(group_name, group_data)

        all_vars = {}
        any_found = False
        project_root = os.path.abspath(os.getcwd())
        current_dir = basedir

        while True:
            group_vars_dir = os.path.join(current_dir, "group_vars")
            self.display.v(f"[autovars] Scanning: {group_vars_dir}")

            if os.path.isdir(group_vars_dir):
                for fname in os.listdir(group_vars_dir):
                    basename, ext = os.path.splitext(fname)
                    if ext.lower() not in ('.yaml', '.yml'):
                        self.display.v(f"[autovars] Ignoring {fname} (unsupported extension)")
                        continue

                    if basename.lower() not in allowed_names:
                        self.display.v(f"[autovars] Skipping {fname} — not in allowed list")
                        continue

                    gv_path = os.path.join(group_vars_dir, fname)
                    self.display.v(f"[autovars] Loading vars from {gv_path}")
                    try:
                        with open(gv_path, 'r', encoding='utf-8') as f:
                            group_vars_data = yaml.safe_load(f) or {}
                            if not isinstance(group_vars_data, dict):
                                raise AnsibleError(f"Expected dict in {gv_path}, got {type(group_vars_data)}")

                            for k, v in group_vars_data.items():
                                if k in all_vars:
                                    self.display.v(f"[autovars] Overriding {k}: {all_vars[k]} -> {v}")
                                all_vars[k] = v
                            any_found = True
                    except Exception as e:
                        raise AnsibleError(f"[autovars] Failed to load {gv_path}: {e}")

            if os.path.basename(current_dir) == "inventories":
                break
            if not os.path.commonpath([current_dir, project_root]) == project_root:
                self.display.v(f"[autovars] Reached outside project root: {project_root}. Stopping.")
                break

            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir

        if not any_found:
            self.display.v("[autovars] No group_vars/*.yaml files loaded.")

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
