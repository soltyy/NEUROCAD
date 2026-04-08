# PRD — NeuroCad
**Version:** v0.1 · **Date:** 2026-04-07
 (FreeCAD Extension)

**Status:** Draft v2 · **Owner:** TBD · **Updated:** 2026-04-01

---

## Problem

Инженеры и дизайнеры тратят часы на ручное создание параметрических моделей в FreeCAD. Python API мощный, но требует знания — барьер входа высокий. Итерация медленная: изменить параметр = переписать код.

---

## Goal

Дать пользователю FreeCAD боковую панель, где он описывает геометрию на естественном языке → расширение генерирует, выполняет и валидирует Python-код через FreeCAD API → модель появляется в viewport.

Аналог: GitHub Copilot, но для 3D-геометрии. Продукт: NeuroCad.

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

- Боковая панель (workbench) в FreeCAD с chat-интерфейсом
- Чтение состояния активного документа (объекты, типы, placement)
- Генерация FreeCAD Python API кода через настраиваемый LLM
- Безопасное выполнение кода (sandbox — см. ARCH)
- Feedback loop: ошибка → автоматический retry (до 3 общих попыток, включая первую)
- Rollback при невалидной геометрии — документ не меняется
- Валидация геометрии после каждой операции
- Undo: каждая операция — один FreeCAD transaction
- Экспорт: STEP, STL через `core/exporter.py`
- UI настройки LLM (провайдер, модель, ключ, base_url)
- Streaming response + progress indicator в панели

### Out (MVP)

- PartDesign, Draft, Sketcher workbench
- Мультипользовательский режим
- Работа без активного FreeCAD документа
- Импорт внешних STEP/IGES файлов через панель
- Голосовой ввод
- Мультимодальность (скриншот → геометрия)

### Workbench scope — MVP: только `Part`

Поддерживаемые операции:

| Категория | Операции |
|---|---|
| Примитивы | box, cylinder, sphere, cone |
| Булевы | cut, fuse, common |
| Модификация | fillet, chamfer (только простые тела) |
| Отверстия | hole, cboreHole |
| Трансформации | placement, rotation |

Всё остальное — явный out-of-scope MVP. LLM сообщает об этом пользователю.

---

## Architecture (одна строка на слой)

```
Chat UI (Qt panel)
  → Context Builder     # читает FreeCAD doc state → structured snapshot
  → Prompt Builder      # system prompt + context + history
  → LLM Adapter         # единый интерфейс: Anthropic / OpenAI / Ollama / any
  → Safe Executor       # exec в whitelist namespace → FreeCAD doc
  → Feedback Loop       # ошибка → traceback → retry (отдельный turn)
  → Validator           # геом. проверка → commit или rollback
  → Exporter            # STEP / STL
  → Viewport            # doc.recompute() → live render
```

**CAD base:** FreeCAD 1.1.0+ · Python 3.11 · Qt 6.8.3
**LLM:** любой провайдер, настраивается пользователем (см. ниже)
**Протокол:** OpenAI-compatible + нативные адаптеры

**Контракт `LLMAdapter.complete` (единый, см. ARCH):**

```python
def complete(
    self,
    messages: list[dict],    # [{"role": "user"|"assistant", "content": str}]
    system: str,
    tools: list[dict] | None = None,  # зарезервировано; в MVP не используется
) -> LLMResponse: ...
```

---

## LLM Configuration

Модель Roo Code: пользователь сам задаёт провайдера, модель и ключ.

```jsonc
// ~/.freecad/neurocad/config.json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "base_url": null,
  "max_tokens": 4096,
  "temperature": 0
  // api_key НЕ хранится в файле — только через env или secure store
}
```

**Политика хранения API key (приоритет по убыванию):**

1. `NEUROCAD_API_KEY` — переменная окружения (наивысший приоритет)
2. Системное хранилище секретов (keyring / macOS Keychain / Windows Credential Store)
3. Ввод через Settings UI — два пути:
   - **Save** → ключ сохраняется в keyring (persist)
   - **Use once** → ключ передаётся в адаптер только на текущую сессию, не сохраняется

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

**FreeCAD, не OpenSCAD** — параметрическое дерево, Python API, STEP-экспорт, 1M+ пользователей.

**Агентный цикл, не plain generation** — агент читает состояние документа, генерирует код, выполняет в sandbox, валидирует геометрию. Не угадывает состояние. LLM tool-calling API не используется — вся логика на стороне executor.

**Sandbox обязателен** — whitelist модулей: `FreeCAD`, `Part`, `App`, `Base`, `math`, `json`. `Sketcher`, `Draft`, `PartDesign` — вне MVP.

**Rollback-first** — любая операция либо полностью применяется (геометрия валидна), либо полностью откатывается. Документ не остаётся в частично изменённом состоянии.

**Retry — отдельный диалоговый turn** — traceback не подменяет исходное сообщение пользователя, а добавляется отдельной записью в историю.

**Провайдер-агностик** — никакой жёсткой привязки к вендору.

---

## Success Metrics — MVP

| Метрика | Цель |
|---|---|
| Простая операция (box, cylinder, hole) | Успех с 1-й попытки ≥ 80% |
| Средняя операция (cut, fuse, fillet) | Успех с ≤ 3 попыток ≥ 70% |
| Сложная операция (shell, loft, compound) | Успех с ≤ 3 попыток ≥ 40%; failure — явное сообщение |
| Время от промпта до объекта | < 8 сек (p90, удалённый API) |
| Crash / некорректная геометрия без rollback | 0% |
| Незапланированное изменение документа при ошибке | 0% |

### Benchmark protocol

Acceptance dataset: **50 задач** (20 простых / 20 средних / 10 сложных).

Для каждой задачи фиксируется:

| Поле | Описание |
|---|---|
| `prompt` | Текст пользователя |
| `expected_type` | Тип результата (`Part::Cut`, `Part::Fuse`, …) |
| `max_retries` | Допустимое число попыток |
| `latency_p90_ms` | Целевой порог |
| `geometry_valid` | bool |
| `rollback_triggered` | bool (если triggered — документ не изменён) |

Тест считается пройденным если `geometry_valid=True` за `≤ max_retries` попыток и при любом сбое `rollback_triggered` гарантирован.

---

## Risks

| Риск | Вероятность | Митигация |
|---|---|---|
| LLM генерирует невалидный Python | Высокая | Sandbox + feedback loop + retry |
| Качество локальных моделей (Ollama) ниже | Высокая | Минимальные требования: 8B+ params, 32k context |
| FreeCAD API меняется между версиями | Средняя | Pin FreeCAD 1.1.0, тесты при апдейте |
| Сложные топологии за пределами MVP scope | Высокая | Явные ограничения в system prompt + fallback |
| Latency удалённых API > 8 сек | Низкая | Streaming в панели + progress indicator |
| API key утечка через config файл | Средняя | env / keyring / session-only UI; в config.json не пишется |

---

## Sprint Plan

| Sprint | Deliverable |
|---|---|
| 1 (нед. 1–2) | FreeCAD workbench, Qt-панель, context builder, history (prep) |
| 2 (нед. 3–4) | LLM adapter layer, safe executor, rollback, feedback loop |
| 3 (нед. 5–6) | Settings UI, exporter, streaming, benchmark run, dog-food |

---

## Decisions

| Вопрос | Решение |
|---|---|
| Workbench scope | MVP: только `Part` + список операций выше |
| API key storage | env > keyring; UI — интерфейс к двум путям: Save (→keyring) / Use once (→session); в файл не пишется |

## Open (post-MVP)

| Вопрос | Когда решать |
|---|---|
| Distribution model (open-source / платная) | После MVP, отдельное решение |
