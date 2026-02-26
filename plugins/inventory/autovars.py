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
        return os.path.basename(path) in ('inventory.yaml', 'inventory.yml')

    def parse(self, inventory, loader, path, cache=True):
        self.loader = loader
        self.inventory = inventory
        basedir = os.path.dirname(path)

        self._pending_host_vars = {}

        config_data = loader.load_from_file(path) or {}
        if not isinstance(config_data, dict):
            raise AnsibleError(f"Expected dict in {path}, got {type(config_data)}")

        configured_project_name = config_data.get("project_name")
        configured_names = config_data.get("allowed_group_files", ["all", "main"])
        allowed_names = set(n.lower() for n in configured_names)

        inventory_parts = os.path.normpath(path).split(os.sep)
        inferred_project_name = None
        inferred_env_name = None

        try:
            inventories_index = inventory_parts.index("inventories")
            inferred_project_name = inventory_parts[inventories_index + 2]
            inferred_env_name = inventory_parts[inventories_index + 3]
        except (ValueError, IndexError):
            pass

        project_name = configured_project_name or inferred_project_name
        if project_name:
            allowed_names.add(project_name.lower())
        if inferred_env_name:
            allowed_names.add(inferred_env_name.lower())

        for group_name, group_data in config_data.items():
            if group_name in ("plugin", "allowed_group_files", "project_name"):
                continue
            if not isinstance(group_data, dict):
                continue
            self._parse_group_hierarchy(group_name, group_data)

        dirs_chain = []
        current_dir = basedir
        project_root = os.path.abspath(os.getcwd())

        while True:
            dirs_chain.append(current_dir)
            if os.path.basename(current_dir) == "inventories":
                break
            if not os.path.commonpath([current_dir, project_root]) == project_root:
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir

        def deep_merge(dst, src):
            for k, v in src.items():
                if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v

        def sorted_allowed_files(dir_path):
            prj = (project_name or "").lower()
            env = (inferred_env_name or "").lower()

            def rank(base):
                bl = base.lower()
                if bl in ("all", "main"):
                    return (0, bl)
                if prj and bl == prj:
                    return (1, bl)
                if env and bl == env:
                    return (2, bl)
                return (3, bl)

            files = []
            try:
                for fname in os.listdir(dir_path):
                    base, ext = os.path.splitext(fname)
                    if ext.lower() not in ('.yaml', '.yml'):
                        continue
                    if base.lower() not in allowed_names:
                        continue
                    files.append(fname)
            except FileNotFoundError:
                return []

            return sorted(files, key=lambda fn: rank(os.path.splitext(fn)[0]))

        # --- Load group_vars ---
        all_vars = {}
        for lvl_dir in reversed(dirs_chain):
            group_vars_dir = os.path.join(lvl_dir, "group_vars")
            if not os.path.isdir(group_vars_dir):
                continue

            for fname in sorted_allowed_files(group_vars_dir):
                gv_path = os.path.join(group_vars_dir, fname)
                try:
                    with open(gv_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        if not isinstance(data, dict):
                            raise AnsibleError(f"Expected dict in {gv_path}, got {type(data)}")
                        deep_merge(all_vars, data)
                except Exception as e:
                    raise AnsibleError(f"[autovars] Failed to load {gv_path}: {e}")

        self.inventory.add_group('all')
        for k, v in all_vars.items():
            self.inventory.set_variable('all', k, v)

        for host, vars_dict in self._pending_host_vars.items():
            for k, v in vars_dict.items():
                self.inventory.set_variable(host, k, v)

        if not self.inventory.hosts:
            raise AnsibleError("[autovars] No hosts found in inventory.")


    def _parse_group_hierarchy(self, group_name, group_data):
        self.inventory.add_group(group_name)

        if group_data is None:
            group_data = {}
        if not isinstance(group_data, dict):
            raise AnsibleError(f"[autovars] Group '{group_name}' must be a dict.")

        # --- Hosts (safe handling) ---
        hosts_dict = group_data.get("hosts") or {}
        if not isinstance(hosts_dict, dict):
            raise AnsibleError(f"[autovars] Group '{group_name}'.hosts must be a dict.")

        for host, host_data in hosts_dict.items():
            self.inventory.add_host(host, group=group_name)
            if isinstance(host_data, dict):
                self._pending_host_vars.setdefault(host, {}).update(host_data)

        children_dict = group_data.get("children") or {}

        if not children_dict:
            shorthand = {
                k: v for k, v in group_data.items()
                if k not in ("hosts", "vars", "children")
            }
            if shorthand:
                children_dict = shorthand

        if not isinstance(children_dict, dict):
            raise AnsibleError(f"[autovars] Group '{group_name}'.children must be a dict.")

        for child_name, child_data in children_dict.items():
            if child_data is None:
                self.inventory.add_group(child_name)
            elif isinstance(child_data, dict):
                self._parse_group_hierarchy(child_name, child_data)
            else:
                raise AnsibleError(
                    f"[autovars] Child '{child_name}' in group '{group_name}' must be dict or null."
                )

            self.inventory.add_child(group_name, child_name)

        # --- Group vars ---
        vars_dict = group_data.get("vars") or {}
        if not isinstance(vars_dict, dict):
            raise AnsibleError(f"[autovars] Group '{group_name}'.vars must be a dict.")

        for k, v in vars_dict.items():
            self.inventory.set_variable(group_name, k, v)