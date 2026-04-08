# ARCH — NeuroCad
**Version:** v0.3 · **Date:** 2026-04-08
**Python 3.11 · FreeCAD 1.0+ · PySide2/PySide6 · провайдер-агностик LLM**

Revision на основе: изучения FreeCAD source (deepwiki.com/FreeCAD/FreeCAD) + ghbalf/freecad-ai production паттернов.

---

## Что изменилось от v0.1

| Проблема v0.1 | Исправление v0.3 | Источник |
|---|---|---|
| `addDockWidget` в `Initialize()` → `getMainWindow() == None` краш | `get_panel_dock()` singleton, lazy init в `Activated()` | ghbalf/freecad-ai InitGui.py |
| `from PySide6 import ...` хардкод | `ui/compat.py` shim PySide2/PySide6 | ghbalf/freecad-ai compat.py |
| `processEvents()` в streaming → UI freeze, reentrancy | `LLMWorker(threading.Thread)` + `QTimer.singleShot(0, cb)` | ghbalf/freecad-ai + Qt docs |
| `FreeCAD.ActiveDocument` → неверный doc при нескольких открытых | `get_active_document()` GUI-aligned через `FreeCADGui.ActiveDocument` | ghbalf/freecad-ai active_document.py |
| `CONFIG_PATH = ~/.freecad/...` хардкод | `FreeCAD.ConfigGet("UserAppData")` + XDG + legacy fallback | FreeCAD source + ghbalf/freecad-ai |
| `extract_code()` не контрактизирована | `core/code_extractor.py` — отдельный модуль с тестами | best practice |
| regex-based sandbox check | tokenize-based `_pre_check()` + явный блок `FreeCADGui` | FreeCAD source study |
| `validator`: только `Shape.isValid()` | двухступенчатая: `obj.State` → `Shape` | FreeCAD src/App/Document.cpp |
| Транзакция `"CADCopilot"` (расхождение в коде) | Унифицировано `"NeuroCad"` | consistency |
| `workbench.py` + `InitGui.py` = два файла для одного | Workbench класс и команды — прямо в `InitGui.py` | ghbalf/freecad-ai InitGui.py |
| Input не блокируется во время выполнения | `_set_busy(True/False)` — disable input + send button | correctness |

---

## Структура репозитория

```
neurocad/
├── __init__.py
├── InitGui.py               # Workbench класс + команды + Gui.addWorkbench()
│                            # НЕТ отдельного workbench.py (ghbalf паттерн)
│
├── ui/
│   ├── compat.py            # PySide2/PySide6 shim — все UI файлы импортируют отсюда
│   ├── panel.py             # get_panel_dock() singleton + CopilotPanel(QDockWidget)
│   ├── settings.py          # SettingsDialog: провайдер / модель / ключ / base_url
│   └── widgets.py           # MessageBubble, StatusDot, ProgressBar
│
├── core/
│   ├── active_document.py   # get_active_document() — GUI-aligned doc resolution
│   ├── code_extractor.py    # extract_code(raw) → str, strip fenced blocks
│   ├── worker.py            # LLMWorker(threading.Thread) — LLM I/O вне main thread
│   ├── agent.py             # run() + _execute_with_rollback() — только main thread
│   ├── context.py           # capture(doc) → DocSnapshot, to_prompt_str()
│   ├── prompt.py            # build_system(snap) → str
│   ├── executor.py          # _pre_check() tokenize + safe exec whitelist namespace
│   ├── validator.py         # State-check + Shape-check
│   ├── exporter.py          # STEP / STL через Part.makeCompound
│   └── history.py           # Turn(role, content), History
│
├── llm/
│   ├── base.py              # LLMAdapter Protocol, LLMResponse dataclass
│   ├── anthropic.py         # AnthropicAdapter
│   ├── openai.py            # OpenAIAdapter (openai / ollama / openai-compatible)
│   └── registry.py          # load_adapter(), load_adapter_with_session_key()
│
├── config/
│   ├── config.py            # _get_config_dir() + load/save + save_api_key
│   └── defaults.py          # DEFAULT_SYSTEM_PROMPT, SANDBOX_WHITELIST
│
└── tests/
    ├── conftest.py           # QApplication fixture, mock FreeCAD
    ├── test_compat.py        # PySide shim импортируется без ошибок
    ├── test_code_extractor.py
    ├── test_active_document.py
    ├── test_context.py
    ├── test_history.py
    ├── test_config.py        # _get_config_dir, key precedence, no api_key in file
    ├── test_executor.py      # tokenize pre_check, sandbox, timeout, max objects
    ├── test_validator.py     # State-check, Shape-check
    ├── test_agent.py         # retry semantics, history structure, rollback
    ├── test_adapters.py      # provider switch, base_url, session key not persisted
    ├── test_exporter.py
    └── benchmark.py          # 50 задач, запускается вручную, не в pytest
```

---

## Слои и ответственность

```
┌─────────────────────────────────────────────────────────┐
│  InitGui.py                                             │
│  NeuroCadWorkbench + OpenChatCommand + SettingsCommand  │
│  Gui.addWorkbench() + Gui.addCommand()                  │
├─────────────────────────────────────────────────────────┤
│  ui/panel.py                                            │
│  get_panel_dock() singleton — lazy dock creation        │
│  CopilotPanel — chat UI, input guard, worker lifecycle  │
├─────────────────────────────────────────────────────────┤
│  core/worker.py                                         │
│  LLMWorker(threading.Thread)                            │
│  LLM I/O → chunks → QTimer.singleShot → main thread UI │
├─────────────────────────────────────────────────────────┤
│  core/agent.py  (main thread only)                      │
│  run() + _execute_with_rollback()                       │
│  transaction "NeuroCad" / commit / abort                │
├────────────────────┬────────────────────────────────────┤
│  core/context.py   │  core/prompt.py                    │
│  active_document   │  code_extractor                    │
├────────────────────┴────────────────────────────────────┤
│  llm/  (LLMAdapter Protocol)                            │
│  AnthropicAdapter / OpenAIAdapter / registry            │
├─────────────────────────────────────────────────────────┤
│  core/executor.py → core/validator.py → core/exporter   │
│  tokenize pre_check / whitelist exec / State+Shape      │
├─────────────────────────────────────────────────────────┤
│  FreeCAD Python API  (Part only MVP)                    │
│  App.Document · Part · FreeCADGui                       │
└─────────────────────────────────────────────────────────┘
```

---

## InitGui.py — точка входа (ghbalf паттерн)

```python
# InitGui.py — весь workbench здесь, отдельный workbench.py не нужен
import FreeCADGui as Gui

class NeuroCadWorkbench(Gui.Workbench):
    MenuText = "NeuroCad"
    ToolTip  = "LLM-assisted 3D modelling"

    def Initialize(self):
        # ТОЛЬКО toolbar и menu — dock создаётся лениво в Activated()
        # getMainWindow() может быть None в момент Initialize()
        self.appendToolbar("NeuroCad", ["NeuroCad_OpenChat", "NeuroCad_Settings"])
        self.appendMenu("NeuroCad",    ["NeuroCad_OpenChat", "NeuroCad_Settings"])

    def Activated(self):
        from neurocad.ui.panel import get_panel_dock
        dock = get_panel_dock()        # создаёт если не существует
        if dock:
            dock.show()

    def Deactivated(self):
        from neurocad.ui.panel import get_panel_dock
        dock = get_panel_dock(create=False)   # не создавать если нет
        if dock:
            dock.hide()

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class OpenChatCommand:
    def GetResources(self):
        return {"MenuText": "Open AI Chat", "ToolTip": "Open NeuroCad chat panel"}

    def Activated(self, index=0):
        from neurocad.ui.panel import get_panel_dock
        dock = get_panel_dock()
        if dock:
            dock.show()
            dock.raise_()

    def IsActive(self):
        return True


class SettingsCommand:
    def GetResources(self):
        return {"MenuText": "NeuroCad Settings", "ToolTip": "Configure LLM provider and API key"}

    def Activated(self, index=0):
        from neurocad.ui.settings import SettingsDialog
        dlg = SettingsDialog(Gui.getMainWindow())
        dlg.exec()

    def IsActive(self):
        return True


Gui.addCommand("NeuroCad_OpenChat",  OpenChatCommand())
Gui.addCommand("NeuroCad_Settings",  SettingsCommand())
Gui.addWorkbench(NeuroCadWorkbench())
```

---

## ui/compat.py — PySide2/PySide6 shim

```python
# ui/compat.py
# Все UI файлы импортируют Qt отсюда, не напрямую из PySide6/PySide2.
# FreeCAD < 1.0 (0.21.x) использует PySide2, FreeCAD 1.0+ — PySide6.

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal, Slot
    PYSIDE_VERSION = 6
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt, Signal, Slot
    PYSIDE_VERSION = 2

__all__ = ["QtCore", "QtGui", "QtWidgets", "Qt", "Signal", "Slot", "PYSIDE_VERSION"]
```

---

## ui/panel.py — singleton dock

```python
# ui/panel.py
from .compat import QtCore, QtWidgets, Qt, Signal

_panel_dock: "CopilotPanel | None" = None

def get_panel_dock(create: bool = True) -> "CopilotPanel | None":
    """
    Singleton: возвращает существующий dock или создаёт новый.
    Безопасно вызывать многократно — FreeCAD не получит дублирующих dock'ов.
    
    create=False: вернуть None если dock не существует (используется в Deactivated).
    """
    global _panel_dock
    if _panel_dock is None and create:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
        if mw is not None:
            _panel_dock = CopilotPanel(mw)
            mw.addDockWidget(Qt.RightDockWidgetArea, _panel_dock)
    return _panel_dock


class CopilotPanel(QtWidgets.QDockWidget):
    """
    Боковая chat-панель NeuroCad.
    
    Управление busy-состоянием:
      _set_busy(True)  — вызывается при старте LLMWorker
      _set_busy(False) — вызывается по сигналам worker.done / worker.error
    
    Exec всегда в main thread: LLMWorker через done-сигнал передаёт код,
    панель вызывает _run_exec(code) в своём слоте.
    """

    def __init__(self, parent=None):
        super().__init__("NeuroCad", parent)
        self._worker: "LLMWorker | None" = None
        self._history = History()
        self._adapter = None
        self._bubble = None
        self._build_ui()
        self._init_adapter()

    def _build_ui(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        # Chat area
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._msg_container = QtWidgets.QWidget()
        self._msg_layout = QtWidgets.QVBoxLayout(self._msg_container)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)

        # Status dot в заголовке
        self.status_dot = StatusDot()

        # Progress bar
        self.progress_bar = ProgressBar()

        # Input row
        self._input = QtWidgets.QLineEdit()
        self._input.setPlaceholderText("Опишите геометрию...")
        self._input.returnPressed.connect(self._on_submit)
        self._send_btn = QtWidgets.QPushButton("Send")
        self._send_btn.clicked.connect(self._on_submit)
        input_row = QtWidgets.QHBoxLayout()
        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)

        layout.addWidget(self._scroll)
        layout.addWidget(self.progress_bar)
        layout.addLayout(input_row)
        self.setWidget(container)

    def _init_adapter(self):
        try:
            from neurocad.config.config import load as load_config
            from neurocad.llm.registry import load_adapter
            self._adapter = load_adapter(load_config())
        except Exception:
            self._adapter = None

    def _set_busy(self, busy: bool):
        """Единая точка управления busy-состоянием."""
        self._input.setEnabled(not busy)
        self._send_btn.setEnabled(not busy)
        state = "thinking" if busy else "idle"
        self.status_dot.set_state(state)
        self.progress_bar.set_state(state)

    def _on_submit(self):
        text = self._input.text().strip()
        if not text:
            return

        # Guard: активный документ
        from neurocad.core.active_document import get_active_document
        doc = get_active_document()
        if doc is None:
            self._add_message("feedback", "Нет активного документа. Откройте файл FreeCAD.")
            return

        # Guard: worker уже работает
        if self._worker is not None and self._worker.is_running():
            return

        if self._adapter is None:
            self._add_message("feedback", "Провайдер не настроен. Откройте Settings.")
            return

        self._input.clear()
        self._add_message("user", text)
        self._bubble = self._add_message("assistant", "")
        self._set_busy(True)

        from neurocad.core.worker import LLMWorker
        self._worker = LLMWorker(
            on_chunk=self._on_chunk,
            on_attempt=self._on_attempt,
            on_exec_needed=self._on_exec_needed,   # exec в main thread
            on_done=self._on_worker_done,
            on_error=self._on_worker_error,
        )
        self._worker.start(text, doc, self._adapter, self._history)

    def _on_chunk(self, chunk: str):
        """Slot в main thread — вызывается через QTimer.singleShot."""
        if self._bubble:
            self._bubble.append_text(chunk)

    def _on_attempt(self, n: int, mx: int):
        """Slot в main thread."""
        self.progress_bar.set_attempt(n, mx)

    def _on_exec_needed(self, code: str, attempt: int):
        """
        Exec ВСЕГДА в main thread.
        FreeCAD transaction API (openTransaction/commitTransaction/abortTransaction)
        не thread-safe — вызывается только из main thread.
        """
        from neurocad.core.active_document import get_active_document
        from neurocad.core.agent import _execute_with_rollback
        doc = get_active_document()
        if doc is None:
            result_data = {"ok": False, "traceback": "Документ закрыт во время выполнения"}
        else:
            result = _execute_with_rollback(code, doc)
            result_data = {
                "ok": result.ok,
                "traceback": result.traceback,
                "new_objects": result.new_objects,
                "rolled_back": result.rolled_back,
            }
        # Вернуть результат в worker (он ждёт через threading.Event)
        if self._worker:
            self._worker.receive_exec_result(result_data)

    def _on_worker_done(self, agent_result):
        """Slot в main thread — вызывается через QTimer.singleShot."""
        state = "idle" if agent_result.ok else "error"
        self.status_dot.set_state(state)
        self.progress_bar.set_state(state)
        self._set_busy(False)
        if not agent_result.ok:
            self._add_message("feedback", f"Ошибка: {agent_result.error}")
        self._worker = None

    def _on_worker_error(self, msg: str):
        """Slot в main thread — необработанное исключение в worker."""
        self._add_message("feedback", f"Внутренняя ошибка: {msg}")
        self.status_dot.set_state("error")
        self.progress_bar.set_state("error")
        self._set_busy(False)
        self._worker = None

    def _add_message(self, role: str, text: str) -> "MessageBubble":
        from .widgets import MessageBubble
        bubble = MessageBubble(role, text)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, bubble)
        QtCore.QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))
        return bubble
```

---

## core/active_document.py

```python
# core/active_document.py

def get_active_document():
    """
    GUI-aligned active document resolution.
    
    FreeCAD.ActiveDocument и FreeCADGui.ActiveDocument могут расходиться
    при нескольких открытых документах. GUI-версия корректна для операций
    связанных с тем, что видит пользователь в viewport.
    
    Паттерн из ghbalf/freecad-ai active_document.py.
    """
    try:
        import FreeCADGui, FreeCAD
        gui_doc = FreeCADGui.ActiveDocument
        if gui_doc is not None:
            return FreeCAD.getDocument(gui_doc.Document.Name)
    except Exception:
        pass
    try:
        import FreeCAD
        return FreeCAD.ActiveDocument
    except Exception:
        return None
```

---

## core/code_extractor.py

```python
# core/code_extractor.py
import re

def extract_code(raw: str) -> str:
    """
    Удаляет fenced code blocks из LLM-ответа.
    
    LLM часто возвращает код в ```python ... ``` или ``` ... ``` вопреки system prompt.
    extract_code() обрабатывает это до передачи в executor.
    
    Если markdown не обнаружен — возвращает raw.strip() as-is.
    Если после strip пусто — возвращает "" (executor/agent обработает как ошибку).
    
    НЕ делает синтаксический анализ — это зона executor._pre_check().
    """
    # Убираем fenced blocks: ```python\n...\n``` и ```\n...\n```
    stripped = re.sub(r'```(?:python)?\s*\n?(.*?)```', r'\1', raw, flags=re.DOTALL)
    return stripped.strip()
```

---

## core/worker.py — LLMWorker

```python
# core/worker.py
import threading
from typing import Callable, Any

class LLMWorker:
    """
    Запускает LLM streaming в отдельном Python thread.
    
    Паттерн из ghbalf/freecad-ai: threading.Thread (stdlib), не QThread.
    UI updates — через QTimer.singleShot(0, callback) в main thread.
    FreeCAD doc operations (exec, recompute, transaction) — ТОЛЬКО в main thread,
    через on_exec_needed callback + threading.Event для синхронизации.
    
    Lifecycle:
      worker.start(text, doc, adapter, history)
        → streaming loop → on_chunk(chunk) [→ QTimer → UI]
        → on_exec_needed(code, attempt) [→ QTimer → panel._on_exec_needed]
        → panel._on_exec_needed вызывает _execute_with_rollback в main thread
        → panel вызывает worker.receive_exec_result(result)
        → worker продолжает (retry или finish)
      → on_done(AgentResult) [→ QTimer → UI]
    """

    def __init__(
        self,
        on_chunk: Callable[[str], None],
        on_attempt: Callable[[int, int], None],
        on_exec_needed: Callable[[str, int], None],
        on_done: Callable[[Any], None],
        on_error: Callable[[str], None],
    ):
        self._on_chunk = on_chunk
        self._on_attempt = on_attempt
        self._on_exec_needed = on_exec_needed
        self._on_done = on_done
        self._on_error = on_error
        self._thread: threading.Thread | None = None
        self._exec_event = threading.Event()
        self._exec_result: dict | None = None
        self._cancelled = threading.Event()

    def start(self, text: str, doc, adapter, history):
        self._cancelled.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(text, doc, adapter, history),
            daemon=True,
            name="NeuroCad-LLMWorker",
        )
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        self._cancelled.set()
        self._exec_event.set()   # разблокировать ожидание exec если заблокировано

    def receive_exec_result(self, result: dict):
        """Вызывается из main thread после _execute_with_rollback."""
        self._exec_result = result
        self._exec_event.set()

    def _schedule_main(self, callback, *args):
        """Запланировать callback в main thread через Qt event loop."""
        from neurocad.ui.compat import QtCore
        QtCore.QTimer.singleShot(0, lambda: callback(*args))

    def _run(self, text: str, doc, adapter, history):
        """Выполняется в worker thread."""
        try:
            from neurocad.core.agent import run as agent_run
            from neurocad.core.history import History

            # Передаём callbacks в agent.run()
            # agent.run() вызывает on_exec_needed (через _schedule_main) вместо прямого exec
            # и ждёт receive_exec_result через threading.Event
            from neurocad.core.agent import AgentCallbacks
            cb = AgentCallbacks(
                on_chunk=lambda c: self._schedule_main(self._on_chunk, c),
                on_attempt=lambda n, mx: self._schedule_main(self._on_attempt, n, mx),
                on_exec_needed=self._request_exec,
            )
            result = agent_run(text, doc, adapter, history, cb)
            if not self._cancelled.is_set():
                self._schedule_main(self._on_done, result)
        except Exception as e:
            import traceback
            if not self._cancelled.is_set():
                self._schedule_main(self._on_error, traceback.format_exc())

    def _request_exec(self, code: str, attempt: int) -> dict:
        """
        Запрашивает exec в main thread и ждёт результат.
        Блокирует worker thread до получения результата.
        """
        self._exec_event.clear()
        self._exec_result = None
        self._schedule_main(self._on_exec_needed, code, attempt)
        self._exec_event.wait()   # ждём receive_exec_result() из main thread
        return self._exec_result or {"ok": False, "traceback": "No result received"}
```

---

## core/agent.py

```python
# core/agent.py
from dataclasses import dataclass, field
from typing import Callable, Any

@dataclass
class AgentCallbacks:
    on_chunk: Callable[[str], None]
    on_attempt: Callable[[int, int], None]
    on_exec_needed: Callable[[str, int], dict]  # blocking: ждёт ExecResult из main thread

@dataclass
class AgentResult:
    ok: bool
    code: str | None = None
    objects: list[str] = field(default_factory=list)
    attempts: int = 0
    error: str | None = None
    rolled_back: bool = False

MAX_RETRIES = 3

def run(
    user_message: str,
    doc,
    adapter,
    history,
    callbacks: AgentCallbacks | None = None,
) -> AgentResult:
    from neurocad.core import context, prompt
    from neurocad.core.code_extractor import extract_code
    from neurocad.core.history import Role

    snap = context.capture(doc)
    system = prompt.build_system(snap)
    history.add(Role.USER, user_message)

    for attempt in range(MAX_RETRIES):
        if callbacks:
            callbacks.on_attempt(attempt + 1, MAX_RETRIES)

        messages = history.to_llm_messages()

        # Streaming path (Sprint 3) или complete() fallback (Sprint 2)
        if callbacks:
            chunks: list[str] = []
            for chunk in adapter.stream(messages, system):
                chunks.append(chunk)
                callbacks.on_chunk(chunk)
            raw = "".join(chunks)
        else:
            raw = adapter.complete(messages, system).content

        code = extract_code(raw)

        if not code.strip():
            history.add(Role.FEEDBACK,
                f"Попытка {attempt + 1}: пустой код. Сгенерируй валидный Python.")
            continue

        # Exec в main thread: через callback (Sprint 2+) или напрямую (Sprint 1)
        if callbacks:
            result_data = callbacks.on_exec_needed(code, attempt + 1)
            # Конвертируем dict обратно в ExecResult-like
            from neurocad.core.executor import ExecResult
            result = ExecResult(
                ok=result_data.get("ok", False),
                traceback=result_data.get("traceback"),
                new_objects=result_data.get("new_objects", []),
                rolled_back=result_data.get("rolled_back", False),
            )
        else:
            result = _execute_with_rollback(code, doc)

        if result.ok:
            history.add(Role.ASSISTANT, code)
            return AgentResult(ok=True, code=code,
                               objects=result.new_objects, attempts=attempt + 1)

        history.add(Role.FEEDBACK,
            f"Ошибка на попытке {attempt + 1}:\n{result.traceback}\n\nИсправь код.")

    return AgentResult(ok=False, error="Превышено число попыток",
                       attempts=MAX_RETRIES, rolled_back=True)


def _execute_with_rollback(code: str, doc) -> "ExecResult":
    """
    Выполняет код в FreeCAD транзакции.
    
    ВАЖНО: вызывать ТОЛЬКО из main thread.
    FreeCAD transaction API не thread-safe (src/App/Document.cpp).
    
    Transaction name "NeuroCad" — отображается в Edit → Undo menu.
    """
    import traceback as tb_module
    from neurocad.core import executor, validator
    from neurocad.core.executor import ExecResult

    doc.openTransaction("NeuroCad")
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

        doc.commitTransaction()
        return result
    except Exception:
        doc.abortTransaction()
        return ExecResult(ok=False, traceback=tb_module.format_exc(), rolled_back=True)
```

---

## core/executor.py — tokenize-based sandbox

```python
# core/executor.py
import tokenize, io, threading
from dataclasses import dataclass, field

# Токены, запрещённые на уровне pre_check (до compile/exec)
_BLOCKED_NAME_TOKENS = frozenset({
    "import", "from",       # import statements
    "FreeCADGui",           # GUI calls = краш или зависание
    "__import__",           # динамический импорт
    "os", "sys",            # системные модули
    "subprocess",           # shell execution
    "open",                 # файловый I/O
    "eval", "exec",         # вложенный eval/exec
})

@dataclass
class ExecResult:
    ok: bool
    error: str | None = None
    traceback: str | None = None
    new_objects: list[str] = field(default_factory=list)
    rolled_back: bool = False

def _pre_check(code: str) -> str | None:
    """
    Tokenize-based проверка кода до compile().
    Возвращает описание ошибки или None если OK.
    
    Надёжнее regex: не срабатывает на строки/комментарии,
    не даёт ложных позитивов.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except tokenize.TokenError as e:
        return f"Tokenize error: {e}"
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in _BLOCKED_NAME_TOKENS:
            return f"Запрещённый токен: '{tok.string}' (строка {tok.start[0]})"
    return None

def _build_namespace(doc) -> dict:
    import FreeCAD, Part, math, json
    return {
        "FreeCAD": FreeCAD, "App": FreeCAD, "Base": FreeCAD.Base,
        "Part": Part, "doc": doc, "math": math, "json": json,
        "__builtins__": {
            "print": print, "range": range, "len": len,
            "round": round, "abs": abs, "min": min, "max": max,
            "list": list, "dict": dict, "str": str,
            "float": float, "int": int, "bool": bool,
        },
    }

def execute(code: str, doc) -> ExecResult:
    """
    Выполняет код в sandbox namespace.
    Вызывать ТОЛЬКО из main thread (FreeCAD document operations).
    """
    # Pre-check: tokenize-level блокировки
    err = _pre_check(code)
    if err:
        return ExecResult(ok=False, error=err, traceback=err)

    # Compile
    try:
        compiled = compile(code, "<neurocad>", "exec")
    except SyntaxError as e:
        return ExecResult(ok=False, error=str(e), traceback=str(e))

    # Snapshot объектов до exec
    before = set(doc.Objects) if doc else set()

    # Exec с timeout
    result_holder: list[ExecResult] = []
    exc_holder: list[str] = []

    def _exec():
        import traceback as tb_module
        ns = _build_namespace(doc)
        try:
            exec(compiled, ns)
            after = set(doc.Objects) if doc else set()
            new_objs = [o.Name for o in (after - before)]
            if len(new_objs) > 5:
                exc_holder.append(f"Превышен лимит новых объектов: {len(new_objs)} > 5")
            else:
                result_holder.append(ExecResult(ok=True, new_objects=new_objs))
        except Exception:
            exc_holder.append(tb_module.format_exc())

    t = threading.Thread(target=_exec, daemon=True)
    t.start()
    t.join(timeout=10)

    if t.is_alive():
        return ExecResult(ok=False, error="Timeout: выполнение превысило 10 сек",
                          traceback="Timeout")
    if exc_holder:
        return ExecResult(ok=False, error=exc_holder[0], traceback=exc_holder[0])
    if not result_holder:
        return ExecResult(ok=False, error="Нет результата", traceback="No result")
    return result_holder[0]
```

---

## core/validator.py — двухступенчатая проверка

```python
# core/validator.py
from dataclasses import dataclass

@dataclass
class ValidationResult:
    ok: bool
    reason: str | None = None

def check(doc, object_names: list[str]) -> ValidationResult:
    """
    Двухступенчатая валидация геометрии после doc.recompute().
    
    Ступень 1: obj.State (FreeCAD recompute error flag)
      После recompute() объект с ошибкой выставляет State = ["Error"]
      без выброса исключения. Это первый и более надёжный индикатор.
      Источник: FreeCAD src/App/Document.cpp
    
    Ступень 2: Shape validity
      Только если State чистый.
    """
    for name in object_names:
        obj = doc.getObject(name)
        if obj is None:
            return ValidationResult(ok=False, reason=f"Object '{name}' not found after exec")

        # Ступень 1: State check
        state = getattr(obj, "State", [])
        if isinstance(state, (list, tuple)):
            for s in state:
                if isinstance(s, str) and s.lower() in ("error", "invalid"):
                    return ValidationResult(
                        ok=False,
                        reason=f"Object '{name}' recompute error (State={state})"
                    )

        # Ступень 2: Shape check
        if not hasattr(obj, "Shape"):
            return ValidationResult(ok=False, reason=f"Object '{name}' has no Shape property")
        shape = obj.Shape
        if shape.isNull():
            return ValidationResult(ok=False, reason=f"Object '{name}' Shape is null")
        if not shape.isValid():
            return ValidationResult(ok=False, reason=f"Object '{name}' Shape is invalid")
        if shape.ShapeType not in {"Solid", "Shell", "Compound", "Face"}:
            return ValidationResult(
                ok=False,
                reason=f"Object '{name}' ShapeType={shape.ShapeType!r} not in allowed set"
            )

    return ValidationResult(ok=True)
```

---

## config/config.py — config path с fallback

```python
# config/config.py
from pathlib import Path
import json, keyring

def _get_config_dir() -> Path:
    """
    Config path priority:
    1. FreeCAD.ConfigGet("UserAppData") — официальный FreeCAD API
       macOS: ~/Library/Application Support/FreeCAD/
       Linux: ~/.local/share/FreeCAD/  (или XDG_DATA_HOME)
       Windows: %APPDATA%\\FreeCAD\\
    2. ~/.config/FreeCAD/ — XDG fallback (ghbalf/freecad-ai паттерн)
    3. ~/.freecad/ — legacy fallback для тестов без FreeCAD
    """
    try:
        import FreeCAD
        ua = FreeCAD.ConfigGet("UserAppData")
        if ua:
            return Path(ua) / "neurocad"
    except Exception:
        pass
    xdg = Path.home() / ".config" / "FreeCAD"
    if xdg.parent.exists():
        return xdg / "neurocad"
    return Path.home() / ".freecad" / "neurocad"

DEFAULTS = {
    "provider":    "anthropic",
    "model":       "claude-sonnet-4-6",
    "base_url":    None,
    "max_tokens":  4096,
    "temperature": 0,
    # api_key намеренно отсутствует
}

def load() -> dict:
    path = _get_config_dir() / "config.json"
    if path.exists():
        try:
            data = json.loads(path.read_text())
            data.pop("api_key", None)
            known = {k: v for k, v in data.items() if k in DEFAULTS}
            return {**DEFAULTS, **known}
        except Exception:
            pass
    return DEFAULTS.copy()

def save(cfg: dict) -> None:
    cfg = {k: v for k, v in cfg.items() if k != "api_key"}
    path = _get_config_dir() / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2))

def save_api_key(provider: str, key: str) -> None:
    keyring.set_password("neurocad", provider, key)
```

---

## core/context.py + history.py — без изменений от v0.1

```python
# core/context.py
@dataclass
class ObjectInfo:
    name: str; type_id: str; shape_type: str | None
    volume_mm3: float | None; placement: str; visible: bool

@dataclass
class DocSnapshot:
    filename: str; active_object: str | None
    objects: list[ObjectInfo] = field(default_factory=list); unit: str = "mm"

def capture(doc) -> DocSnapshot: ...   # защита от отсутствия Shape
def to_prompt_str(snap: DocSnapshot) -> str: ...   # ≤ 2000 символов
```

```python
# core/history.py
class Role(StrEnum):
    USER = "user"; ASSISTANT = "assistant"; FEEDBACK = "feedback"

@dataclass
class Turn:
    role: Role; content: str

class History:
    def add(self, role: Role, content: str) -> None: ...
    def to_llm_messages(self) -> list[dict]: ...   # FEEDBACK → role=user
    def items(self) -> list[Turn]: ...
    def clear(self) -> None: ...
```

---

## core/exporter.py

```python
# core/exporter.py
from pathlib import Path

SUPPORTED = {"step", "stl"}

def export(doc, object_names: list[str], path: str | Path) -> None:
    """
    Экспорт в STEP или STL.
    
    str(path) обязателен — C++ binding TopoShapePy не принимает Path.
    Part.OCCError перехватывается и перебрасывается с контекстом.
    """
    try:
        import Part
    except ImportError:
        raise RuntimeError("Part module not available")

    path = Path(path)
    fmt = path.suffix.lstrip(".").lower()
    if fmt not in SUPPORTED:
        raise ValueError(f"Unsupported format: {fmt!r}. Supported: {SUPPORTED}")

    shapes = [
        doc.getObject(n).Shape
        for n in object_names
        if doc.getObject(n) is not None
        and hasattr(doc.getObject(n), "Shape")
        and not doc.getObject(n).Shape.isNull()
    ]
    if not shapes:
        raise ValueError("No exportable shapes found")

    try:
        compound = Part.makeCompound(shapes)
        if fmt == "step":
            compound.exportStep(str(path))
        elif fmt == "stl":
            compound.exportStl(str(path), 0.01)
    except Part.OCCError as e:
        raise RuntimeError(f"OCCT export error: {e}") from e
```

---

## llm/ — без изменений от v0.1 по контракту

```python
# llm/base.py
@dataclass
class LLMResponse:
    content: str; input_tokens: int; output_tokens: int; stop_reason: str

class LLMAdapter(Protocol):
    def complete(self, messages: list[dict], system: str,
                 tools: list[dict] | None = None) -> LLMResponse: ...
    def stream(self, messages: list[dict], system: str) -> Iterator[str]: ...

# llm/registry.py
ADAPTERS = {"anthropic": AnthropicAdapter, "openai": OpenAIAdapter,
            "ollama": OpenAIAdapter, "openai-compatible": OpenAIAdapter}

def load_adapter(config: dict) -> LLMAdapter: ...
def load_adapter_with_session_key(config: dict, session_key: str) -> LLMAdapter: ...
def _resolve_api_key(config: dict) -> str: ...  # env > keyring; ValueError если нет
```

---

## pyproject.toml

```toml
[project]
name = "neurocad"
requires-python = ">=3.11"

dependencies = [
    "anthropic>=0.25",
    "openai>=1.30",
    "httpx>=0.27",
    "pydantic>=2.7",
    "keyring>=25.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt", "ruff", "mypy"]

# Платформа: macOS arm64, FreeCAD 1.0.2, Python 3.11.14 (bundled)
# PySide6 и shiboken6 — из bundle FreeCAD, не через pip
# PYTHONPATH: /Applications/FreeCAD.app/Contents/Resources/lib:$PYTHONPATH
# Symlink: <FreeCAD.ConfigGet("UserAppData")>/Mod/neurocad → ./neurocad
# FreeCAD 1.1 on macOS may resolve this to:
# ~/Library/Application Support/FreeCAD/v1-1/Mod/neurocad
```

---

## Покрытие тестами — приоритет

| Тест | Почему важен |
|---|---|
| `test_compat.py::test_pyside_import` | shim импортируется без ошибок на обеих версиях |
| `test_code_extractor.py` | fenced/unfenced/multi-block/empty → корректный код до executor |
| `test_executor.py::test_pre_check_blocks_freecadgui` | GUI calls из exec запрещены |
| `test_executor.py::test_pre_check_tokenizer_vs_regex` | tokenize не срабатывает на комментарии |
| `test_executor.py::test_timeout` | exec не висит вечно |
| `test_validator.py::test_state_error_flag` | `State=["Error"]` → ok=False без исключения |
| `test_agent.py::test_retry_history_structure` | история не засоряется user-turn'ами |
| `test_agent.py::test_rollback_on_invalid_geometry` | документ не меняется при ошибке |
| `test_config.py::test_config_dir_freecad_api` | _get_config_dir использует ConfigGet |
| `test_config.py::test_key_precedence` | env > keyring; ValueError при отсутствии |
| `test_adapters.py::test_session_key_not_persisted` | Use once не пишет keyring |
| `test_exporter.py::test_step_and_stl` | оба формата корректны |
| `benchmark.py` | 50 задач вручную перед релизом |

---

## Правила останова (встроены в промты спринтов)

- Ответ без TASK CODE = невалиден
- `addDockWidget` в `Initialize()` без singleton → rejected (использовать `get_panel_dock()`)
- `from PySide6 import` напрямую в UI-файлах → rejected (использовать compat.py)
- `processEvents()` в streaming path → rejected (нарушает FreeCAD thread safety)
- FreeCAD transaction API вне main thread → rejected
- `FreeCAD.ActiveDocument` вместо `get_active_document()` → rejected
- CONFIG_PATH хардкод без `_get_config_dir()` fallback chain → rejected
- tokenize pre_check заменён на regex → rejected
- Validator только Shape без State → rejected
- Транзакция не "NeuroCad" → rejected
- `FreeCADGui` не заблокирован в executor → rejected
- Addon Manager / PartDesign / мультимодальность → post-MVP, стоп
- Benchmark в pytest suite → остановить
- Противоречие ARCH.md v0.3 → приоритет у файла
