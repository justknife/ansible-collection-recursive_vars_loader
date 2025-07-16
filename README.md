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

Fully automatic variable loading using ***only the plugin itself***.





---

## 📦 Project structure sample

```plaintext
project
├──inventories/
│       └── project1/
│           ├── group_vars/
│           │   └── project1_specific.yaml
│           └── dev/
│                 └── inventory.yaml
│                 └── group_vars/sample_vars.yaml
│       └── project2/
│           ├── group_vars/
│           │    └── project2_specific.yaml
│           └── prod
│               └── inventory.yaml
│               └── group_vars/sample_vars.yaml
│__play.yaml
```

Now u can load recursive group_vars/*.yaml(vars) when running for sample

```shell
ansible-playbook play.yaml -i inventories/project2/prod/inventory.yaml
```

## Installation
```shell
ansible-galaxy collection install justknife.recursive_vars
```
then just add into inventory.yaml
```yaml
plugin: justknife.recursive_vars.autovars
```

or if install manually add into project ***autovars.py*** or dir plugins
then in ansible.cfg put
```ini
inventory_plugins = ./plugins/inventory
```


Set the plugin path in ansible.cfg:

```
[defaults]
inventory_plugins = ./plugins/inventory
inventory = ./inventory.yaml
```
