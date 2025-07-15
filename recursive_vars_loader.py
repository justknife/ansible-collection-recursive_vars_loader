from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleFileNotFound

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        result = super(ActionModule, self).run(tmp, task_vars)

        # Путь к директории, откуда запущен playbook
        base_dir = os.path.abspath(task_vars.get('playbook_dir', '.'))

        loaded = []
        for level in range(4):  # на 0, 1, 2, 3 уровня вверх
            path = os.path.join(base_dir, *(['..'] * level), 'group_vars', 'all.yaml')
            path = os.path.abspath(path)

            if os.path.exists(path):
                self._display.display(f"Loading vars from: {path}")
                try:
                    data = self._loader.load_from_file(path)
                    task_vars.update(data)
                    loaded.append(path)
                except Exception as e:
                    raise AnsibleFileNotFound(f"Failed to load {path}: {str(e)}")

        result['loaded_group_vars'] = loaded
        result['changed'] = False
        return result
