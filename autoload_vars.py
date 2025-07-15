from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
from ansible.plugins.callback import CallbackBase

class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'autoload_vars'

    def on_play_start(self, play):
        playbook_dir = play._variable_manager._loader.get_basedir()
        loader = play._variable_manager._loader
        vars_manager = play._variable_manager

        levels_up = 3
        loaded_paths = []

        for level in range(levels_up + 1):
            gv_path = os.path.abspath(
                os.path.join(playbook_dir, *(['..'] * level), 'group_vars', 'all.yaml')
            )
            if os.path.exists(gv_path):
                self._display.display(f"AUTOLOAD: including vars from {gv_path}")
                data = loader.load_from_file(gv_path)
                vars_manager.extra_vars.update(data)
                loaded_paths.append(gv_path)

        if not loaded_paths:
            self._display.display("AUTOLOAD: no group_vars/all.yaml found above playbook")
