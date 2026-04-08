# PRD — NeuroCad
**Version:** v0.3 · **Date:** 2026-04-08

**Status:** Draft · **Revision:** на основе изучения FreeCAD source + ghbalf/freecad-ai

---

## Problem

Инженеры и дизайнеры тратят часы на ручное создание параметрических моделей в FreeCAD. Python API мощный, но требует знания — барьер входа высокий. Итерация медленная: изменить параметр = переписать код вручную.

---

## Goal

Дать пользователю FreeCAD боковую chat-панель, где он описывает геометрию на естественном языке → расширение генерирует, выполняет и валидирует Python-код через FreeCAD API → модель появляется в viewport.

Аналог: GitHub Copilot, но для 3D-геометрии. Продукт: **NeuroCad**.

---

## Prior Art

**ghbalf/freecad-ai** (github.com/ghbalf/freecad-ai, 107★, апрель 2026) — ближайший аналог, работает в production. NeuroCad отличается фокусом на надёжности (sandbox с tokenize-based блокировкой, двухступенчатая валидация геометрии) и открытой архитектурой. Паттерны реализации dock-панели, threading и config path взяты из ghbalf/freecad-ai как production-proven.

---

## Users

| Сегмент | Боль | Ценность |
|---|---|---|
| Hobbyist / maker | Не знает Python API | Делает то, что раньше не мог |
| Инженер-механик | Итерация медленная | В 3–5× быстрее черновой дизайн |
| Протезист / медик | CAD вообще чужой | Доступность без обучения |

---

## Scope — MVP (6 недель)

### In

- Боковая chat-панель (workbench) в FreeCAD, dock-виджет
- Чтение активного документа: объекты, типы, placement, видимость
- Генерация FreeCAD Python-кода через настраиваемый LLM
- Безопасный sandbox exec (whitelist namespace, tokenize-уровень блокировок)
- Feedback loop: ошибка → traceback как отдельный turn → retry (≤ 3 попытки)
- Двухступенчатая валидация геометрии: State-check + Shape-check
- Rollback при любой ошибке — документ не меняется
- Undo: каждая операция — один FreeCAD transaction с именем "NeuroCad"
- Streaming response через LLMWorker (threading.Thread) без блокировки UI
- Progress indicator: ProgressBar + StatusDot из одной точки управления
- UI настройки LLM (провайдер, модель, ключ, base_url) — два пути сохранения ключа
- Экспорт STEP / STL
- PySide2 / PySide6 совместимость через `ui/compat.py`

### Out (MVP)

- PartDesign, Draft, Sketcher workbench
- Мультипользовательский режим
- Работа без активного FreeCAD документа
- Импорт внешних STEP / IGES файлов через панель
- Мультимодальность (скриншот → геометрия)
- FreeCAD Addon Manager интеграция

### Workbench scope — MVP: только `Part`

| Категория | Операции |
|---|---|
| Примитивы | box, cylinder, sphere, cone |
| Булевы | cut, fuse, common |
| Модификация | fillet, chamfer (только простые тела) |
| Отверстия | hole, cboreHole |
| Трансформации | placement, rotation |

Всё остальное — явный out-of-scope MVP. LLM информирует пользователя об ограничении.

---

## Architecture (одна строка на слой)

```
InitGui.py + workbench команды    # FreeCAD entry point, singleton dock
  → get_panel_dock()              # ленивый singleton: dock создаётся при первом вызове
  → CopilotPanel (QDockWidget)    # chat UI, input guard, LLMWorker lifecycle
  → LLMWorker (threading.Thread)  # LLM I/O в отдельном потоке, UI через QTimer.singleShot
  → agent.run()                   # оркестрация: prompt → llm → exec → validate → commit/rollback
  → Context Builder               # FreeCADGui.ActiveDocument → DocSnapshot
  → Prompt Builder                # system prompt + context + history → строка для LLM
  → LLM Adapter                   # единый интерфейс: Anthropic / OpenAI / Ollama / any
  → CodeExtractor                 # strip fenced blocks перед exec
  → Safe Executor                 # tokenize pre_check + exec в whitelist namespace
  → Validator                     # State-check + Shape-check после recompute()
  → Exporter                      # STEP / STL через Part.makeCompound
  → FreeCAD doc.recompute()       # live render в viewport
```

**CAD base:** FreeCAD 1.0+ (тест на 1.0.2) · Python 3.11 · Qt 6 / Qt 5 (compat)
**LLM:** любой провайдер, настраивается пользователем
**Threading:** Python stdlib `threading.Thread` + `QTimer.singleShot(0, cb)` для UI updates

---

## LLM Configuration

```jsonc
// ~/.config/FreeCAD/neurocad/config.json
// (путь через FreeCAD.ConfigGet("UserAppData") + fallback)
{
  "provider":    "anthropic",
  "model":       "claude-sonnet-4-6",
  "base_url":    null,
  "max_tokens":  4096,
  "temperature": 0
  // api_key НЕ хранится в файле — только через env или secure store
}
```

**Политика API key (приоритет по убыванию):**

1. `NEUROCAD_API_KEY` env var
2. Системное хранилище (keyring / macOS Keychain / Windows Credential Manager)
3. Settings UI — **Save** → keyring (persist) / **Use once** → только session, keyring не трогается

Хранение ключа в `config.json` в открытом виде — **запрещено**.

**Провайдеры из коробки:**

| Провайдер | `provider` | `base_url` |
|---|---|---|
| Anthropic | `anthropic` | — |
| OpenAI | `openai` | — |
| Ollama | `ollama` | `http://localhost:11434` |
| LM Studio | `openai-compatible` | `http://localhost:1234/v1` |
| OpenRouter | `openai-compatible` | `https://openrouter.ai/api/v1` |
| Любой совместимый | `openai-compatible` | задаётся |

---

## Key Decisions

**`get_panel_dock()` singleton, не dock в `Initialize()`** — `Initialize()` вызывается при загрузке модуля, когда `getMainWindow()` может быть `None`. Singleton в `panel.py` создаёт dock лениво в `Activated()`. Паттерн взят из ghbalf/freecad-ai.

**`threading.Thread`, не `QThread`** — Python stdlib threading проще и достаточно. UI updates через `QTimer.singleShot(0, cb)` — стандартный cross-thread Qt паттерн. FreeCAD doc operations (transaction, recompute) остаются в main thread. Паттерн взят из ghbalf/freecad-ai.

**`FreeCADGui.ActiveDocument`, не `FreeCAD.ActiveDocument`** — при нескольких открытых документах они могут расходиться. GUI-aligned version корректна.

**`ui/compat.py` shim** — FreeCAD 0.21 использует PySide2, 1.0+ — PySide6. Все UI-файлы импортируют Qt через shim, не напрямую.

**Tokenize-based sandbox pre_check** — надёжнее regex, не даёт ложных срабатываний на комментарии. Явно блокирует `FreeCADGui` (GUI calls из exec = краш).

**Двухступенчатая валидация** — после `doc.recompute()` объект с ошибкой не бросает исключение, а выставляет `State = ["Error"]`. Validator проверяет State первым, Shape вторым.

**Транзакция `"NeuroCad"`** — имя отображается в FreeCAD Undo menu, унифицировано.

**Rollback-first** — любая операция либо полностью применяется, либо полностью откатывается. Документ не остаётся в частично изменённом состоянии.

**Retry — отдельный turn** — traceback добавляется как `Role.FEEDBACK`, не подменяет user-сообщение.

---

## Success Metrics — MVP

| Метрика | Цель |
|---|---|
| Простая операция (box, cylinder, hole) | Успех с 1-й попытки ≥ 80% |
| Средняя операция (cut, fuse, fillet) | Успех с ≤ 3 попыток ≥ 70% |
| Сложная операция (shell, loft, compound) | Успех с ≤ 3 попыток ≥ 40%; failure — явное сообщение |
| Время от промпта до объекта | < 8 сек p90 (удалённый API) |
| Crash / невалидная геометрия без rollback | 0% |
| Незапланированное изменение документа при ошибке | 0% |
| UI freeze во время LLM запроса | 0% |

### Benchmark protocol

Acceptance dataset: **50 задач** (20 простых / 20 средних / 10 сложных).

| Поле | Описание |
|---|---|
| `prompt` | Текст пользователя |
| `expected_type` | Тип результата (`Part::Cut`, `Part::Fuse`, …) |
| `max_retries` | Допустимое число попыток |
| `latency_p90_ms` | Целевой порог |
| `geometry_valid` | bool |
| `rollback_triggered` | bool (если triggered — документ не изменён) |

---

## Risks

| Риск | Вероятность | Митигация |
|---|---|---|
| LLM генерирует невалидный Python | Высокая | Tokenize pre_check + sandbox + retry |
| LLM возвращает код в fenced blocks | Высокая | CodeExtractor strip перед exec |
| FreeCADGui calls из LLM-кода | Средняя | Tokenize блокировка `FreeCADGui` токена |
| `doc.recompute()` тихий сбой без исключения | Высокая | Двухступенчатая State+Shape валидация |
| Несовместимость PySide2 / PySide6 | Высокая | `ui/compat.py` shim |
| `getMainWindow() == None` при Initialize() | Высокая | `get_panel_dock()` singleton, lazy init |
| FreeCAD.ActiveDocument ≠ FreeCADGui.ActiveDocument | Средняя | `get_active_document()` GUI-aligned |
| Качество локальных моделей (Ollama) | Высокая | Минимум: 8B+ params, 32k context |
| API key утечка через config файл | Средняя | env > keyring; в файл не пишется |
| Latency > 8 сек | Низкая | Streaming + ProgressBar |

---

## Sprint Plan

| Sprint | Deliverable |
|---|---|
| 1 (нед. 1–2) | Scaffold, workbench (ghbalf паттерн), панель, compat.py, active_document.py, code_extractor.py, context, history, config |
| 2 (нед. 3–4) | LLM adapter, executor (tokenize), validator (State+Shape), agent loop, LLMWorker(threading.Thread) |
| 3 (нед. 5–6) | Settings UI, streaming, ProgressBar, exporter, benchmark, dog-food |

---

## Open (post-MVP)

| Вопрос | Когда решать |
|---|---|
| Distribution model (open-source / платная) | После MVP |
| FreeCAD Addon Manager интеграция | После MVP |
| Мультимодальность (viewport screenshot → prompt) | После MVP |
| PartDesign workflow | После MVP |
