# 🔁 Ansible Callback Plugin: `autoload_vars` + Task-Based Fallback `recursive_vars_loader`

Этот репозиторий содержит два подхода для автоматической загрузки `group_vars/all.yaml` из родительских директорий проекта:

---

## 📦 1. Callback Plugin — `autoload_vars`

### 🧠 Что делает

Плагин `autoload_vars` автоматически поднимается вверх по директориям (до 3 уровней) от `playbook_dir` и ищет `group_vars/all.yaml`.  
Если находит — автоматически загружает переменные **до старта playbook**, без необходимости писать `tasks`, `roles` или `include_vars`.

### 📁 Пример структуры

inventories/
└── nginx/
└── project1/
├── group_vars/
│ └── all.yaml ← общие переменные
└── dev/
├── group_vars/
│ └── all.yaml ← переменные окружения
├── inventory


### ⚙️ Установка

1. Положи файл `autoload_vars.py` в директорию `plugins/callback/`
2. В `ansible.cfg` укажи:

```ini
[defaults]
callback_plugins = ./plugins/callback
callbacks_enable = profile_tasks,autoload_vars


Никаких действий не требуется — просто запускай playbook как обычно:

bash
Копировать
Редактировать
ansible-playbook -i inventories/nginx/project1/dev/inventory playbook.yml


- name: Load project-level group_vars
  hosts: all
  gather_facts: false

  tasks:
    - name: Load recursive group_vars
      recursive_vars_loader:

    - debug:
        var: common_var
