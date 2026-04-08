# SPRINT 2 — NeuroCad
**Version:** v0.1 · **Date:** 2026-04-07
 · LLM Adapter + Executor + Agent Loop

**Нед. 3–4 · Python 3.11 · FreeCAD 1.1.0+**

---

## Цель спринта

Пользователь вводит текст в панель → расширение генерирует FreeCAD Python-код через LLM → код выполняется в sandbox → геометрия появляется в viewport. При ошибке — rollback, до 3 общих попыток.

Предусловие: Sprint 1 полностью закрыт (DoD пройден).

---

## Задачи

### T1 · LLM Adapter: base + Anthropic + OpenAI
**Estimate:** 6ч

`llm/base.py` — Protocol и dataclass (уже в ARCH, реализовать):

```python
@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    stop_reason: str  # "end_turn" | "max_tokens"

class LLMAdapter(Protocol):
    def complete(
        self,
        messages: list[dict],
        system: str,
        tools: list[dict] | None = None,  # зарезервировано; в MVP не используется
    ) -> LLMResponse: ...
```

`llm/anthropic.py` — `AnthropicAdapter`.
`llm/openai.py` — `OpenAIAdapter` (покрывает openai / ollama / openai-compatible через `base_url`).

`llm/registry.py` — `load_adapter(config)` и `load_adapter_with_session_key(config, key)`.

Acceptance (`test_adapters.py`):
- `AnthropicAdapter.complete()` возвращает `LLMResponse` на реальный запрос (интеграционный, пропускается без ключа)
- `OpenAIAdapter` с кастомным `base_url` инициализируется без ошибок
- `load_adapter()` без ключа в env/keyring → `ValueError` с внятным текстом
- `load_adapter_with_session_key()` использует переданный ключ, не вызывает keyring
- `test_session_key_not_persisted`: keyring не модифицируется при `load_adapter_with_session_key()`
- mock-адаптер возвращает корректный `LLMResponse` — используется в NC-DEV-CORE-003 и тестах интеграции панели

---

### T2 · Safe Executor
**Estimate:** 5ч

`core/executor.py` — sandbox exec в whitelist namespace.

```python
WHITELIST = {"FreeCAD", "App", "Base", "Part", "math", "json"}

@dataclass
class ExecResult:
    ok: bool
    error: str | None = None
    traceback: str | None = None
    new_objects: list[str] = field(default_factory=list)
    rolled_back: bool = False

def execute(code: str, doc) -> ExecResult: ...
```

Политика исполнения:
- timeout: 10 сек
- макс. новых объектов за ход: 5
- запрещены `import`/`from` statements в коде (модули уже в namespace)
- запрещены fenced code blocks в ответе LLM (` ``` `)
- `os`, `sys`, `subprocess`, `open`, `eval`, `exec` — недоступны

Acceptance (`test_executor.py`):
- корректный FreeCAD-код → `ExecResult(ok=True, new_objects=[...])`
- синтаксическая ошибка → `ExecResult(ok=False, traceback=...)`
- `os.listdir` в коде → `NameError`, `ok=False`
- `import Part` в коде → отклонён до exec, `ok=False`
- `__import__("os")` в коде → `NameError`, `ok=False`
- код с 6 новыми объектами → `ok=False` (превышен лимит)
- код, выполняющийся >10 сек → `ok=False`, timeout

---

### T3 · Validator
**Estimate:** 3ч

`core/validator.py` — проверка геометрии после exec.

```python
@dataclass
class ValidationResult:
    ok: bool
    reason: str | None = None

def check(doc, object_names: list[str]) -> ValidationResult: ...
```

Проверяет каждый новый объект:
- `obj.Shape` существует
- `obj.Shape.isValid()` — True
- `obj.Shape.isNull()` — False
- `obj.Shape.ShapeType in {"Solid", "Shell", "Compound", "Face"}` — не "Edge"/"Wire"

Acceptance (`test_validator.py`):
- валидный Box → `ValidationResult(ok=True)`
- объект без Shape → `ok=False, reason=...`
- невалидная геометрия (mock) → `ok=False`

---

### T4 · Agent: execute_with_rollback
**Estimate:** 5ч

`core/agent.py` — транзакция через FreeCAD undo stack.

```python
def _execute_with_rollback(code: str, doc) -> ExecResult:
    """
    Lifecycle: execute() → recompute() → validate() → commit
                                                      → rollback при любой ошибке
    """
    import traceback
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
        return ExecResult(ok=False, traceback=traceback.format_exc(), rolled_back=True)
```

Acceptance (`test_agent.py`):
- успешный exec → `commitTransaction()` вызван, объект в документе
- ошибка exec → `abortTransaction()`, документ не изменён
- невалидная геометрия → `abortTransaction()`, документ не изменён
- exception внутри exec → `abortTransaction()`, `rolled_back=True`

---

### T5 · Agent: главный цикл + prompt builder
**Estimate:** 6ч

`core/prompt.py` — system prompt и контекст документа. Трансформация истории — в `History.to_llm_messages()`.

```python
DEFAULT_SYSTEM_PROMPT = """..."""  # из config/defaults.py

def build_system(snap: DocSnapshot) -> str: ...
# to_llm_messages — НЕ здесь; единственный владелец — History.to_llm_messages()
```

`core/agent.py` — `run()`:

```python
MAX_RETRIES = 3

def run(
    user_message: str,
    doc,
    adapter: LLMAdapter,
    history: History,        # History из Sprint 1 — add(), to_llm_messages(), clear()
) -> AgentResult:
    # history.add(Role.USER, user_message) — один раз
    # history.add(Role.FEEDBACK, ...) — при retry, не перезаписывает user
    # history.add(Role.ASSISTANT, ...) — только при успехе
```

`ui/panel.py` — подключает `run()` к сигналу `message_submitted`.

Acceptance (`test_agent.py`):
- успешный run за 1 попытку → `AgentResult(ok=True, attempts=1)`
- провал 1й попытки + успех 2й → `AgentResult(ok=True, attempts=2)`
- 3 провала → `AgentResult(ok=False, attempts=3)`
- `history.items() == [USER, ASSISTANT]` после успеха, без FEEDBACK
- `history.items() == [USER, FEEDBACK, ASSISTANT]` при успехе на 2й попытке
- `history.to_llm_messages()` конвертирует FEEDBACK → role=user
- тесты читают структуру через `history.items()` (см. ARCH: `History.items()`)

---

### T6 · Интеграция с панелью
**Estimate:** 3ч

Подключить `agent.run()` к UI: `message_submitted` → `run()` → обновить панель.

```python
# ui/panel.py
def _on_message_submitted(self, text: str):
    self.status_dot.set_state("thinking")
    self._add_message("user", text)
    result = agent.run(text, FreeCAD.ActiveDocument, self._adapter, self._history)
    if result.ok:
        self._add_message("assistant", result.code)
        self.status_dot.set_state("idle")
    else:
        self._add_message("feedback", f"Ошибка: {result.error}")
        self.status_dot.set_state("error")
```

Prerequisite для ручной проверки: провайдер и модель заданы через `NEUROCAD_API_KEY` env var
и `~/.freecad/neurocad/config.json` (provider, model). Settings UI — Sprint 3.

Acceptance (ручная проверка):
- ввод "создай куб 10×10×10мм" → Box появляется в FreeCAD viewport
- ввод заведомо сломанного кода → панель показывает ошибку, документ не изменён
- `StatusDot` корректно переключается idle → thinking → idle/error

---

## Definition of Done — Sprint 2

- [ ] `AnthropicAdapter` и `OpenAIAdapter` возвращают `LLMResponse`
- [ ] `load_adapter()` без ключа → `ValueError`
- [ ] `execute()` блокирует `os`, `import`, fenced blocks, timeout
- [ ] `_execute_with_rollback()`: commit при успехе, abort при любой ошибке
- [ ] Документ не меняется при любом сбое (rollback гарантирован)
- [ ] `run()` делает ≤ 3 общих попытки, history структурирована корректно
- [ ] Ввод промпта в панели → объект в viewport (happy path)
- [ ] Ввод сломанного промпта → ошибка в панели, документ не тронут
- [ ] `ruff check .` — чистый
- [ ] `mypy .` — чистый
- [ ] `pytest` — все тесты зелёные (интеграционные с реальным LLM — skip без ключа)

---

## Не в этом спринте

- Settings UI (провайдер / ключ / base_url) — Sprint 3
- Streaming response — Sprint 3
- Export STEP/STL — Sprint 3
- Undo через UI — Sprint 3
