# 🔁 Ansible Inventory Plugin: `autovars`

## Quick start
```shell
ansible-galaxy collection install justknife.recursive_vars
```


The `autovars` plugin is a custom Ansible inventory plugin that:

- Automatically searches for group_vars/all.yaml up to 3 levels up the directory tree
- Loads variables from that file
- Assigns them to a dummy host localhost with local connection
- не требует задач, ролей, `include_vars` или `vars_files`

Requires no tasks, roles, include_vars, or vars_files

Fully automatic variable loading using only the plugin itself.



Полностью автоматическая подгрузка переменных **только силами плагина**.

---

## 📦 Project structure 

```plaintext
project/
├── ansible.cfg
├── plugins/
│   └── inventory/
│       └── autovars.py         # <- the plugin
├── group_vars/
│   └── all.yaml                # <- variables to be loaded
├── inventory.yaml              # <- inventory referencing the plugin
└── playbook.yml

```

## Installation
Place autovars.py in plugins/inventory/.


Set the plugin path in ansible.cfg:

```
[defaults]
inventory_plugins = ./plugins/inventory
inventory = ./inventory.yaml
```
