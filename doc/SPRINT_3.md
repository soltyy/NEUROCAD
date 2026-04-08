# SPRINT 3 — NeuroCad
**Version:** v0.1 · **Date:** 2026-04-07
 · Settings UI + Exporter + Streaming

**Нед. 5–6 · Python 3.11 · FreeCAD 1.1.0+**

---

## Цель спринта

Продукт готов к dog-food тесту: пользователь настраивает провайдера через UI, видит streaming-ответ в панели, экспортирует результат в STEP/STL, а benchmark показывает измеримые метрики.

Предусловие: Sprint 2 полностью закрыт (DoD пройден).

---

## Задачи

### T1 · Settings UI: полная реализация
**Estimate:** 6ч

`ui/settings.py` — диалог из Sprint 1 (shell) получает полную логику.

Два пути сохранения ключа согласно ARCH:

```python
# Save → keyring
def _on_save(self):
    config.save(self._collect_config())       # без api_key
    config.save_api_key(provider, key)        # keyring
    self._adapter = registry.load_adapter(config.load())
    self.accept()

# Use once → session key, keyring не трогаем
def _on_use_once(self):
    cfg = self._collect_config()
    self._adapter = registry.load_adapter_with_session_key(cfg, key)
    self.accept()
```

Acceptance (`test_config.py`, `test_adapters.py`):
- Save: ключ в keyring, в `config.json` отсутствует
- Use once: keyring не модифицируется (`test_session_key_not_persisted`)
- Base URL field: disabled для `anthropic` / `openai`, enabled для остальных
- При смене провайдера — адаптер пересоздаётся без перезапуска FreeCAD
- Невалидный ключ → внятное сообщение об ошибке в диалоге, не крэш

---

### T2 · Streaming response
**Estimate:** 5ч

`LLMAdapter.stream()` зафиксирован в ARCH. Единый flow: `panel → agent.run(callbacks) → stream + execute + validate + rollback`.

```python
# core/agent.py — AgentCallbacks для Sprint 3
@dataclass
class AgentCallbacks:
    on_chunk: Callable[[str], None]          # chunk → live update
    on_attempt: Callable[[int, int], None]   # (n, max) → ProgressBar

def run(..., callbacks: AgentCallbacks | None = None) -> AgentResult:
    for attempt in range(MAX_RETRIES):
        if callbacks: callbacks.on_attempt(attempt + 1, MAX_RETRIES)
        code_chunks = []
        for chunk in adapter.stream(messages, system):
            code_chunks.append(chunk)
            if callbacks: callbacks.on_chunk(chunk)
        result = _execute_with_rollback(extract_code(''.join(code_chunks)), doc)
        ...

# ui/panel.py
def _on_message_submitted(self, text: str):
    self.status_dot.set_state("thinking")
    self.progress_bar.set_state("thinking")
    bubble = self._add_message("assistant", "")
    cb = AgentCallbacks(
        on_chunk=lambda c: (bubble.append_text(c), QApplication.processEvents()),
        on_attempt=lambda n, mx: self.progress_bar.set_attempt(n, mx),
    )
    result = agent.run(text, FreeCAD.ActiveDocument, self._adapter, self._history, cb)
    state = "idle" if result.ok else "error"
    self.status_dot.set_state(state)
    self.progress_bar.set_state(state)
```

Acceptance:
- текст появляется в панели по мере генерации, не после завершения
- UI не фризит во время streaming
- прерывание streaming (закрытие панели) не вызывает исключения
- rollback работает в том же flow
- `ProgressBar` синхронизирован с `StatusDot` из одной точки

---

### T3 · Exporter
**Estimate:** 3ч

`core/exporter.py` — STEP и STL из контракта ARCH.

```python
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

Кнопка Export в панели: открывает `QFileDialog`, вызывает `exporter.export()`.

Acceptance (`test_exporter.py`):
- `export(..., "model.step")` создаёт валидный STEP файл
- `export(..., "model.stl")` создаёт валидный STL файл
- пустой список объектов → `ValueError`
- неподдерживаемый формат → `ValueError`

---

### T4 · Progress indicator
**Estimate:** 2ч

`ui/widgets.py` — `ProgressBar` с тремя состояниями.

```python
class ProgressBar(QWidget):
    def set_state(self, state: Literal["idle", "thinking", "error"]) -> None: ...
    def set_attempt(self, attempt: int, max_attempts: int) -> None: ...
    # показывает "Попытка 2/3" при retry
```

Acceptance:
- при первой попытке: spinner без текста попыток
- при retry: "Попытка 2/3", "Попытка 3/3" — через `AgentCallbacks.on_attempt`
- при успехе: возврат в idle за 1 сек
- при ошибке: красный индикатор + текст ошибки
- `StatusDot` и `ProgressBar` управляются из одной точки — `_on_message_submitted` через callbacks

---

### T5 · Benchmark run
**Estimate:** 6ч

Прогон 50 задач из acceptance dataset (PRD: 20 простых / 20 средних / 10 сложных).

```python
# tests/benchmark.py
@dataclass
class BenchmarkCase:
    prompt: str
    expected_type: str      # "Part::Box", "Part::Cut", ...
    max_retries: int
    latency_p90_ms: int

@dataclass
class BenchmarkResult:
    case: BenchmarkCase
    ok: bool
    attempts: int
    latency_ms: int
    geometry_valid: bool
    rollback_triggered: bool
    error: str | None

def run_benchmark(adapter: LLMAdapter, doc, cases: list[BenchmarkCase]) -> list[BenchmarkResult]:
    ...
```

Acceptance:
- benchmark прогоняется без крэша на всех 50 задачах
- результаты пишутся в `benchmark_results.json`
- итоговый отчёт: success rate по каждому bucket, p90 latency, rollback count
- простые задачи ≥ 80% с 1й попытки (целевой порог из PRD)
- средние задачи ≥ 70% за ≤ 3 попытки (целевой порог из PRD)

---

### T6 · Dog-food тест
**Estimate:** 4ч *(ручная сессия)*

Сценарий: реальная рабочая сессия в FreeCAD от открытия до экспорта.

Чеклист:
- [ ] Открыть FreeCAD, активировать NeuroCad workbench
- [ ] Настроить провайдера через Settings UI (Save path)
- [ ] Создать корпус 50×30×10мм с двумя отверстиями — через промпт
- [ ] Добавить фаску 1мм на верхних рёбрах — через промпт
- [ ] Намеренно ввести некорректный промпт — убедиться в rollback
- [ ] Сменить провайдера через Settings UI (Use once) — убедиться в переключении
- [ ] Экспортировать модель в STEP и STL
- [ ] Проверить STEP в стороннем просмотрщике (FreeCAD reopen / KiCad)

Фиксируется:
- число промптов до финальной модели
- число автоматических retry
- субъективная оценка качества ответов по провайдерам

---

## Definition of Done — Sprint 3

- [ ] Settings UI: Save пишет в keyring, Use once не пишет
- [ ] Смена провайдера без перезапуска FreeCAD
- [ ] Streaming: текст появляется по мере генерации, UI не фризит
- [ ] Export STEP и STL создают валидные файлы
- [ ] ProgressBar показывает номер попытки при retry
- [ ] Benchmark: 50 задач без крэша, результаты в `benchmark_results.json`
- [ ] Отчёт: success rate по всем трём bucket, p90 latency, rollback count
- [ ] Простые задачи: ≥ 80% с 1й попытки
- [ ] Средние задачи: ≥ 70% за ≤ 3 попытки
- [ ] Dog-food чеклист пройден полностью
- [ ] `ruff check .` — чистый
- [ ] `mypy .` — чистый
- [ ] `pytest` — все тесты зелёные

---

## Не в этом спринте

- Packaging / FreeCAD Addon Manager — post-MVP
- Мультимодальность — post-MVP
- PartDesign, Draft, Sketcher workbench — post-MVP
- Distribution model — отдельное решение после dog-food
