# SPRINT 1 — NeuroCad
**Version:** v0.1 · **Date:** 2026-04-07
 · FreeCAD Workbench + Context Builder

**Нед. 1–2 · Python 3.11 · FreeCAD 1.1.0+**

---

## Цель спринта

Пользователь открывает FreeCAD, активирует workbench NeuroCad, видит боковую панель и может получить текстовый снимок активного документа через debug action. LLM, executor, Settings UI — не в этом спринте.

---

## Задачи

### T1 · Scaffold репозитория
**Estimate:** 2ч

```
neurocad/
├── __init__.py
├── workbench.py
├── ui/
│   ├── panel.py
│   ├── widgets.py        # MessageBubble, StatusDot
│   └── settings.py       # заглушка — Sprint 3
├── core/
│   ├── context.py
│   └── history.py
├── config/
│   ├── config.py
│   └── defaults.py
├── llm/                  # заглушки — Sprint 2
│   ├── base.py
│   └── registry.py
├── tests/
│   ├── test_context.py
│   ├── test_history.py
│   └── test_config.py
└── pyproject.toml
```

`pyproject.toml` минимум:
```toml
[project]
name = "neurocad"
requires-python = ">=3.11"
dependencies = ["pydantic>=2.7", "keyring>=25.0"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt", "ruff", "mypy"]
```

Acceptance:
- `pip install -e .[dev]` проходит без ошибок
- `ruff check .` чистый
- `mypy .` чистый
- все тестовые файлы существуют (пустые фикстуры — ОК)

---

### T2 · FreeCAD Workbench
**Estimate:** 4ч

`workbench.py` регистрирует workbench, монтирует панель справа.

```python
from PySide6 import QtCore
import FreeCADGui

class CadCopilotWorkbench(FreeCADGui.Workbench):
    MenuText = "NeuroCad"
    ToolTip  = "LLM-assisted 3D modelling"

    def Initialize(self):
        from .ui.panel import CopilotPanel
        self.panel = CopilotPanel()
        FreeCADGui.getMainWindow().addDockWidget(
            QtCore.Qt.RightDockWidgetArea, self.panel
        )

    def Activated(self):    self.panel.show()
    def Deactivated(self):  self.panel.hide()
    def GetClassName(self): return "Gui::PythonWorkbench"

FreeCADGui.addWorkbench(CadCopilotWorkbench())
```

Acceptance:
- workbench появляется в меню FreeCAD
- панель открывается/закрывается при переключении workbench
- нет ошибок в FreeCAD Report view при загрузке

---

### T3 · CopilotPanel + widgets
**Estimate:** 7ч *(включает widgets.py)*

`ui/widgets.py` — базовые компоненты:
- `MessageBubble(role: str, text: str)` — QFrame с текстом, цвет по role
- `StatusDot` — QLabel с тремя состояниями: idle / thinking / error

`ui/panel.py` — минимальная панель: список сообщений + ввод + кнопка + debug action.

```python
class CopilotPanel(QDockWidget):
    message_submitted = Signal(str)    # пользователь отправил текст
    snapshot_requested = Signal()      # debug: показать снимок документа

    def _build_ui(self):
        # QScrollArea → список MessageBubble
        # QLineEdit (однострочный, Enter → submit)  ← не QTextEdit
        # QPushButton("Send")
        # QPushButton("Show Snapshot")  → emit snapshot_requested
        # StatusDot в заголовке
```

Acceptance:
- панель отображается без крэша
- ввод текста и Enter/Send → emit `message_submitted(str)`
- кнопка "Show Snapshot" → emit `snapshot_requested()`
- `StatusDot` меняет цвет при вызове `.set_state("thinking")`
- `MessageBubble` рендерится с разными role-цветами
- сигналы ловятся тестом через `pytest-qt`

---

### T4 · Context Builder
**Estimate:** 6ч

`core/context.py`:

```python
@dataclass
class ObjectInfo:
    name: str
    type_id: str
    shape_type: str | None
    volume_mm3: float | None
    placement: str
    visible: bool

@dataclass
class DocSnapshot:
    filename: str
    active_object: str | None
    objects: list[ObjectInfo]
    unit: str = "mm"

def capture(doc) -> DocSnapshot: ...
def to_prompt_str(snap: DocSnapshot) -> str: ...
```

`to_prompt_str` — компактный текст для LLM-промпта (не JSON):

```
doc: test.FCStd | unit: mm | active: Box
objects:
  Box  Part::Box  Solid  vol=8000.0  Pos=(0,0,0)  visible=True
  Cut  Part::Cut  Solid  vol=6200.0  Pos=(0,0,0)  visible=True
```

Debug action в `panel.py` при `snapshot_requested`:
```python
snap = context.capture(FreeCAD.ActiveDocument)
self._add_message("assistant", context.to_prompt_str(snap))
```

Acceptance (`test_context.py`):
- `capture()` на пустом документе → `DocSnapshot` с пустым `objects`
- `capture()` на документе с 3+ объектами разных типов → корректные поля
- объект без `Shape` → `shape_type=None`, `volume_mm3=None`, нет исключения
- `to_prompt_str()` ≤ 2000 символов при 20 объектах
- нажатие "Show Snapshot" в панели → текст снимка появляется в чате

---

### T5 · Config: load/save
**Estimate:** 3ч

`config/config.py` — чтение/запись без API key.

Acceptance (`test_config.py`):
- `load()` возвращает defaults при отсутствии файла
- `load()` мержит файл с defaults; неизвестные ключи игнорируются
- `save()` не пишет `api_key` даже если передан в dict
- `load()` вычищает `api_key` если он оказался в файле

---

### T6 · History (prep-task)
**Estimate:** 2ч

Инфраструктурная задача для Sprint 2. В Sprint 1 реализуется и покрывается тестами, но UI не использует.

```python
class Role(StrEnum):
    USER      = "user"
    ASSISTANT = "assistant"
    FEEDBACK  = "feedback"

@dataclass
class Turn:
    role: Role
    content: str

class History:
    def add(self, role: Role, content: str) -> None: ...
    def to_llm_messages(self) -> list[dict]: ...  # FEEDBACK → "user"
    def clear(self) -> None: ...
```

Acceptance (`test_history.py`):
- `to_llm_messages()` конвертирует FEEDBACK → role=user
- USER и ASSISTANT проходят без изменений
- `clear()` обнуляет историю

---

## Definition of Done — Sprint 1

- [ ] Workbench загружается в FreeCAD 1.1.0+ без ошибок в Report view
- [ ] Панель открывается, `QLineEdit` принимает ввод, emit `message_submitted`
- [ ] `MessageBubble` и `StatusDot` рендерятся корректно
- [ ] "Show Snapshot" показывает текст снимка в чате
- [ ] `capture(doc)` работает на пустом и непустом документе
- [ ] `to_prompt_str()` ≤ 2000 символов при 20 объектах
- [ ] `save(config)` не пишет `api_key`
- [ ] `to_llm_messages()` конвертирует FEEDBACK → user
- [ ] `pip install -e .[dev]` — чистый
- [ ] `ruff check .` — чистый
- [ ] `mypy .` — чистый
- [ ] `pytest` — все тесты зелёные
- [ ] Ручная проверка: FreeCAD → создать Box → "Show Snapshot" → Box виден в тексте

---

## Не в этом спринте

- LLM adapter, executor, validator, agent loop — Sprint 2
- Settings UI (провайдер / ключ / base_url) — Sprint 3
- Undo / export / streaming — Sprint 3
- Packaging / Addon Manager — post-MVP
