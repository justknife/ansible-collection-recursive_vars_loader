# 🔁 Ansible Inventory Plugin: `autovars`

Плагин `autovars` — это кастомный inventory-плагин Ansible, который:

- автоматически ищет `group_vars/all.yaml` вверх по дереву (до 3 уровней)
- загружает переменные из него
- назначает их вымышленному хосту `localhost` с локальным подключением
- не требует задач, ролей, `include_vars` или `vars_files`

Полностью автоматическая подгрузка переменных **только силами плагина**.

---

## 📦 Структура проекта

```plaintext
project/
├── ansible.cfg
├── plugins/
│   └── inventory/
│       └── autovars.py         # <- этот плагин
├── group_vars/
│   └── all.yaml                # <- переменные, которые будут подгружены
├── inventory.yaml              # <- inventory, ссылающийся на плагин
└── playbook.yml
```

⚙️ Установка
Помести autovars.py в plugins/inventory/

Укажи путь к плагинам в ansible.cfg:

```
[defaults]
inventory_plugins = ./plugins/inventory
inventory = ./inventory.yaml
```
