# ARCH — NeuroCad
**Version:** v0.1 · **Date:** 2026-04-07


**Python 3.11 · FreeCAD 1.1.0+ · провайдер-агностик LLM**

---

## Структура репозитория

```
neurocad/
├── __init__.py
├── InitGui.py               # FreeCAD GUI entrypoint — обязателен для регистрации workbench
├── workbench.py             # определение класса CadCopilotWorkbench
│
├── ui/
│   ├── panel.py             # Qt боковая панель (chat + input + streaming)
│   ├── settings.py          # Settings dialog: провайдер / модель / ключ / base_url
│   └── widgets.py           # CodeBlock, StatusDot, MessageBubble, ProgressBar
│
├── core/
│   ├── agent.py             # главный цикл: prompt → llm → exec → validate → commit/rollback
│   ├── context.py           # читает FreeCAD doc → DocSnapshot
│   ├── prompt.py            # system prompt + context → строка; to_llm_messages — в History
│   ├── executor.py          # safe exec в whitelist namespace
│   ├── validator.py         # проверяет геометрию после exec
│   ├── exporter.py          # STEP / STL export
│   └── history.py           # хранит Turn(role, content) — внутренняя схема продукта
│
├── llm/
│   ├── base.py              # Protocol: LLMAdapter, LLMResponse
│   ├── anthropic.py         # AnthropicAdapter
│   ├── openai.py            # OpenAIAdapter (+ ollama, lm-studio, openrouter)
│   └── registry.py          # ADAPTERS, load_adapter(config), load_adapter_with_session_key(config, key)
│
├── config/
│   ├── config.py            # load/save config; политика API key
│   └── defaults.py          # DEFAULT_SYSTEM_PROMPT, SANDBOX_WHITELIST, MVP_OPERATIONS
│
└── tests/
    ├── test_context.py
    ├── test_executor.py      # sandbox whitelist, timeout, max objects
    ├── test_validator.py
    ├── test_agent.py         # retry semantics, history structure, rollback
    ├── test_adapters.py      # provider switching, base_url override
    ├── test_exporter.py
    ├── test_config.py        # key precedence: env > keyring; при отсутствии — ValueError
    └── benchmark.py          # кодовый прогон 50 задач; не unit test, запускается вручную
```

---

## Слои и ответственность

```
┌──────────────────────────────────────┐
│  UI layer  (ui/)                     │  Qt widgets, streaming, progress
├──────────────────────────────────────┤
│  Agent  (core/agent.py)              │  оркестрация, retry, rollback
├─────────────────┬────────────────────┤
│  Context        │  Prompt            │  чтение doc / сборка промпта
├─────────────────┴────────────────────┤
│  LLM Adapter  (llm/)                 │  единый интерфейс к любому LLM
├──────────────────────────────────────┤
│  Executor → Validator → Exporter     │  sandbox exec, геом. проверка, экспорт
├──────────────────────────────────────┤
│  FreeCAD Python API  (Part only MVP) │  внешняя зависимость
└──────────────────────────────────────┘
```

---

## Контракты

### LLMAdapter (единственная каноническая сигнатура)

```python
# llm/base.py
from typing import Protocol, Iterator
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str          # сгенерированный Python-код (только код, без markdown)
    input_tokens: int
    output_tokens: int
    stop_reason: str      # "end_turn" | "max_tokens" — "tool_use" не используется в MVP

class LLMAdapter(Protocol):
    def complete(
        self,
        messages: list[dict],    # [{"role": "user"|"assistant", "content": str}]
        system: str,
        tools: list[dict] | None = None,  # зарезервировано; в MVP не используется
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[dict],
        system: str,
    ) -> Iterator[str]: ...   # yields content chunks; добавлен в Sprint 3
```

### DocSnapshot

```python
# core/context.py
from dataclasses import dataclass, field

@dataclass
class ObjectInfo:
    name: str
    type_id: str            # "Part::Box", "Part::Cut", ...
    shape_type: str | None  # "Solid", "Shell", "Compound", ...
    volume_mm3: float | None
    placement: str          # "Pos=(0,0,0) Yaw=0 Pitch=0 Roll=0"
    visible: bool

@dataclass
class DocSnapshot:
    filename: str
    active_object: str | None
    objects: list[ObjectInfo] = field(default_factory=list)
    unit: str = "mm"

def capture(doc) -> DocSnapshot: ...
def to_prompt_str(snap: DocSnapshot) -> str: ...
```

### ExecResult

```python
# core/executor.py
from dataclasses import dataclass, field

@dataclass
class ExecResult:
    ok: bool
    error: str | None = None
    traceback: str | None = None
    new_objects: list[str] = field(default_factory=list)
    rolled_back: bool = False
```

### AgentResult

```python
# core/agent.py
from dataclasses import dataclass, field

@dataclass
class AgentResult:
    ok: bool
    code: str | None = None
    objects: list[str] = field(default_factory=list)
    attempts: int = 0
    error: str | None = None
    rolled_back: bool = False
```

### AgentCallbacks (добавлен в Sprint 3)

```python
# core/agent.py
from typing import Callable

@dataclass
class AgentCallbacks:
    on_chunk: Callable[[str], None]          # chunk текста → live update UI
    on_attempt: Callable[[int, int], None]   # (attempt, max) → ProgressBar
```

### load_adapter_with_session_key (registry public contract)

```python
# llm/registry.py
def load_adapter_with_session_key(config: dict, session_key: str) -> LLMAdapter:
    """Создать адаптер с session-only ключом (Use once).
    Ключ не записывается в keyring. _resolve_api_key() не вызывается.
    Вызывается напрямую из ui/settings.py при выборе Use once.
    """
```

---

## Agent: главный цикл

### Две схемы — продуктовая история и LLM-проекция

`history.py` — единственный владелец трансформации Turn → LLM-формат.
`prompt.py` не дублирует `to_llm_messages` — вызывает `history.to_llm_messages()` напрямую.

```python
# core/history.py
from dataclasses import dataclass
from enum import StrEnum

class Role(StrEnum):
    USER      = "user"
    ASSISTANT = "assistant"
    FEEDBACK  = "feedback"   # retry traceback — внутренняя роль, не идёт в LLM напрямую

@dataclass
class Turn:
    role: Role
    content: str

class History:
    def __init__(self) -> None:
        self._turns: list[Turn] = []

    def add(self, role: Role, content: str) -> None:
        self._turns.append(Turn(role, content))

    def to_llm_messages(self) -> list[dict]:
        """Единственный владелец трансформации. FEEDBACK → role=user при отправке."""
        return [
            {"role": "user" if t.role == Role.FEEDBACK else t.role,
             "content": t.content}
            for t in self._turns
        ]

    def items(self) -> list[Turn]:
        """Read-only список turn-ов — используется в тестах для проверки структуры истории."""
        return list(self._turns)

    def clear(self) -> None:
        self._turns.clear()
```

### Цикл агента

```python
# core/agent.py
MAX_RETRIES = 3

def run(
    user_message: str,
    doc,
    adapter: LLMAdapter,
    history: History,                          # core/history.py
    callbacks: AgentCallbacks | None = None,   # Sprint 3: live UI updates
) -> AgentResult:

    snap = context.capture(doc)
    system = prompt.build_system(snap)

    # user message добавляется один раз
    history.add(Role.USER, user_message)

    for attempt in range(MAX_RETRIES):
        if callbacks:
            callbacks.on_attempt(attempt + 1, MAX_RETRIES)

        messages = history.to_llm_messages()

        # Sprint 3: streaming path через callbacks
        # Sprint 1-2: fallback на complete() если callbacks=None
        if callbacks:
            chunks: list[str] = []
            for chunk in adapter.stream(messages, system):
                chunks.append(chunk)
                callbacks.on_chunk(chunk)
            code = extract_code("".join(chunks))
        else:
            response = adapter.complete(messages, system)
            code = extract_code(response.content)

        result = _execute_with_rollback(code, doc)

        if result.ok:
            history.add(Role.ASSISTANT, code)
            return AgentResult(ok=True, code=code,
                               objects=result.new_objects, attempts=attempt + 1)

        # feedback — отдельный внутренний turn, не перезаписывает user
        history.add(
            Role.FEEDBACK,
            f"Ошибка на попытке {attempt + 1}:\n{result.traceback}\n\nИсправь код."
        )

    return AgentResult(ok=False, error="Превышено число попыток",
                       attempts=MAX_RETRIES, rolled_back=True)


def _execute_with_rollback(code: str, doc) -> ExecResult:
    """
    Lifecycle одного запроса:
      execute() → doc.recompute() → validator.check() → commit
                                                       → rollback при любой ошибке
    Документ никогда не остаётся в частично изменённом состоянии.
    """
    import traceback
    # Snapshot через FreeCAD транзакцию.
    # doc.openTransaction() / doc.abortTransaction() — нативный FreeCAD undo stack.
    # Сохраняет: объекты, placement, visibility, labels, зависимости, active object.
    # Не сохраняет: внешние файлы, состояние viewport камеры.
    doc.openTransaction("CADCopilot")
    try:
        result = executor.execute(code, doc)
        if not result.ok:
            doc.abortTransaction()
            result.rolled_back = True
            return result

        doc.recompute()
        valid = validator.check(doc, result.new_objects)
        if not valid.ok:
            doc.abortTransaction()
            return ExecResult(ok=False,
                              traceback=f"Геометрия невалидна: {valid.reason}",
                              rolled_back=True)

        doc.commitTransaction()  # commit — попадает в FreeCAD undo stack
        return result
    except Exception:
        doc.abortTransaction()
        return ExecResult(ok=False, traceback=traceback.format_exc(), rolled_back=True)
```

---

## Sandbox

### Разрешённые модули (MVP)

```python
# config/defaults.py
SANDBOX_WHITELIST: set[str] = {
    "FreeCAD", "App", "Base", "Part", "math", "json",
}
# Sketcher, Draft, PartDesign — вне MVP, не импортируются, не в whitelist
```

### Namespace

```python
# core/executor.py
def _build_namespace(doc) -> dict:
    import FreeCAD, Part, math, json
    return {
        "FreeCAD": FreeCAD,
        "App":     FreeCAD,
        "Base":    FreeCAD.Base,
        "Part":    Part,
        "doc":     doc,
        "math":    math,
        "json":    json,
        "__builtins__": {
            "print": print, "range": range, "len": len,
            "round": round, "abs": abs, "min": min, "max": max,
            "list": list, "dict": dict, "str": str,
            "float": float, "int": int, "bool": bool,
        },
    }
```

Недоступны: `os`, `sys`, `subprocess`, `open`, `__import__`, `eval`, `exec` (вложенный).

### Политика исполнения

| Параметр | Значение |
|---|---|
| Timeout exec | 10 сек |
| Макс. новых объектов за ход | 5 |
| Удаление существующих объектов | запрещено без явной команды пользователя |
| Циклический recompute | запрещён |
| LLM-ответ содержит только код | запрещены fenced code blocks (` ``` `) и `import`/`from` statements; комментарии (`#`) допустимы |

---

## LLM Registry

```python
# llm/registry.py
from .anthropic import AnthropicAdapter
from .openai import OpenAIAdapter

ADAPTERS: dict[str, type[LLMAdapter]] = {
    "anthropic":         AnthropicAdapter,
    "openai":            OpenAIAdapter,
    "ollama":            OpenAIAdapter,
    "openai-compatible": OpenAIAdapter,
}

def load_adapter(config: dict) -> LLMAdapter:
    cls = ADAPTERS.get(config["provider"])
    if cls is None:
        raise ValueError(f"Unknown provider: {config['provider']}")
    return cls(
        api_key=_resolve_api_key(config),
        model=config["model"],
        base_url=config.get("base_url"),
        max_tokens=config.get("max_tokens", 4096),
        temperature=config.get("temperature", 0),
    )

def _resolve_api_key(config: dict) -> str:
    """env > keyring; при отсутствии — ValueError. Config field не используется."""
    import os, keyring
    if key := os.environ.get("NEUROCAD_API_KEY"):
        return key
    if key := keyring.get_password("neurocad", config.get("provider", "")):
        return key
    raise ValueError(
        "API key not found. Set NEUROCAD_API_KEY env var, "
        "save via Settings UI (Save), or use Settings UI (Use once)."
    )

# Transient path: ключ введён в Settings UI без сохранения (Use once).
# ui/settings.py вызывает эту функцию напрямую; _resolve_api_key() не задействован.
def load_adapter_with_session_key(config: dict, session_key: str) -> LLMAdapter:
    """Создать адаптер с session-only ключом, без записи в keyring."""
    cls = ADAPTERS.get(config["provider"])
    if cls is None:
        raise ValueError(f"Unknown provider: {config['provider']}")
    return cls(
        api_key=session_key,
        model=config["model"],
        base_url=config.get("base_url"),
        max_tokens=config.get("max_tokens", 4096),
        temperature=config.get("temperature", 0),
    )
```

---

## Config: хранение и политика ключей

```python
# config/config.py
from pathlib import Path
import json, keyring

CONFIG_PATH = Path.home() / ".freecad" / "neurocad" / "config.json"

DEFAULTS = {
    "provider":    "anthropic",
    "model":       "claude-sonnet-4-6",
    "base_url":    None,
    "max_tokens":  4096,
    "temperature": 0,
    # api_key намеренно отсутствует
}

def load() -> dict:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())
        data.pop("api_key", None)  # не читаем ключ из файла
        known = {k: v for k, v in data.items() if k in DEFAULTS}  # unknown keys ignored
        return {**DEFAULTS, **known}
    return DEFAULTS.copy()

def save(cfg: dict) -> None:
    cfg = {k: v for k, v in cfg.items() if k != "api_key"}  # ключ не пишем
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

def save_api_key(provider: str, key: str) -> None:
    """Сохранить ключ в системное хранилище (persist между сессиями)."""
    keyring.set_password("neurocad", provider, key)

```

---

## Exporter

```python
# core/exporter.py
from pathlib import Path
import Part

SUPPORTED = {"step", "stl"}

def export(doc, object_names: list[str], path: str | Path) -> None:
    path = Path(path)
    fmt = path.suffix.lstrip(".").lower()
    if fmt not in SUPPORTED:
        raise ValueError(f"Unsupported format: {fmt}")

    shapes = [doc.getObject(n).Shape for n in object_names
              if hasattr(doc.getObject(n), "Shape")]
    if not shapes:
        raise ValueError("No exportable shapes found")

    compound = Part.makeCompound(shapes)
    if fmt == "step":
        compound.exportStep(str(path))
    elif fmt == "stl":
        compound.exportStl(str(path), 0.01)
```

---

## FreeCAD Workbench: точка входа

```python
# workbench.py
import FreeCAD
import FreeCADGui
from PySide6 import QtCore  # явный импорт (PySide6 6.8.3, Qt 6.8.3)

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
# InitGui.py в корне мода содержит: import neurocad.workbench
```

---

## Зависимости

```toml
# pyproject.toml
[project]
name = "neurocad"
requires-python = ">=3.11"

dependencies = [
    "anthropic>=0.25",
    "openai>=1.30",
    "httpx>=0.27",
    "pydantic>=2.7",
    "keyring>=25.0",         # хранение API key
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt", "ruff", "mypy"]

# Платформа: macOS arm64, FreeCAD 1.1.0, Python 3.11.14 (bundled)
# PySide6 и shiboken6 поставляются FreeCAD — не устанавливать через pip
# PYTHONPATH должен включать FreeCAD bundle lib:
#   /Applications/FreeCAD.app/Contents/Resources/lib
```

---

## Покрытие тестами: приоритет

| Тест | Почему важен |
|---|---|
| `test_agent.py::test_retry_history_structure` | история не засоряется user-turn-ами |
| `test_agent.py::test_rollback_on_invalid_geometry` | документ не меняется при ошибке |
| `test_agent.py::test_rollback_on_exec_error` | то же при exception в exec |
| `test_executor.py::test_sandbox_blocks_os` | `os`, `subprocess` недоступны |
| `test_executor.py::test_timeout` | exec не висит вечно |
| `test_adapters.py::test_provider_switch` | смена провайдера без перезапуска |
| `test_config.py::test_key_precedence` | env > keyring; при отсутствии — ValueError |
| `test_adapters.py::test_session_key_not_persisted` | Use once — ключ не пишется в keyring |
| `test_exporter.py::test_step_and_stl` | оба формата экспортируются корректно |
| `benchmark.py` | acceptance dataset 50 задач; запускается вручную перед релизом |
