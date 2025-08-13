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
        # Разрешаем оба варианта имени
        return os.path.basename(path) in ('inventory.yaml', 'inventory.yml')

    def parse(self, inventory, loader, path, cache=True):
        self.loader = loader
        self.inventory = inventory
        basedir = os.path.dirname(path)

        # Pending host vars to apply LAST (so they win)
        self._pending_host_vars = {}

        # 0) Load inventory.yaml (params + structure)
        config_data = loader.load_from_file(path) or {}
        if not isinstance(config_data, dict):
            raise AnsibleError(f"Expected dict in {path}, got {type(config_data)}")

        configured_project_name = config_data.get("project_name")
        configured_names = config_data.get("allowed_group_files", ["all", "main"])
        allowed_names = set(n.lower() for n in configured_names)

        # 1) Infer project/env from path
        inventory_parts = os.path.normpath(path).split(os.sep)
        inferred_project_name = None
        inferred_env_name = None
        try:
            inventories_index = inventory_parts.index("inventories")
            inferred_project_name = inventory_parts[inventories_index + 2]
        except (ValueError, IndexError):
            pass
        try:
            inferred_env_name = inventory_parts[inventories_index + 3]
        except (ValueError, IndexError):
            pass

        project_name = (configured_project_name or inferred_project_name)
        if project_name:
            allowed_names.add(project_name.lower())
        if inferred_env_name:
            allowed_names.add(inferred_env_name.lower())

        self.display.v(f"[autovars] Project name: {project_name}")
        self.display.v(f"[autovars] Env name: {inferred_env_name}")
        self.display.v(f"[autovars] Allowed group_var base names: {sorted(allowed_names)}")

        # 2) Parse inventory structure, but DO NOT set host vars yet (queue them)
        for group_name, group_data in config_data.items():
            if group_name in ("plugin", "allowed_group_files", "project_name"):
                continue
            if not isinstance(group_data, dict):
                continue
            self._parse_group_hierarchy(group_name, group_data)

        # 3) Build dirs chain up to "inventories"
        dirs_chain = []
        current_dir = basedir
        project_root = os.path.abspath(os.getcwd())

        while True:
            dirs_chain.append(current_dir)
            if os.path.basename(current_dir) == "inventories":
                break
            if not os.path.commonpath([current_dir, project_root]) == project_root:
                self.display.v(f"[autovars] Reached outside project root: {project_root}. Stopping.")
                break
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir

        # ---------- helpers: deep merge + deterministic file ordering ----------

        def deep_merge(dst, src):
            """
            dict <- dict
            - dict + dict: рекурсивный merge с перезаписью по ключу
            - list: полная замена (last write wins)
            - остальные типы: замена
            """
            for k, v in src.items():
                if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
                    deep_merge(dst[k], v)
                else:
                    dst[k] = v

        def sorted_allowed_files(dir_path):
            """
            Вернёт *.yml|*.yaml, отфильтрованные по allowed_names и
            отсортированные по приоритету в рамках каталога:
              all == main (самые низкие, одинаковый ранг)
              затем <project>
              затем <env>
              затем прочие — по алфавиту.
            """
            prj = (project_name or "").lower()
            env = (inferred_env_name or "").lower()

            def rank(base):
                bl = base.lower()
                if bl in ("all", "main"):
                    return (0, 0 if bl == "all" else 1, bl)  # одинаковая ступень, но стабильность all перед main
                if prj and bl == prj:
                    return (1, 0, bl)
                if env and bl == env:
                    return (2, 0, bl)
                return (3, 0, bl)  # прочие по алфавиту на последней ступени

            files = []
            try:
                for fname in os.listdir(dir_path):
                    base, ext = os.path.splitext(fname)
                    if ext.lower() not in ('.yaml', '.yml'):
                        continue
                    if base.lower() not in allowed_names:
                        self.display.v(f"[autovars] Skipping {fname} — not in allowed list")
                        continue
                    files.append(fname)
            except FileNotFoundError:
                return []

            return sorted(files, key=lambda fn: rank(os.path.splitext(fn)[0]))

        # 4) Merge group_vars with ascending priority (root -> project -> env)
        all_vars = {}
        any_found = False

        for lvl_dir in reversed(dirs_chain):  # сначала inventories/, потом ниже и ниже, так глубже перезапишет
            group_vars_dir = os.path.join(lvl_dir, "group_vars")
            self.display.v(f"[autovars] Scanning: {group_vars_dir}")

            if not os.path.isdir(group_vars_dir):
                continue

            for fname in sorted_allowed_files(group_vars_dir):
                gv_path = os.path.join(group_vars_dir, fname)
                self.display.v(f"[autovars] Loading vars from {gv_path}")
                try:
                    with open(gv_path, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                        if not isinstance(data, dict):
                            raise AnsibleError(f"Expected dict in {gv_path}, got {type(data)}")
                        # глубокий merge: списки полностью заменяются, словари мержатся
                        deep_merge(all_vars, data)
                        any_found = True
                except Exception as e:
                    raise AnsibleError(f"[autovars] Failed to load {gv_path}: {e}")

        if not any_found:
            self.display.v("[autovars] No group_vars/*.yml|*.yaml files loaded.")

        # 5) Apply merged group vars to a target group (NOT to every host)
        target_group = 'all'
        self.inventory.add_group(target_group)
        for k, v in all_vars.items():
            self.inventory.set_variable(target_group, k, v)

        # 6) Apply queued host vars LAST so they override any group vars from this source
        for host, vars_dict in self._pending_host_vars.items():
            for k, v in vars_dict.items():
                self.inventory.set_variable(host, k, v)

        # 7) Ensure we actually have hosts
        if not self.inventory.hosts:
            raise AnsibleError("[autovars] No hosts found in inventory to inject vars into.")

    def _parse_group_hierarchy(self, group_name, group_data):
        self.inventory.add_group(group_name)

        # Hosts: add now, but queue their variables to apply at the end
        hosts_dict = group_data.get("hosts", {})
        for host, host_data in hosts_dict.items():
            self.inventory.add_host(host, group=group_name)
            if isinstance(host_data, dict):
                self._pending_host_vars.setdefault(host, {}).update(host_data)

        # Children
        for child_name, child_data in group_data.get("children", {}).items():
            self._parse_group_hierarchy(child_name, child_data)
            self.inventory.add_child(group_name, child_name)

        # Group vars from inventory.yaml (как и было)
        vars_dict = group_data.get("vars", {})
        if vars_dict:
            for k, v in vars_dict.items():
                self.inventory.set_variable(group_name, k, v)
