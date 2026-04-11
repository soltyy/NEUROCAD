# NeuroCad · Sprint Plans v0.7
**Дата:** 2026-04-10 · Основа: ARCH v0.3 + ghbalf/freecad-ai production паттерны + фактическое состояние репозитория

## Оглавление

- [Sprint 1 — Scaffold + Workbench + Panel + Core Infrastructure](#sprint-1--scaffold--workbench--panel--core-infrastructure)
- [Sprint 2 — LLM Adapter + Executor + Agent Loop + LLMWorker](#sprint-2--llm-adapter--executor--agent-loop--llmworker)
- [Актуальное состояние на 2026-04-10](#актуальное-состояние-на-2026-04-10)
- [Sprint 2.1 — Stabilization Gate для завершения Sprint 2](#sprint-21--stabilization-gate-для-завершения-sprint-2)
- [Sprint 3 — Settings + Export + Benchmark + Dog-food](#sprint-3--settings--export--benchmark--dog-food)
- [Sprint 4 — Capability Boundary + Safe-Fail + Benchmark Hardening](#sprint-4--capability-boundary--safe-fail--benchmark-hardening)
- [Sprint 4.1 — Release Recovery + Workbench Availability](#sprint-41--release-recovery--workbench-availability)
- [Sprint 5.1 — UI Refresh + Visual Hardening](#sprint-51--ui-refresh--visual-hardening)
- [Sprint 5.2 — User Bubble Rendering Fix](#sprint-52--user-bubble-rendering-fix)
- [Сводная таблица: что изменилось от v0.1 → v0.7](#сводная-таблица-что-изменилось-от-v01--v07)

---

# Sprint 1 — Scaffold + Workbench + Panel + Core Infrastructure
**Нед. 1–2 · Python 3.11 · FreeCAD 1.0+**

## Цель

Пользователь открывает FreeCAD, активирует NeuroCad workbench (ghbalf паттерн), видит боковую панель-singleton, получает снимок активного документа через debug action. Вся инфраструктура Sprint 2 заложена с первого дня: `compat.py`, `active_document.py`, `code_extractor.py`, `worker.py` (заглушка).

**Предусловие:** —

**Rolling Plan (старт)**
```
1. NC-DEVOPS-INFRA-001  / DevOps    / Scaffold репозитория         / planned
2. NC-DEV-UI-001        / Developer / InitGui + compat + панель    / planned
3. NC-DEV-CORE-001      / Developer / context + history + config + code_extractor / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEVOPS-INFRA-001** | DevOps | 1 | Scaffold репозитория по ARCH v0.3 | pyproject.toml, DEV_SETUP.md, conftest.py, дерево файлов | `pip install -e .[dev]` чистый; ruff/mypy чистые; все файлы из ARCH v0.3 существуют; `core/worker.py` — заглушка `class LLMWorker: pass`; `ui/compat.py` — полная реализация shim | `TASK CODE: NC-DEVOPS-INFRA-001` / Scaffold по ARCH v0.3. Создать файлы: neurocad/__init__.py neurocad/InitGui.py ui/{compat,panel,settings,widgets}.py core/{active_document,code_extractor,worker,agent,context,prompt,executor,validator,exporter,history}.py config/{config,defaults}.py llm/{base,registry}.py tests/{conftest,test_compat,test_code_extractor,test_active_document,test_context,test_history,test_config}.py / ui/compat.py — полная реализация: try PySide6 except ImportError PySide2; экспортирует QtCore, QtGui, QtWidgets, Qt, Signal, Slot, PYSIDE_VERSION / core/worker.py — заглушка: class LLMWorker: pass / core/code_extractor.py — заглушка: def extract_code(raw): return raw.strip() / core/active_document.py — заглушка: def get_active_document(): return None / pyproject.toml: name=neurocad python>=3.11 deps=pydantic>=2.7,keyring>=25.0 dev=pytest>=8,pytest-qt,ruff,mypy / DEV_SETUP.md: macOS arm64; FreeCAD 1.0.2; PYTHONPATH=/Applications/FreeCAD.app/Contents/Resources/lib:$PYTHONPATH; PySide6 из bundle не pip; symlink ~/Library/Application\ Support/FreeCAD/Mod/neurocad→./neurocad / tests/conftest.py: QApplication fixture + mock FreeCAD модуль / test_compat.py: from neurocad.ui.compat import QtCore,Qt,Signal — без ошибок / НЕ делать: бизнес-логику, Docker, CI / Ответ без TASK CODE = невалиден |
| **NC-DEV-UI-001** | Developer | 2 | InitGui.py (ghbalf паттерн) + ui/widgets.py + ui/panel.py с singleton | InitGui.py, compat.py (финал), panel.py, widgets.py, pytest-qt тест | InitGui.py содержит NeuroCadWorkbench + OpenChatCommand + SettingsCommand + Gui.addWorkbench/addCommand; Initialize() только appendToolbar/appendMenu; Activated() вызывает get_panel_dock(); get_panel_dock() создаёт dock лениво через getMainWindow(); compat.py используется во всех UI файлах; QLineEdit (не QTextEdit); MessageBubble.append_text(chunk); StatusDot.set_state(); _set_busy(True/False) | `TASK CODE: NC-DEV-UI-001` / InitGui.py по ARCH v0.3: NeuroCadWorkbench(Gui.Workbench) — Initialize() только appendToolbar+appendMenu без addDockWidget; Activated() → from neurocad.ui.panel import get_panel_dock; dock=get_panel_dock(); if dock: dock.show(); Deactivated() → get_panel_dock(create=False) hide; GetClassName() → "Gui::PythonWorkbench"; OpenChatCommand и SettingsCommand классы с GetResources/Activated/IsActive; Gui.addCommand("NeuroCad_OpenChat", OpenChatCommand()); Gui.addCommand("NeuroCad_Settings", SettingsCommand()); Gui.addWorkbench(NeuroCadWorkbench()) / ui/panel.py: _panel_dock = None; def get_panel_dock(create=True): global _panel_dock; if None and create: mw=FreeCADGui.getMainWindow(); if mw: _panel_dock=CopilotPanel(mw); mw.addDockWidget(Qt.RightDockWidgetArea, _panel_dock); return _panel_dock; CopilotPanel(QDockWidget): _build_ui с QScrollArea+QLineEdit+QPushButton("Send")+QPushButton("Show Snapshot")+StatusDot в заголовке; self._worker=None; _set_busy(busy:bool): input/send_btn setEnabled(not busy), status_dot.set_state("thinking" if busy else "idle"); все Qt импорты через compat / ui/widgets.py: MessageBubble(role,text)→QFrame; append_text(chunk) добавляет текст; StatusDot→QLabel idle/thinking/error; все импорты через compat / НЕ делать: LLMWorker, agent.run(), ProgressBar / Ответ без TASK CODE = невалиден |
| **NC-DEV-CORE-001** | Developer | 2 | core/context.py + core/history.py + config/config.py + core/code_extractor.py + core/active_document.py | context.py, history.py, config.py, code_extractor.py, active_document.py, test_*.py | save() не пишет api_key; _get_config_dir() через FreeCAD.ConfigGet+fallback; extract_code() strips fenced blocks; active_document возвращает GUI-aligned doc; to_prompt_str() ≤2000 символов; тесты без реального FreeCAD | `TASK CODE: NC-DEV-CORE-001` / core/active_document.py по ARCH v0.3: get_active_document()→try FreeCADGui.ActiveDocument→FreeCAD.getDocument(gui_doc.Document.Name); except→FreeCAD.ActiveDocument; except→None / core/code_extractor.py по ARCH v0.3: extract_code(raw:str)→str; re.sub(r'```(?:python)?\s*\n?(.*?)```', r'\1', raw, flags=DOTALL).strip() / core/context.py: @dataclass ObjectInfo(name,type_id,shape_type|None,volume_mm3|None,placement,visible); @dataclass DocSnapshot(filename,active_object|None,objects,unit="mm"); capture(doc)→DocSnapshot без краша при отсутствии Shape; to_prompt_str()≤2000 символов / core/history.py: Role(StrEnum) USER/ASSISTANT/FEEDBACK; History.add/to_llm_messages(FEEDBACK→"user")/items/clear / config/config.py: _get_config_dir()→Path: try import FreeCAD; ua=FreeCAD.ConfigGet("UserAppData"); if ua: return Path(ua)/"neurocad"; except: xdg=Path.home()/".config"/"FreeCAD"; if xdg.parent.exists(): return xdg/"neurocad"; return Path.home()/".freecad"/"neurocad"; load/save/save_api_key по ARCH v0.3 / test_code_extractor.py: fenced python→голый код; unfenced→as-is; пустой raw→""; multi-block→склеенный; backtick без python→тоже stripped / test_active_document.py: mock FreeCADGui.ActiveDocument→mock doc; нет FreeCADGui→fallback; нет FreeCAD→None / test_config.py: _get_config_dir mock FreeCAD.ConfigGet; no api_key saved; load merges defaults / НЕ делать: LLM вызовы, executor / Ответ без TASK CODE = невалиден |
| **NC-DEV-CORE-002** | Developer | 3 | Snapshot: snapshot_requested → panel показывает контекст | panel.py (обновлён), test | Show Snapshot → текст в MessageBubble; get_active_document()==None → сообщение без краша | `TASK CODE: NC-DEV-CORE-002` / В CopilotPanel: def _on_snapshot_requested(self): from neurocad.core.active_document import get_active_document; from neurocad.core import context; doc=get_active_document(); if doc is None: self._add_message("feedback","Нет активного документа"); return; snap=context.capture(doc); self._add_message("assistant",context.to_prompt_str(snap)) / Подключить кнопку Show Snapshot к _on_snapshot_requested / Ответ без TASK CODE = невалиден |
| **NC-DEVOPS-INFRA-002** | DevOps | 4 | Финальный CI-прогон Sprint 1 | stdout, PASS/FAIL | ruff/mypy/pytest чистые | `TASK CODE: NC-DEVOPS-INFRA-002` / pip install -e .[dev]; ruff check .; mypy .; pytest --tb=short -v / PASS если всё чисто / Ответ без TASK CODE = невалиден |
| **NC-PM-REVIEW-001** | PM | 4 | DoD-чеклист: 16 пунктов | Закрытый чеклист | Все 16 approved | (1) InitGui.py: workbench + команды + addWorkbench/addCommand в одном файле (2) Initialize() не вызывает addDockWidget (3) Activated() → get_panel_dock() создаёт dock лениво (4) Deactivated() → dock.hide() без создания (5) get_panel_dock(create=False) → None если не существует (6) Все UI импорты через compat.py (7) QLineEdit→submit через Enter и кнопку Send (8) MessageBubble.append_text() работает (9) StatusDot меняет цвет (10) _set_busy() disable/enable input+send_btn (11) Show Snapshot → текст снимка в чате (12) get_active_document()==None → сообщение без краша (13) extract_code() strips fenced blocks (14) save() не пишет api_key (15) _get_config_dir() использует ConfigGet с fallback (16) pip/ruff/mypy/pytest чистые |

**Правила останова Sprint 1:** addDockWidget в Initialize() → rejected / `from PySide6 import` напрямую в UI → rejected / `FreeCAD.ActiveDocument` вместо get_active_document() → rejected / CONFIG_PATH хардкод → rejected / Ответ без TASK CODE = невалиден.

---

# Sprint 2 — LLM Adapter + Executor + Agent Loop + LLMWorker
**Нед. 3–4 · Python 3.11 · FreeCAD 1.0+**

**Предусловие: Sprint 1 DoD закрыт полностью.**

## Цель

Пользователь вводит промпт → LLMWorker стримит LLM → код передаётся в main thread через `on_exec_needed` → exec в sandbox → геометрия в viewport. UI не фризит. При ошибке — rollback.

Streaming UI (ProgressBar, chunk display) — в Sprint 3. Здесь только `complete()` path без callbacks — agent.run(callbacks=None).

**Rolling Plan (старт)**
```
1. NC-DEV-LLM-001    / Developer / LLM Adapter layer           / planned
2. NC-DEV-CORE-003   / Developer / Executor + Validator + Agent / planned
3. NC-DEV-CORE-004   / Developer / LLMWorker(threading.Thread)  / planned
4. NC-DEV-UI-002     / Developer / Подключение worker к панели  / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-LLM-001** | Developer | 1 | LLM Adapter: base.py + anthropic.py + openai.py + registry.py | base.py, anthropic.py, openai.py, registry.py, test_adapters.py | OpenAIAdapter с base_url без ошибок; load_adapter() без ключа → ValueError; load_adapter_with_session_key() не вызывает keyring; test_session_key_not_persisted зелёный; mock-адаптер возвращает корректный LLMResponse; интеграционные skip без ключа | `TASK CODE: NC-DEV-LLM-001` / llm/base.py: @dataclass LLMResponse(content,input_tokens,output_tokens,stop_reason); class LLMAdapter(Protocol) complete(messages,system,tools=None)→LLMResponse; stream(messages,system)→Iterator[str] / llm/anthropic.py: AnthropicAdapter(api_key,model,max_tokens,temperature) / llm/openai.py: OpenAIAdapter(api_key,model,base_url,max_tokens,temperature) — покрывает openai/ollama/openai-compatible / llm/registry.py: ADAPTERS dict; load_adapter(config): _resolve_api_key(env>keyring; ValueError); load_adapter_with_session_key(config,session_key): не вызывает _resolve_api_key / test_adapters.py: MockAdapter возвращает LLMResponse; test_session_key_not_persisted: keyring.set_password не вызывается; skip интеграционных без ключа / НЕ делать: LLMWorker, Settings UI, streaming UI / Ответ без TASK CODE = невалиден |
| **NC-DEV-CORE-003** | Developer | 1 | executor.py + validator.py + agent.py + prompt.py | executor.py, validator.py, agent.py, prompt.py, test_*.py | _pre_check tokenize-based блокирует import/FreeCADGui/os/__import__; executor timeout=10сек, макс объектов=5; validator двухступенчатая State+Shape; agent _execute_with_rollback транзакция "NeuroCad"; run() ≤3 попытки; history структура корректна; extract_code используется | `TASK CODE: NC-DEV-CORE-003` / core/executor.py по ARCH v0.3: _BLOCKED_NAME_TOKENS=frozenset({"import","from","FreeCADGui","__import__","os","sys","subprocess","open","eval","exec"}); _pre_check(code)→str|None через tokenize.generate_tokens; ExecResult dataclass; _build_namespace(doc); execute(code,doc)→ExecResult: _pre_check→compile→threading.Thread exec timeout=10сек макс новых объектов=5 / core/validator.py по ARCH v0.3: двухступенчатая: (1) obj.State содержит "error"/"invalid"→ValidationResult(ok=False); (2) Shape isNull/isValid/ShapeType / core/agent.py: AgentCallbacks(on_chunk,on_attempt,on_exec_needed); AgentResult dataclass; _execute_with_rollback: doc.openTransaction("NeuroCad")/commit/abort по ARCH v0.3; run(text,doc,adapter,history,callbacks=None): callbacks=None path — exec напрямую; callbacks path — через on_exec_needed; extract_code из code_extractor; пустой код → FEEDBACK; MAX_RETRIES=3 / core/prompt.py: build_system(snap)→str; DEFAULT_SYSTEM_PROMPT из config/defaults.py / test_executor.py: test_pre_check_blocks_freecadgui; test_pre_check_tokenizer_no_false_positive (комментарий "# open file"); test_sandbox_blocks_os; test_timeout; test_max_objects / test_validator.py: test_state_error_flag (State=["Error"]→ok=False); test_null_shape; test_invalid_shape; test_valid_solid / test_agent.py: history structure; rollback on exec error; rollback on invalid geometry; retry semantics / НЕ делать: LLMWorker, Settings UI, ProgressBar / Ответ без TASK CODE = невалиден |
| **NC-DEV-CORE-004** | Developer | 2 | core/worker.py: LLMWorker(threading.Thread) — полная реализация | worker.py, test_worker.py | LLMWorker запускается в daemon thread; on_chunk/on_attempt вызываются через QTimer.singleShot(0,...); on_exec_needed вызывается в main thread через QTimer.singleShot; worker ждёт receive_exec_result через threading.Event; cancel() разблокирует ожидание; is_running() корректен; тест с mock adapter | `TASK CODE: NC-DEV-CORE-004` / core/worker.py по ARCH v0.3: LLMWorker(on_chunk,on_attempt,on_exec_needed,on_done,on_error); start(text,doc,adapter,history): threading.Thread(target=_run,daemon=True,name="NeuroCad-LLMWorker").start(); is_running(); cancel(): _cancelled.set()+_exec_event.set(); receive_exec_result(result:dict): self._exec_result=result; _exec_event.set(); _schedule_main(callback,*args): from neurocad.ui.compat import QtCore; QtCore.QTimer.singleShot(0,lambda:callback(*args)); _run(text,doc,adapter,history): AgentCallbacks(on_chunk=λ c:_schedule_main(self._on_chunk,c), on_attempt=λ n,mx:_schedule_main(self._on_attempt,n,mx), on_exec_needed=self._request_exec); agent.run(text,doc,adapter,history,cb)→result; _schedule_main(on_done,result); _request_exec(code,attempt)→dict: _exec_event.clear(); _schedule_main(on_exec_needed,code,attempt); _exec_event.wait(); return _exec_result / test_worker.py: mock adapter (complete() только, streaming=None); mock on_exec_needed возвращает {"ok":True,"new_objects":["Box"]}; проверить что on_done вызван с AgentResult(ok=True); проверить retry при ExecResult(ok=False) на первой попытке; cancel() не вызывает on_done; is_running() False после завершения / НЕ делать: Settings UI, ProgressBar, streaming / Ответ без TASK CODE = невалиден |
| **NC-DEV-UI-002** | Developer | 3 | Подключить LLMWorker к CopilotPanel | panel.py (обновлён), ручная проверка | _on_submit создаёт LLMWorker и стартует; input disabled во время; _on_exec_needed вызывает _execute_with_rollback в main thread и worker.receive_exec_result; _on_worker_done/error → _set_busy(False); ввод "создай куб 10×10×10мм" → Box в viewport; сломанный промпт → ошибка, документ не тронут | `TASK CODE: NC-DEV-UI-002` / В CopilotPanel подключить LLMWorker по ARCH v0.3: _on_submit: guard get_active_document()==None → сообщение; guard worker.is_running() → return; _set_busy(True); worker=LLMWorker(on_chunk=self._on_chunk, on_attempt=self._on_attempt, on_exec_needed=self._on_exec_needed, on_done=self._on_worker_done, on_error=self._on_worker_error); worker.start(text,doc,adapter,history) / _on_chunk(chunk): bubble.append_text(chunk) / _on_attempt(n,mx): status_dot.set_state("thinking") / _on_exec_needed(code,attempt): from neurocad.core.agent import _execute_with_rollback; from neurocad.core.active_document import get_active_document; result=_execute_with_rollback(code,get_active_document()); self._worker.receive_exec_result({...}) / _on_worker_done(result): _set_busy(False); if not result.ok: _add_message("feedback",...) / _on_worker_error(msg): _add_message+_set_busy(False) / _init_adapter() при __init__ / НЕ делать: Settings UI, ProgressBar, streaming chunks display / Ответ без TASK CODE = невалиден |
| **NC-DEVOPS-INFRA-003** | DevOps | 4 | Финальный CI-прогон Sprint 2 | stdout, PASS/FAIL | ruff/mypy/pytest чистые; интеграционные skip без ключа | `TASK CODE: NC-DEVOPS-INFRA-003` / ruff check .; mypy .; pytest --tb=short -v / PASS если всё чисто / Ответ без TASK CODE = невалиден |
| **NC-PM-REVIEW-002** | PM | 4 | DoD-чеклист: 13 пунктов | Закрытый чеклист | Все 13 approved | (1) AnthropicAdapter/OpenAIAdapter → LLMResponse (2) load_adapter() без ключа → ValueError (3) _pre_check блокирует FreeCADGui/os/import через tokenize (4) _pre_check не срабатывает на комментарий # open file (5) timeout=10сек (6) validator двухступенчатая: State=["Error"]→ok=False (7) _execute_with_rollback транзакция "NeuroCad" commit/abort (8) LLMWorker exec через on_exec_needed в main thread (9) input disabled во время выполнения (10) промпт → объект в viewport (11) сломанный промпт → ошибка, документ не тронут (12) ruff/mypy чистые (13) pytest зелёный |

**Правила останова Sprint 2:** processEvents() в exec path → rejected / FreeCAD transaction вне main thread → rejected / tokenize заменён на regex → rejected / validator только Shape без State → rejected / транзакция не "NeuroCad" → rejected / Settings UI/ProgressBar → Sprint 3, стоп / Ответ без TASK CODE = невалиден.

---

# Актуальное состояние на 2026-04-10

1. **Последний подтверждённый сохранённый baseline проекта — Sprint 4.**
   - Всё, что в этом репозитории можно считать текущим состоянием проекта, должно интерпретироваться как состояние **после Sprint 4**.
   - Sprint 5 и любые более поздние claims не считаются текущим состоянием репозитория.
2. **Sprint 5+ утрачены как project state.**
   - Любые упоминания Sprint 5, Sprint 6, corrective scope, manual smoke на коммитах вне текущего дерева считаются историческими артефактами, а не подтверждённым текущим статусом.
   - Такие материалы можно использовать только как архивный контекст для будущего восстановления, но не как основание писать `completed`.
3. **Source of truth для текущего статуса проекта:**
   - текущий код в репозитории;
   - план и acceptance Sprint 4 в этом документе;
   - архитектурные решения в `.roo/evals/decisions-log.md`, если они не противоречат коду.
4. В коде есть осознанные отклонения от исходного Sprint 2 плана, и они должны считаться **нормой текущего baseline**:
   - dispatch в main thread сделан через `QObject + Signal(..., Qt.QueuedConnection)`, а не через `QTimer.singleShot(0, ...)`;
   - `executor.execute()` выполняет код синхронно в main thread; внутренний `threading.Thread` для `exec()` убран как небезопасный для FreeCAD document mutations;
   - hard timeout перенесён на LLM transport / worker handoff / UI watchdog, а не на сам `exec()` внутри FreeCAD.
5. Практическое следствие для планирования:
   - Sprint 4 можно считать выполненным baseline-этапом;
   - всё после Sprint 4 должно либо перепроверяться заново в текущем дереве, либо планироваться как новая работа, а не как уже выполненное.

---

# Sprint 2.1 — Stabilization Gate для завершения Sprint 2
**Нед. 5 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed

**Предусловие: текущий end-to-end path работает на простых запросах, архитектурный базис Sprint 2 не откатывается.**

## Цель

Закрыть именно те хвосты Sprint 2, которые можно безопасно доделать в рамках текущей архитектуры: улучшить grounded generation, убрать слепые retry, стабилизировать diagnostics и формально закрыть release gate Sprint 2 без добавления нового большого функционала.

## Принципы Sprint 2.1

1. Не менять main-thread семантику выполнения FreeCAD-кода.
2. Не возвращаться к `QTimer.singleShot` как основному dispatcher.
3. Не добавлять streaming UI, exporter, benchmark и dog-food в этот спринт.
4. Не расширять capability scope без теста и подтверждённого существования FreeCAD API.
5. Любая правка должна либо снижать вероятность зависания/галлюцинации, либо ничего не менять в runtime path.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-003A   / Developer / Prompt grounding + supported API contract   / completed
2. NC-DEV-CORE-003B   / Developer / Retry guardrails + error classification      / completed
3. NC-DEV-UI-002A     / Developer / Release-safe diagnostics in panel            / completed
4. NC-DEVOPS-INFRA-003A / DevOps   / Final verification for Sprint 2 semantics   / completed
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-003A** | Developer | 1 | Grounded prompt для закрытия хвоста Sprint 2 | prompt.py, defaults.py, context.py, tests/test_agent.py | `build_system()` использует snapshot документа; prompt явно перечисляет доступные модули и поддержанные операции Sprint 2.1; prompt запрещает `FreeCADGui`, `import`, выдуманные `Part.make*` API вне подтверждённого списка; простой запрос по-прежнему проходит; unsupported high-level запрос не ухудшает документ | `TASK CODE: NC-DEV-CORE-003A` / Не менять executor или worker. Обновить `core/prompt.py`, чтобы `build_system(snap)` включал компактный snapshot активного документа, активный объект и whitelist поддержанных операций текущего релизного подмножества: `Part.makeBox`, `makeCylinder`, `makeSphere`, `makeCone`, placement, простые boolean (`cut/fuse/common`) только если реально уже поддержаны текущим кодом и тестами. Обновить `config/defaults.py`: запретить многоблочный ответ, imports, `FreeCADGui`, unsupported `Part.make*` методы. `core/context.py`: убедиться, что snapshot для prompt компактный и не шумный. Добавить тесты: system prompt содержит snapshot; unsupported API не попадает в поддержанный whitelist. / НЕ делать: streaming, settings UI, exporter |
| **NC-DEV-CORE-003B** | Developer | 1 | Retry guardrails и классификация ошибок без смены архитектуры | agent.py, executor.py, tests/test_agent.py, tests/test_executor.py | Ошибки `Blocked token ...` и `module 'Part' has no attribute ...` классифицируются отдельно; такие ошибки не вызывают бессмысленный полный retry тем же классом решения; feedback в history содержит короткую конкретную причину; `agent.run()` не уходит в деградацию на 3 одинаковые неудачные попытки; простые успешные кейсы не регрессируют | `TASK CODE: NC-DEV-CORE-003B` / Сохранить текущий main-thread exec и `AgentCallbacks`. В `core/executor.py` добавить безопасное распознавание unsupported attribute path (`module 'Part' has no attribute ...`, аналогичные ошибки для whitelist модулей). В `core/agent.py` нормализовать ошибки минимум в категории: `blocked_token`, `unsupported_api`, `validation`, `llm_transport`, `timeout`, `runtime`. Для `blocked_token` и `unsupported_api` делать направленный feedback в history и не повторять слепо тот же паттерн. Для транспортных и timeout ошибок допустим ограниченный retry. Не добавлять новый concurrency path. |
| **NC-DEV-UI-002A** | Developer | 2 | Привести диагностику панели к release-safe виду | panel.py, debug.py, widgets.py, tests/test_panel.py | Пользователь в панели видит короткий статус, а не поток сырых `[debug] ...`; подробная трассировка остаётся в логах; watchdog сохраняется; busy-state корректно снимается при timeout/error; UI не теряет текущую работоспособность на простых кейсах | `TASK CODE: NC-DEV-UI-002A` / Не трогать contract `panel -> worker -> on_exec_needed -> receive_exec_result`. В `ui/panel.py` заменить текущие debug bubbles на компактные пользовательские статусы (`Request sent`, `Retrying`, `Execution failed`, `Unsupported operation`, `Timed out`). Подробный trace оставить только через `core/debug.py` в console/report view. Не внедрять ещё `SettingsDialog`, `ProgressBar`, streaming bubbles. |
| **NC-DEVOPS-INFRA-003A** | DevOps | 3 | Финальная верификация Sprint 2 после стабилизации | stdout, PASS/FAIL, короткий release note | `ruff/mypy/pytest` чистые; smoke-тест на простые supported запросы зелёный; regression-тесты на blocked token и unsupported API зелёные; документ Sprint 2 можно считать закрытым на уровне текущей архитектуры | `TASK CODE: NC-DEVOPS-INFRA-003A` / Прогнать `ruff check .`, `mypy .`, `pytest --tb=short -v`. Отдельно подтвердить вручную или smoke-тестом: (1) `Создай куб 10x10x10 мм` успешно создаёт объект; (2) `создай шестерню` даёт controlled failure без порчи документа; (3) timeout path снимает busy-state. / НЕ делать: benchmark, dog-food |
| **NC-PM-REVIEW-002A** | PM | 4 | DoD-чеклист Sprint 2.1 / closure Sprint 2 | Закрытый чеклист | Все 10 approved | (1) `build_system()` использует snapshot документа (2) Prompt содержит явный supported scope (3) `FreeCADGui`/`import`/unsupported `Part.make*` явно не поощряются prompt-ом (4) unsupported API классифицируется отдельно от общего runtime error (5) blocked token path безопасен (6) main-thread exec semantics не изменены (7) dispatcher остаётся signal/queued-connection (8) panel release mode не заспамлена debug bubbles (9) простой supported кейс проходит (10) unsupported кейс даёт safe-fail без порчи документа |

**Факт закрытия Sprint 2.1:**
- `NC-DEV-CORE-003A` — completed
- `NC-DEV-CORE-003B` — completed
- `NC-DEV-UI-002A` — completed
- `NC-DEVOPS-INFRA-003A` — completed
- `NC-PM-REVIEW-002A` — completed
- Автоматизированная верификация:
  - `.venv/bin/ruff check .` → clean
  - `.venv/bin/mypy .` → clean
  - `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --tb=short -v` → `95 passed, 1 skipped, 1 xfailed`

**Правила останова Sprint 2.1:** любое изменение, возвращающее `exec()` в background thread → rejected / возврат к `QTimer.singleShot` как основному dispatcher → rejected / добавление streaming/export/settings вместо стабилизации Sprint 2 → stop / расширение поддержанного API без теста и подтверждения существования метода в FreeCAD → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 3 — Settings + Export + Benchmark + Dog-food
**Нед. 5–7 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (manual benchmark findings accepted as final input for next planning step)

**Предусловие: Sprint 2.1 закрыт; release gate Sprint 2 формально пройден на текущей архитектуре.**

## Цель

Довести продукт до dog-food уровня без архитектурного отката: реализовать полноценный Settings UI, экспорт STEP/STL, benchmark по реальному capability scope и ручную dog-food сессию. Core stabilization из Sprint 2.1 считается базой; дополнительные изменения в prompt/agent допускаются только как точечный hardening по итогам benchmark, а не как основной scope спринта. Streaming остаётся вторичным tail work и не является входным критерием релиза.

**Rolling Plan (старт)**
```
1. NC-DEV-UI-003      / Developer / Settings UI + release-grade status/progress        / planned
2. NC-DEV-CORE-007    / Developer / Exporter + optional streaming tail work            / planned
3. NC-DEV-TEST-001    / Developer / Benchmark + supported-capability dataset           / planned
4. NC-DEV-CORE-008    / Developer / Residual hardening from benchmark findings         / planned
5. NC-PM-DOG-001      / PM        / Dog-food after benchmark gate                      / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-UI-003** | Developer | 1 | Settings UI + release-grade status/progress surface | settings.py, widgets.py, panel.py, test_config.py, test_panel.py, test_adapters.py | Save: ключ в keyring, в config.json отсутствует; если `keyring` недоступен, UI предлагает Use once/session path без крэша; Use once не модифицирует keyring; смена провайдера/модели/base_url пересоздаёт `self._adapter` без перезапуска FreeCAD; ProgressBar показывает attempt/status из единой точки управления; текущие debug messages не дублируются как обычные chat bubbles в release mode | `TASK CODE: NC-DEV-UI-003` / ui/settings.py: полноценный `SettingsDialog(QDialog)` с provider/model/base_url/api_key, кнопками `Save` и `Use once`; `Save` использует `config.save()` + `save_api_key()` если keyring доступен, иначе показывает контролируемое предупреждение. `Use once` вызывает `registry.load_adapter_with_session_key(...)` и не пишет ключ. panel.py: добавить открытие Settings из существующей команды, прогресс/статус привести к одной модели состояния (`idle/thinking/error` + attempt). widgets.py: добавить `ProgressBar(QWidget)` или эквивалентный status widget без processEvents. / НЕ делать: benchmark, exporter |
| **NC-DEV-CORE-007** | Developer | 2 | Exporter + optional streaming tail work | exporter.py, panel.py, tests/test_exporter.py, tests/test_worker.py | Export STEP/STL создаёт валидные файлы из выбранных объектов или всех новых объектов последнего успешного запуска; пустой набор → ValueError; unsupported format → ValueError; `Part.OCCError` ловится и преобразуется в RuntimeError; streaming разрешён только как tail work после зелёного exporter/settings gate и только через существующий dispatcher, без `processEvents()` | `TASK CODE: NC-DEV-CORE-007` / core/exporter.py: `SUPPORTED={"step","stl"}`; фильтр по объектам с валидным `Shape`; compound export; нормализованные ошибки. panel.py: добавить кнопку `Export` и выбор формата через `QFileDialog`. Streaming не является deliverable Sprint 3 и допускается только как optional tail work после завершения settings/export/benchmark, через текущий dispatcher (`Signal + QueuedConnection`) и без изменения main-thread exec semantics. / НЕ делать: dog-food до прохождения benchmark |
| **NC-DEV-TEST-001** | Developer | 3 | Benchmark + supported-capability dataset | tests/benchmark.py, benchmark_results.json, короткий отчёт | Benchmark запускается вне pytest и меряет не только успех, но и безопасный отказ. Dataset делится на 3 bucket: `supported-simple`, `supported-composite`, `unsupported-requests`. Для unsupported bucket успехом считается корректный controlled failure без порчи документа. Целевые метрики: simple ≥90% c 1-й попытки; composite ≥70% ≤3 попыток; unsupported safe-fail ≥95%; p90 latency и rollback count сохраняются в json | `TASK CODE: NC-DEV-TEST-001` / tests/benchmark.py: зафиксировать датасет под реальный capability scope Sprint 3. 20 simple: box/cylinder/sphere/cone/placement. 20 composite: cut/fuse/common/hole через boolean/fillet-chamfer только если поддержка реально доказана тестом. 10 unsupported: gear/involute gear/GUI calls/imports/ambiguous high-level prompts. Результаты сериализуются в `benchmark_results.json`; печатается итоговый отчёт по 3 bucket. Benchmark запускается вручную и не включается в pytest. |
| **NC-DEV-CORE-008** | Developer | 4 | Residual hardening from benchmark findings | prompt.py, agent.py, executor.py, panel.py, tests/test_agent.py, tests/test_executor.py | В scope только точечные исправления, подтверждённые benchmark/dog-food данными; не допускается повторное расширение спринта в отдельный core-эпик; residual fixes не ломают текущий release-safe UX и не меняют thread model | `TASK CODE: NC-DEV-CORE-008` / Разрешены только адресные правки по итогам `NC-DEV-TEST-001`: уточнение whitelist поддержанных операций, более точная классификация ошибок, точечное сужение retry policy, уточнение пользовательских статусов. Запрещено: новый concurrency path, возврат к broad prompt, расширение capability без теста, превращение residual task в новый "Sprint 2.2". |
| **NC-PM-DOG-001** | PM | 5 | Dog-food тест: ручная сессия после benchmark gate | Закрытый чеклист + метрики | Dog-food разрешён только если NC-DEV-TEST-001 достиг целевых метрик. Все 8 пунктов пройдены; отдельно фиксируются prompts, retry count, safe-fail кейсы и оценка провайдера | (1) Открыть FreeCAD, активировать NeuroCad (2) Settings UI: Save и Use once path (3) Создать корпус 50×30×10мм с двумя отверстиями через промпт (4) Сделать boolean/placement-операцию вторым запросом (5) Намеренно unsupported prompt (`создай шестерню`) → controlled failure без порчи документа (6) Сменить провайдера или модель → работает без перезапуска (7) Export STEP и STL (8) Открыть STEP в FreeCAD / KiCad и зафиксировать корректность геометрии |
| **NC-DEVOPS-INFRA-004** | DevOps | 5 | Финальный CI-прогон Sprint 3 | stdout, PASS/FAIL | ruff/mypy/pytest чистые; benchmark не входит в pytest; release mode не содержит зависших debug artefacts в панели | `TASK CODE: NC-DEVOPS-INFRA-004` / `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --tb=short -v`; `.venv/bin/ruff check .`; `.venv/bin/mypy .` / benchmark.py НЕ включать в suite / PASS если всё чисто |
| **NC-PM-REVIEW-003** | PM | 6 | DoD-чеклист Sprint 3 | Закрытый чеклист | Все 14 approved | (1) Settings UI Save → keyring, Use once → не пишет (2) keyring optional path не крашит UI (3) Смена провайдера/модели без перезапуска работает (4) Progress/status surface управляется из одной модели состояния (5) Export STEP/STL валиден (6) `Part.OCCError` перехвачен (7) Benchmark 50 задач создаёт `benchmark_results.json` (8) Отчёт включает 3 bucket + p90 latency + rollback count (9) supported-simple ≥90% c 1-й попытки (10) unsupported safe-fail ≥95% (11) Residual hardening, если делался, подтверждён benchmark findings, а не догадками (12) exec остаётся в main thread (13) dispatcher остаётся `Signal + QueuedConnection` (14) ruff/mypy/pytest clean |

**Правила останова Sprint 3:** `processEvents()` в любом path → rejected / exec вне main thread → rejected / возврат к `QTimer.singleShot` как основному dispatcher при наличии queued-signal path → rejected / benchmark в pytest → остановить / UI release mode показывает сырой `[debug] ...` trace как основной UX → rejected / выдуманные FreeCAD API добавляются в whitelist без теста и подтверждённого существования → rejected / residual hardening превращается в новый большой core scope без benchmark findings → rejected / Addon Manager/PartDesign wizard/мультимодальность → post-MVP, стоп / Ответ без TASK CODE = невалиден.

---

## Факт завершения Sprint 3

**Источник фактов:** ручной прогон во FreeCAD, зафиксированный в `tests/manual/NeuroCad Manual Benchmark Log.md`.

### Подтверждённые выводы

1. `supported-simple`: подтверждено `20/20 OK`. Базовые примитивы и placement работают устойчиво.
2. `supported-composite`: подтверждено `19/20 OK`; один кейс (`composite-20`) остался незаполненным, но общая тенденция однозначна: boolean/composite path уже рабочий и не является главным узким местом продукта.
3. `unsupported-requests`: зафиксирован системный провал capability boundary.
   - Модель пытается генерировать суррогатную или выдуманную геометрию вместо явного отказа.
   - На части кейсов наблюдаются timeout вместо контролируемого safe-fail.
   - На ряде запросов отказ не оформлен как строгая unsupported-policy.
4. Главный риск проекта сместился:
   - уже не `simple/composite generation`,
   - а `safe-fail`, `unsupported request handling`, `timeout classification`, `document cleanliness after failure`.

### Управленческий вывод

Sprint 3 принимается как завершённый этап **с полезным benchmark evidence**, но не как этап, доказавший готовность capability boundary. Следующий спринт должен быть сфокусирован не на новом широком функционале, а на доведении неподдержанных запросов до предсказуемого и безопасного поведения.

---

# Sprint 4 — Capability Boundary + Safe-Fail + Benchmark Hardening
**Нед. 8–9 · Python 3.11 · FreeCAD 1.1**

**Предусловие: Sprint 3 завершён, ручной benchmark accepted as final evidence source for planning.**

## Цель

Сделать поведение NeuroCad предсказуемым на границе возможностей: система должна уверенно отрабатывать поддержанный scope, а неподдержанные запросы — отклонять быстро, явно и без порчи документа. Дополнительно Sprint 4 должен превратить ручной benchmark из разового артефакта в повторяемый release-grade инструмент контроля качества.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-009    / Developer / Capability registry + explicit unsupported policy    / planned
2. NC-DEV-CORE-010    / Developer / Safe-fail execution + rollback cleanliness hardening / planned
3. NC-DEV-UI-004      / Developer / User-facing refusal UX + timeout/error clarity       / planned
4. NC-DEV-TEST-002    / Developer / Benchmark hardening + regression dataset             / planned
5. NC-DEVOPS-INFRA-005 / DevOps   / Final verification for Sprint 4 safety semantics     / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-009** | Developer | 1 | Ввести явную capability boundary и unsupported-policy | prompt.py, defaults.py, agent.py, tests/test_agent.py | Поддержанный scope описан как machine-readable policy; для `gear`, `involute gear`, `GUI calls`, `imports`, `external file import`, `advanced loft/turbine` система даёт явный refusal вместо попытки строить суррогатную геометрию; unsupported path не порождает ложный retry как supported case | `TASK CODE: NC-DEV-CORE-009` / Не менять thread model. Добавить явный registry/политику поддержанных операций и категорий unsupported-запросов. Prompt и agent должны сначала классифицировать запрос относительно capability boundary, а затем либо генерировать код только в supported scope, либо возвращать controlled refusal с короткой причиной. Запретить эвристики вида "построю цилиндр как замену шестерне". |
| **NC-DEV-CORE-010** | Developer | 1 | Усилить safe-fail и чистоту документа после ошибок | executor.py, agent.py, validator.py, tests/test_executor.py, tests/test_agent.py | После blocked token, unsupported API, timeout и runtime error документ остаётся чистым; rollback и отсутствие мусорных объектов подтверждены тестом; timeout path завершает сессию без вечного busy-state; ошибки делятся минимум на `unsupported`, `timeout`, `runtime`, `validation` | `TASK CODE: NC-DEV-CORE-010` / Укрепить post-failure semantics: формализовать критерий "document cleanliness", добавить регрессионные тесты на отсутствие новых объектов после провала, проверить abort transaction и status cleanup. Не добавлять новый concurrency path и не переносить exec из main thread. |
| **NC-DEV-UI-004** | Developer | 2 | Ясный UX для unsupported/timeouts/errors | panel.py, widgets.py, tests/test_panel.py | Панель показывает различимые короткие статусы: `Unsupported request`, `Request timed out`, `Execution failed`; пользователь видит, почему запрос не выполнен; после fail UI полностью восстанавливается; release mode не показывает сырой debug trace | `TASK CODE: NC-DEV-UI-004` / Поверх текущего release-safe UI сделать человекочитаемую границу: unsupported request — отдельное сообщение, transport timeout — отдельное, runtime error — отдельное. Не возвращать raw debug bubbles. Не добавлять streaming-first UX. |
| **NC-DEV-TEST-002** | Developer | 3 | Довести benchmark до повторяемого release-grade контура | tests/benchmark.py, benchmark_results.json, tests/manual/NeuroCad Manual Benchmark Log.md, короткий benchmark report | Ручной benchmark log превращён в baseline dataset; `unsupported-requests` оценивается именно как safe-fail; автоматический benchmark path либо реализован для реального FreeCAD, либо документирован как manual-only gate с валидным шаблоном и правилом подсчёта; результаты сравнимы между прогонами | `TASK CODE: NC-DEV-TEST-002` / Использовать текущий ручной benchmark как baseline. Починить договорённость по bucket names, success semantics и report format. Приоритет Sprint 4 — повторяемость и корректная интерпретация safe-fail, а не искусственное накручивание success-rate. |
| **NC-DEVOPS-INFRA-005** | DevOps | 4 | Финальная верификация Sprint 4 | stdout, PASS/FAIL, safety note | `.venv/bin/ruff check .`, `.venv/bin/mypy .`, `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --tb=short -v` чистые; regression на unsupported/safe-fail зелёный; новый benchmark report приложен и интерпретируется однозначно | `TASK CODE: NC-DEVOPS-INFRA-005` / Прогнать стандартные gate'ы и отдельно подтвердить вручную минимум 3 класса сценариев: supported-simple остаётся зелёным; supported-composite не деградирует; unsupported requests отклоняются без мусорной геометрии и зависаний. |
| **NC-PM-REVIEW-004** | PM | 5 | DoD-чеклист Sprint 4 | Закрытый чеклист | Все 12 approved | (1) Capability boundary описана явно (2) unsupported requests не превращаются в суррогатную геометрию (3) gear/involute gear/GUI/import/external import/turbine class относятся к unsupported path (4) unsupported request даёт явный user-facing refusal (5) timeout path снимает busy-state (6) document cleanliness после fail подтверждена тестом (7) rollback semantics не регрессировали (8) simple benchmark baseline не деградировал (9) composite benchmark baseline не деградировал (10) benchmark report интерпретирует unsupported bucket как safe-fail (11) exec остаётся в main thread (12) ruff/mypy/pytest clean |

**Правила останова Sprint 4:** любое расширение capability scope без benchmark и теста → rejected / попытка "молчаливо подменять" unsupported объект похожей простой геометрией → rejected / processEvents() или новый background exec path → rejected / benchmark success-rate за счёт переопределения unsupported как supported → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 4.1 — Release Recovery + Workbench Availability
**Нед. 10 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed

**Предусловие:** Sprint 4 считается последним подтверждённым baseline. Утраченные Sprint 5/6 не считаются текущим состоянием проекта, но их полезный scope поднимается сюда как recovery-план.

## Цель

Собрать в один короткий recovery-sprint всё, что было целью утраченных Sprint 5/6, но привязать это к текущему baseline после Sprint 4: восстановить manual smoke gate, закрыть узкие corrective defects по refusal/export/UI и добавить отдельный bootstrap/installability gate, чтобы NeuroCad не исчезал из workbench dropdown в FreeCAD.

## Почему Sprint 4.1 нужен

Архивные Sprint 5/6 описывали корректный corrective scope, но скриншот с отсутствующим `NeuroCad` в dropdown показывает ещё один класс риска: даже при исправном core/UI мод может не загрузиться как workbench вообще. Значит recovery scope должен покрывать не только refusal/export/autoscroll/icon, но и сам путь загрузки мода.

**Rolling Plan (старт)**
```
1. NC-DEV-TEST-003A     / Developer / Manual smoke baseline recovery                    / completed
2. NC-DEV-CORE-012A     / Developer / Corrective scope: refusal + export contract       / completed
3. NC-DEV-UI-005A       / Developer / Workbench icon + deterministic panel behavior     / completed
4. NC-DEVOPS-INFRA-006A / DevOps    / Mod bootstrap, symlink and InitGui load sanity    / completed
5. NC-PM-REVIEW-004A    / PM        / Release recovery review after Sprint 4 baseline   / completed
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-TEST-003A** | Developer | 1 | Восстановить manual smoke как release gate поверх Sprint 4 | `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`, короткая reconciliation note | Есть актуальный smoke log для текущего дерева, а не для исторического коммита; отдельно проверены `workbench visibility`, `panel visibility`, `supported-simple`, `unsupported refusal`, `recovery`, `STEP/STL export`; log различает `UI says success` и `effect confirmed` | `TASK CODE: NC-DEV-TEST-003A` / Сначала ничего не чинить. Запустить ручной smoke в реальном FreeCAD по текущему baseline после Sprint 4 и оформить новый log. Не использовать старый Sprint 6 log как доказательство текущего состояния. |
| **NC-DEV-CORE-012A** | Developer | 2 | Поднять из утраченных Sprint 5/6 узкий corrective scope для safe-fail и export contract | `core/agent.py`, `config/defaults.py`, `core/exporter.py`, `tests/test_agent.py`, `tests/test_exporter.py` | File/import/external-resource prompts дают ранний controlled refusal; STEP/STL export считается успешным только если файл реально создан и не пустой; изменения не расширяют capability scope и не меняют main-thread execution semantics | `TASK CODE: NC-DEV-CORE-012A` / Восстановить только подтверждённые corrective changes: ранний refusal для file/import/external-resource intents и верифицируемый export contract. Не превращать задачу в новый capability sprint. |
| **NC-DEV-UI-005A** | Developer | 2 | Поднять из Sprint 6 UI-correctives и добавить явный workbench-availability guard | `InitGui.py`, `ui/panel.py`, `resources/icons/neurocad.svg`, `tests/test_panel.py`, `tests/test_workbench.py` или эквивалент | Иконка загружается без warning; чат скроллится через queued-scroll path; panel singleton не ломается; ошибки в icon/resource path не приводят к silent disappearance workbench; есть regression-test или checklist на успешный import `InitGui.py` | `TASK CODE: NC-DEV-UI-005A` / Восстановить icon path fix и deterministic autoscroll. Дополнительно зафиксировать bootstrap guard: любые top-level правки в `InitGui.py` должны быть безопасны и не должны ронять импорт workbench entry point. |
| **NC-DEVOPS-INFRA-006A** | DevOps | 3 | Проверить bootstrap/installability path мода | `DEV_SETUP.md`, smoke note, optional bootstrap test/checklist | Документирован и проверен единственный корректный способ линковки мода в FreeCAD; `NeuroCad` появляется в dropdown при актуальном mod path; отдельно проверено, что layout мода содержит корректный `InitGui.py` в том месте, где его ждёт FreeCAD | `TASK CODE: NC-DEVOPS-INFRA-006A` / Проверить path `<FreeCAD.ConfigGet("UserAppData")>/Mod/neurocad`, структуру каталога мода и import path entry point. Не ограничиваться unit-тестами: нужен explicit bootstrap checklist для symptom class "workbench missing from dropdown". |
| **NC-PM-REVIEW-004A** | PM | 4 | Ревью recovery-sprint как continuation Sprint 4 | Закрытый чеклист | Все recovery-defects либо закрыты, либо переоткрыты явно; workbench visibility подтверждена отдельно от panel logic; manual smoke и automated gate не смешиваются в один ложный signal | (1) `NeuroCad` виден в dropdown (2) активация workbench показывает panel (3) icon/resource fix не ломает bootstrap (4) file/import refusal не создаёт surrogate geometry (5) export success подтверждается файлом (6) autoscroll deterministic (7) automated gate clean (8) manual smoke для текущего дерева приложен |

**Факт статуса на 2026-04-10:**
- `NC-DEV-TEST-003A` — completed; артефакт: `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- `NC-DEV-CORE-012A` — completed; evidence: corrective changes in `neurocad/core/agent.py`, `neurocad/config/defaults.py`, `neurocad/core/exporter.py`, regression coverage in `tests/test_agent.py` and `tests/test_exporter.py`.
- `NC-DEV-UI-005A` — completed; evidence: workbench/icon/bootstrap behavior covered by current code plus manual reconciliation in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- `NC-DEVOPS-INFRA-006A` — completed; evidence: install/bootstrap checklist in `DEV_SETUP.md` plus manual reconciliation in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- `NC-PM-REVIEW-004A` — completed; все 8 пунктов recovery-checklist подтверждены manual evidence и automated gate.

**Факт закрытия NC-PM-REVIEW-004A:**
- (1) `NeuroCad` виден в dropdown — approved; manual evidence in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- (2) Активация workbench показывает panel — approved; manual evidence in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- (3) icon/resource fix не ломает bootstrap — approved; current `InitGui.py` / `neurocad/InitGui.py` entry points plus manual reconciliation note.
- (4) file/import refusal не создаёт surrogate geometry — approved; refusal logic in `neurocad/core/agent.py` and regression coverage in `tests/test_agent.py`.
- (5) export success подтверждается файлом — approved; contract in `neurocad/core/exporter.py`, regression coverage in `tests/test_exporter.py`, and effect-confirmed manual evidence in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- (6) autoscroll deterministic — approved; current panel behavior plus manual evidence in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.
- (7) automated gate clean — approved; `.venv/bin/ruff check .` clean, `.venv/bin/mypy .` clean, `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest --tb=short -q` → `123 passed, 1 skipped, 1 xfailed`.
- (8) manual smoke для текущего дерева приложен — approved; current manual source of truth in `tests/manual/NeuroCad Manual Smoke + Capability Test Log.md`.

**Факт закрытия Sprint 4.1:**
- `NC-DEV-TEST-003A` — completed
- `NC-DEV-CORE-012A` — completed
- `NC-DEV-UI-005A` — completed
- `NC-DEVOPS-INFRA-006A` — completed
- `NC-PM-REVIEW-004A` — completed

## Что в задачах может приводить к результату на скриншоте

Скриншот показывает не просто hidden panel, а более ранний сбой: `NeuroCad` отсутствует в списке workbench. Это значит, что проблема находится на уровне **bootstrap / entry point / install layout**, а не в обычной логике `CopilotPanel`.

Наиболее вероятные источники такого симптома из scope утраченных Sprint 5/6:

1. **Task icon/path fix в `InitGui.py`**
   - Любая ошибка в top-level коде `InitGui.py` приводит к тому, что FreeCAD не может импортировать workbench entry point и просто не регистрирует `NeuroCad`.
   - Особенно опасны top-level вызовы вроде `FreeCADGui.addIconPath(...)`, `addResourcePath(...)`, обращения к несуществующему API или к пути, который вычисляется с ошибкой.
   - В этом случае symptom на скриншоте полностью ожидаем: workbench не появляется в dropdown вообще.

2. **Неверный mod layout / symlink path**
   - FreeCAD ищет `InitGui.py` в корне каталога мода.
   - Если после recovery-задач изменился способ линковки или пользователь указывает на неправильный каталог, FreeCAD не видит entry point, и `NeuroCad` пропадает из списка workbench.
   - Это особенно важно, потому что проект одновременно содержит repo root и каталог `neurocad/`, а ошибка в инструкции по symlink легко создаёт именно такой симптом.

3. **Слишком агрессивная правка bootstrap ради icon resource registration**
   - Missing icon сам по себе обычно не скрывает workbench; он даёт warning.
   - Но попытка "починить иконку" через небезопасный top-level код уже может скрыть workbench полностью.
   - Значит из Sprint 4.1 нужно поднимать не только acceptance "иконка видна", но и защиту "исправление иконки не ломает загрузку workbench".

4. **Подмена проблемы UI-панели проблемой workbench**
   - Задачи про autoscroll, export contract и refusal UX не должны приводить к такому скриншоту напрямую, потому что они выполняются уже после успешной загрузки мода.
   - Поэтому symptom class на скриншоте почти наверняка связан не с `panel.py`, а с `InitGui.py`, структурой мода или инструкцией установки.

## Диагностический вывод по скриншоту

Если ориентироваться только на symptom, приоритет проверки должен быть таким:

1. корректный ли mod path в `<UserAppData>/Mod/neurocad`;
2. лежит ли `InitGui.py` в том месте, где его реально ожидает FreeCAD;
3. нет ли import-time exception в `InitGui.py`;
4. не сломал ли icon-path fix top-level импорт.

То есть для Sprint 4.1 bootstrap/installability должен быть выделен в отдельную задачу, а не оставлен как побочный эффект UI-fix.

---

# Sprint 5.1 — UI Refresh + Visual Hardening
**Нед. 11 · Python 3.11 · FreeCAD 1.1**
**Статус:** implemented (pending PM review)

**Предусловие:** Sprint 4.1 закрыт как recovery baseline. Sprint 5.1 не расширяет capability scope и не меняет main-thread execution semantics; он поднимает только визуальное качество release UI. Icon path fix уже закрыт отдельным фиксом и не входит в scope этого спринта.

## Цель

Перевести панель NeuroCad на более аккуратный Claude-style layout без архитектурного дрейфа: улучшить иерархию сообщений, собрать input area в единый visual container, убрать визуальное обрезание user prompt в чате, сделать поле ввода адаптивным по высоте, включить auto-scroll к последнему сообщению и устранить self-contradiction, когда LLM генерирует код с blocked tokens вроде `import`.

**Rolling Plan (старт)**
```
1. NC-DEV-UI-005A      / Developer / Claude-style panel layout refresh                    / completed
2. NC-DEV-UI-006A      / Developer / Fold/unfold long assistant and code messages          / completed
3. NC-DEV-CORE-013A    / Developer / Prompt-exec consistency for blocked tokens            / completed
4. NC-PM-REVIEW-005A   / PM        / Review UI refresh against release constraints         / pending PM review
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-UI-005A** | Developer | 1 | Переработать `panel/widgets` под Variant B (Claude-style layout), убрать визуальное обрезание user prompt, сделать поле ввода адаптивным по высоте и включить auto-scroll сообщений | `ui/widgets.py`, `ui/panel.py`, минимальные test fixes при необходимости | `MessageBubble` различает `user` / `assistant` / `feedback` по новой visual semantics; нижняя часть панели заменена на `status label + input box + toolbar row`; `_progress_bar` удалён без регрессии worker/agent path; `_status_dot` сохранён; assistant streaming bubble не ломается; user prompt отображается полностью и переносится на новую строку без визуального truncation; поле ввода автоматически растёт по высоте под текст, но не занимает более половины высоты панели; окно сообщений автоматически прокручивается так, чтобы последнее сообщение любого типа было видно без ручного скролла | `TASK CODE: NC-DEV-UI-005A` / Переработать `neurocad/ui/widgets.py` и `neurocad/ui/panel.py` под Вариант B (Claude-style layout) без изменения runtime-логики worker/agent/adapter. В `MessageBubble`: `user` — bubble справа с фоном `#f4f4f4`, border `#e0e0e0`, radius `12px`, margins `10,8,10,8`; `assistant` — без карточки, слева avatar `N` 24x24 с `#2563eb`, справа обычный `QLabel`; `feedback` — transparent background и `border-left: 3px solid` с цветом по semantic bucket (`Success/Exported` зелёный, `Unsupported/Timed out` жёлтый, `Failed/Error/error` красный, иначе серый), font `11px italic`. В `panel.py`: убрать старые `input_row` и `status_layout`; оставить `status label`, затем единый `input box` с полем ввода сверху, divider, toolbar row снизу; `Snapshot` и `Export` — компактные secondary buttons, send — круглая синяя кнопка `30x30`; `_set_busy()` и `_on_attempt()` очистить от `_progress_bar`; `_on_status()` обновляет только `status label` и feedback bubbles. Дополнительно: user message bubble не должен визуально обрезать введённый prompt; длинные запросы должны отображаться полностью с переносом строк. Поле ввода должно автоматически адаптироваться по высоте под введённый текст, но не вырастать более чем до половины общей высоты панели; при превышении лимита должен включаться внутренний скролл, а не ломаться layout панели. Scroll area с историей сообщений должна автоматически прокручиваться к последнему сообщению любого типа (`user`, `assistant`, `feedback`, status-like bubble`), чтобы актуальное состояние было видно без ручного скролла. Проверочный сценарий: после ошибки `Execution failed` и follow-up feedback последнее сообщение остаётся видимым автоматически. Проверочный пример: `20 цилиндров вокруг куба` отображается целиком. Не трогать `worker`, `agent`, `adapter`, `_on_exec_needed`, `_on_worker_done`, `_on_worker_error`, `_status_dot`, `processEvents()`. Тесты панели менять только минимально, если сломаются из-за удаления `_progress_bar` или layout-контракта. |
| **NC-DEV-UI-006A** | Developer | 2 | Добавить fold/unfold для длинных assistant/code сообщений | `ui/widgets.py`, `ui/panel.py`, `tests/test_panel.py` или эквивалент | Длинные assistant/code сообщения по умолчанию показываются в компактном однострочном preview; пользователь может раскрыть сообщение и снова свернуть его; preview не ломает streaming append path; короткие сообщения остаются как обычные bubbles | `TASK CODE: NC-DEV-UI-006A` / Добавить в UI паттерн fold/unfold для длинных assistant или code-heavy сообщений по аналогии со скриншотами: по умолчанию длинный ответ показывается как краткий preview в одну строку с affordance раскрытия; по действию пользователя сообщение раскрывается полностью и может быть снова свёрнуто. Не ломать текущий streaming path в `_on_chunk()` и `MessageBubble.append_text()`: если bubble уже раскрыт, новые чанки продолжают добавляться корректно; если bubble свёрнут, preview обновляется без потери полного текста. Не менять worker, agent, executor, threading path или message history semantics. |
| **NC-DEV-CORE-013A** | Developer | 3 | Устранить несогласованность между prompt и execution sandbox для blocked tokens | `core/prompt.py`, `config/defaults.py`, `tests/test_agent.py` или эквивалент | Для простых поддержанных запросов система не должна генерировать Python с blocked tokens вроде `import math`; prompt явно запрещает `import`, если runtime path его блокирует; supported-case не выглядит как self-contradiction `LLM generated forbidden code -> executor blocks immediately`; main-thread и worker semantics не меняются | `TASK CODE: NC-DEV-CORE-013A` / Устранить несогласованность между prompt и execution sandbox: если `import` заблокирован, LLM не должен генерировать ответы с `import math` для простых поддержанных задач вроде `20 цилиндров вокруг куба`. Обновить prompt/defaults и добавить regression test на supported-case без forbidden tokens. Не менять worker, executor threading или UI pipeline. |
| **NC-PM-REVIEW-005A** | PM | 4 | Проверить UI refresh и prompt-exec consistency как continuation Sprint 4.1 | Закрытый checklist | Layout стал чище без регрессии runtime semantics; assistant bubble stream append не сломан; feedback states визуально различимы; user prompt не обрезается визуально; поле ввода растёт по высоте автоматически, но не более половины панели; окно сообщений автоматически показывает последнее сообщение; длинные assistant/code сообщения корректно сворачиваются и раскрываются; supported-case больше не деградирует в blocked-token path на `import`; automated gate остаётся clean | (1) Claude-style layout визуально применён (2) `_status_dot` сохранён (3) поле ввода auto-resize по высоте, но capped at 50% panel height (4) окно сообщений auto-scroll до последнего сообщения любого типа (5) `_progress_bar` удалён без регрессии статусов (6) assistant streaming bubble работает (7) feedback colors различимы по semantic bucket (8) user prompt отображается полностью без truncation (9) длинные assistant/code сообщения fold/unfold без потери текста (10) supported prompt не приводит к blocked-token failure из-за `import math` (11) worker/agent path не изменён (12) ruff/mypy/pytest clean |

**Факт статуса на 2026-04-11:**
- `NC-DEV-UI-005A` — completed; UI refresh with adaptive input, auto‑scroll, full user prompt display, Claude‑style layout.
- `NC-DEV-UI-006A` — completed; fold/unfold for long messages, streaming‑compatible.
- `NC-DEV-CORE-013A` — completed; prompt tightened with math‑import guidance, regression test added.
- `NC-PM-REVIEW-005A` — pending PM review.

---

# Sprint 5.2 — UI Correctives + Configurable Limits
**Нед. 12 · Python 3.11 · FreeCAD 1.1**
**Статус:** planned

**Предусловие:** Sprint 5.1 используется как baseline визуального refresh. Sprint 5.2 не меняет capability scope, worker/agent path или threading model; он закрывает точечные UI defects и убирает жёсткий лимит `MAX_OBJECTS = 5` в executor через config-driven contract.

## Цель

Закрыть серию небольших, но чётко определённых UI/core defects: user prompt truncation, status placement, auto-scroll для status-like сообщений, assistant logo identity и configurable object limit вместо жёсткого `5`. Sprint должен быть пригоден для маршрутизации `ak-orchestrator` как набор независимых corrective tasks.

**Rolling Plan (старт)**
```
1. NC-DEV-UI-007A      / Developer / Fix user bubble truncation and right-aligned layout   / planned
2. NC-DEV-UI-007B      / Developer / Move status from input box to title bar               / planned
3. NC-DEV-UI-007C      / Developer / Fix auto-scroll for feedback/status-like messages     / planned
4. NC-DEV-UI-007D      / Developer / Replace assistant placeholder avatar with logo        / planned
5. NC-DEV-CORE-014A    / Developer / Configurable max created objects limit                / planned
6. NC-PM-REVIEW-006A   / PM        / Review Sprint 5.2 corrective scope                    / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-UI-007A** | Developer | 1 | Исправить визуальное обрезание user prompt и stabilise right-aligned user bubble layout | `ui/widgets.py`, `ui/panel.py`, `tests/test_panel.py` | Введённый prompt `вокруг куба 10 конусов` отображается полностью; длинный user prompt переносится на новую строку; user bubble остаётся справа; user prompt не fold/unfold и не превращается в preview | `TASK CODE: NC-DEV-UI-007A` / Исправить визуальное обрезание user prompt в чате NeuroCad. Проблему решать как UI-bug, не меняя submit/data path, worker, agent, history, executor или threading semantics. В `neurocad/ui/widgets.py` для `MessageBubble(role="user")` сделать отдельный layout-контракт bubble, не полагаться только на `QLabel.setWordWrap(True)`, задать явный horizontal size policy и max-width contract относительно доступной ширины scroll viewport/panel, сохранить `wordWrap=True`, не включать fold/unfold для user prompt и не укорачивать `_text` preview-логикой. В `neurocad/ui/panel.py` в `_add_message()` для `role == "user"` перестать добавлять bubble напрямую через `addWidget(..., alignment=Qt.AlignRight)` и вместо этого использовать row-container: `QWidget` + `QHBoxLayout` + `addStretch()` + `addWidget(user_bubble)`. Добавить deterministic path обновления max width user bubble при resize панели/scroll viewport. В `tests/test_panel.py` добавить регрессии на полный текст, wordWrap, right-aligned row-container и отсутствие truncation до первых слов. Не менять worker, agent, executor, history, `_on_exec_needed`, `_on_worker_done`, `_on_worker_error`, threading semantics или capability scope. |
| **NC-DEV-UI-007B** | Developer | 2 | Убрать нижний status label и перенести status zone в title bar | `ui/panel.py`, `tests/test_panel.py` | Нижний текстовый статус `Ready` удалён из input box; status text отображается в верхней строке рядом с `NeuroCad`; круглый status indicator остаётся на одной линии с заголовком и выровнен соосно правой геометрии scroll area/полосы скролла | `TASK CODE: NC-DEV-UI-007B` / Убрать нижний текстовый статус `Ready` из input box и перенести status zone в верхнюю строку рядом с `NeuroCad`. Круглый status indicator оставить на одной линии с заголовком, но сместить от правого края так, чтобы он был визуально соосен области правого scroll gutter/полосе прокрутки, а не прижат к рамке панели. Обновить `_set_busy()` и related UI state path так, чтобы нижнего status label больше не было, а верхняя status zone отражала `Ready` / `Thinking...` / промежуточные статусы без потери текущего status-dot semantics. Не менять worker, agent, executor, history, `_on_exec_needed`, `_on_worker_done`, `_on_worker_error` или threading semantics. |
| **NC-DEV-UI-007C** | Developer | 3 | Починить auto-scroll для feedback/status-like сообщений | `ui/panel.py`, `tests/test_panel.py` | Auto-scroll всегда доводит viewport до последнего сообщения любого типа, включая `Request sent`, `Execution failed` и `Failed after 1 attempts ...` | `TASK CODE: NC-DEV-UI-007C` / Исправить auto-scroll path так, чтобы после добавления или обновления любого status-like/feedback сообщения viewport гарантированно прокручивался к последнему элементу истории. Отдельно закрыть сценарии `Request sent`, `Execution failed` и `Failed after 1 attempts: ...`, где сейчас последнее сообщение может остаться вне видимой области. Добавить регрессии в `tests/test_panel.py`. Не менять worker, agent, executor, history или threading semantics. |
| **NC-DEV-UI-007D** | Developer | 4 | Заменить placeholder assistant avatar на логотип NeuroCad слева от сообщения | `ui/widgets.py`, `resources/icons/neurocad.svg`, `tests/test_panel.py` | Assistant bubble использует логотип `neurocad/resources/icons/neurocad.svg` вместо буквы `N`; логотип расположен слева от assistant message; assistant bubble не получает layout regression | `TASK CODE: NC-DEV-UI-007D` / Для assistant bubble заменить текущий placeholder avatar `N` на логотип из `neurocad/resources/icons/neurocad.svg`; логотип располагать по левой стороне assistant message как устойчивый visual marker, без смещения текста вправо за пределы текущего layout contract. Добавить регрессию в `tests/test_panel.py` на использование логотипа слева. Не менять user/feedback semantics, worker, agent, executor или threading path. |
| **NC-DEV-CORE-014A** | Developer | 2 | Вынести лимит создаваемых объектов из executor в настройку и поднять default до `1000` | `core/executor.py`, `config/config.py`, `ui/settings.py`, `tests/test_executor.py`, `tests/test_config.py`, `tests/test_settings.py` | Жёсткий `MAX_OBJECTS = 5` удалён из runtime path; лимит читается из настройки; default value равен `1000`; настройка редактируема через settings UI; при отсутствии значения используется `1000`; тесты подтверждают configurable limit и отсутствие старого hardcode `5` | `TASK CODE: NC-DEV-CORE-014A` / Вынести лимит числа новых объектов из `neurocad/core/executor.py` в настройку и установить default `1000`. Не выполнять изменение как ad-hoc constant edit; перевести его на config-driven contract. В `executor.py` убрать жёсткий `MAX_OBJECTS = 5` и заменить на чтение значения из конфигурации с безопасным fallback `1000`. В `config/config.py` добавить/поддержать ключ настройки для лимита объектов; в `ui/settings.py` добавить поле редактирования этого значения в SettingsDialog. Обновить tests: `tests/test_executor.py` должен проверять configurable object limit и default `1000`; `tests/test_config.py` и `tests/test_settings.py` должны покрывать загрузку/сохранение нового параметра. Не менять worker, agent retry semantics, threading model или capability scope; меняется только источник значения лимита. |
| **NC-PM-REVIEW-006A** | PM | 6 | Проверить Sprint 5.2 corrective scope после Sprint 5.1 baseline | Закрытый checklist | Все corrective subtasks закрыты без architectural drift; regression tests покрывают сценарии; automated gate по изменённым файлам clean | (1) `NC-DEV-UI-007A` закрыт: user prompt отображается полностью, переносится строками и остаётся справа (2) `NC-DEV-UI-007B` закрыт: нижний `Ready` отсутствует, status zone находится в title bar, indicator выровнен соосно scroll gutter (3) `NC-DEV-UI-007C` закрыт: auto-scroll доводит viewport до последних `Request sent`, `Execution failed` и `Failed after 1 attempts ...` (4) `NC-DEV-UI-007D` закрыт: assistant bubble использует логотип `neurocad.svg` слева (5) `NC-DEV-CORE-014A` закрыт: hardcoded object limit `5` удалён, configurable limit default=`1000` (6) submit/data path не менялся (7) worker/agent/threading path не изменён (8) pytest/ruff/mypy по изменённым файлам clean |

**Факт статуса на 2026-04-11:**
- `NC-DEV-UI-007A` — planned.
- `NC-DEV-UI-007B` — planned.
- `NC-DEV-UI-007C` — planned.
- `NC-DEV-UI-007D` — planned.
- `NC-DEV-CORE-014A` — planned.
- `NC-PM-REVIEW-006A` — planned.

---

# Sprint 5.3 — Naming Consistency
**Нед. 13 · Python 3.11 · FreeCAD 1.1**
**Статус:** planned

**Предусловие:** Sprint 5.2 остаётся corrective baseline. Sprint 5.3 не меняет capability scope, threading model или execution architecture; он закрывает точечную задачу консистентности naming contract.

## Цель

Привести transaction name к единому каноническому виду `NeuroCAD` во всём проекте вместо `NeuroCad`, чтобы исключить дальнейшее расхождение между кодом, тестами и sprint-документацией.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-015A    / Developer / Rename transaction name from NeuroCad to NeuroCAD      / planned
2. NC-PM-REVIEW-007A   / PM        / Review transaction-name consistency                     / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-015A** | Developer | 1 | Заменить transaction name `"NeuroCad"` везде на `"NeuroCAD"` | `core/agent.py`, затронутые тесты, `doc/SPRINT_PLANS.md` при необходимости | `openTransaction()` использует `"NeuroCAD"`; тесты и документация не содержат старого transaction-name contract; изменение ограничено naming consistency и не меняет execution semantics | `TASK CODE: NC-DEV-CORE-015A` / Привести transaction name к единому виду `NeuroCAD` во всём проекте. Заменить все места, где transaction name используется как `"NeuroCad"`, на `"NeuroCAD"`. Обновить соответствующие тесты и sprint-документацию, если они закрепляют старое значение. Не менять worker, agent flow, rollback semantics, threading model, validator logic или capability scope; это только naming consistency fix. |
| **NC-PM-REVIEW-007A** | PM | 2 | Проверить консистентность transaction name после Sprint 5.2 baseline | Закрытый checklist | Во всех runtime и test contracts transaction name единообразно `NeuroCAD`; старое значение `NeuroCad` не остаётся как активный contract в коде/тестах/плане; automated gate по изменённым файлам clean | (1) `openTransaction()` использует `NeuroCAD` (2) tests закрепляют `NeuroCAD`, а не `NeuroCad` (3) sprint docs не описывают старый transaction contract как текущий (4) execution semantics не изменены (5) pytest/ruff/mypy по изменённым файлам clean |

**Факт статуса на 2026-04-11:**
- `NC-DEV-CORE-015A` — planned.
- `NC-PM-REVIEW-007A` — planned.

---

## Сводная таблица: что изменилось от v0.1 → v0.7

| Компонент | v0.1 (оригинал) | v0.7 (финал) |
|---|---|---|
| Workbench entry | `workbench.py` отдельный файл | Всё в `InitGui.py` (ghbalf паттерн) |
| Dock creation | `addDockWidget` в `Initialize()` | `get_panel_dock()` singleton в `panel.py` |
| PySide import | `from PySide6 import ...` хардкод | `from .compat import ...` shim |
| Threading | `processEvents()` в streaming / `QThread` | `LLMWorker(threading.Thread)` + dispatcher через `QObject`/`Signal`/`QueuedConnection` |
| Active document | `FreeCAD.ActiveDocument` | `get_active_document()` GUI-aligned |
| Config path | `~/.freecad/neurocad/` хардкод | `_get_config_dir()` с 3-уровневым fallback |
| Code extraction | `extract_code()` неявная в agent | `core/code_extractor.py` отдельный модуль с тестами |
| Sandbox check | regex / не определено | tokenize-based `_pre_check()` |
| FreeCADGui block | не заблокирован | явно в `_BLOCKED_NAME_TOKENS` |
| Validator | только `Shape.isValid()` | двухступенчатая: `obj.State` → `Shape` |
| Transaction name | `"CADCopilot"` (расхождение) | `"NeuroCad"` везде |
| Input guard | нет | `_set_busy(True/False)` в panel |
| Exporter | `exportStep(str(path))` без guard | + `Part.OCCError` catch + null shape filter |
| Benchmark evidence | не определено | ручной FreeCAD benchmark принят как baseline; Sprint 4 переводит его в release-grade safety gate |
| Recovery after Sprint 4 | не определено | поднят в `Sprint 4.1` как merged-scope из утраченных Sprint 5/6 + отдельный bootstrap/installability gate |
