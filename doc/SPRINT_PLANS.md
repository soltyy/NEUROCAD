# NeuroCad · Sprint Plans v1.9
**Дата:** 2026-04-18 · Основа: ARCH v0.3 + ghbalf/freecad-ai production паттерны + фактическое состояние репозитория

> **Scope note (post-Sprint 5.7):** MVP-ограничения сняты. Ранее в Sprint 1–4 мы
> жёстко сужали capability scope до Part WB («только Part, PartDesign /
> Sketcher / Draft / Mesh — post-MVP»), чтобы стабилизировать executor и
> transaction pipeline. Этот gate закрыт: PartDesign, Sketcher, Draft и Mesh
> **включены в основной scope**, whitelist FreeCAD-типов в
> `tests/test_prompt_recipe.py::VALID_OBJECT_TYPES` покрывает все четыре
> workbench'а. Начиная со Sprint 5.8 новые тикеты могут расширять capability
> scope без ссылки на «MVP». Правила останова отдельных старых спринтов
> оставлены как есть (исторический контекст), но к новым задачам применяется
> только общее ограничение: изменения threading/transaction/sandbox по-прежнему
> require explicit sprint scope.

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
- [Sprint 5.3 — Naming Consistency](#sprint-53--naming-consistency)
- [Sprint 5.4 — LLM Integration, Auth UX, Multi-Step Execution, and Audit Logging](#sprint-54--llm-integration-auth-ux-multi-step-execution-and-audit-logging)
- [Sprint 5.5 — Math Namespace + Geometry Context + Placement Grounding](#sprint-55--math-namespace--geometry-context--placement-grounding)
- [Sprint 5.6 — Cancellation Fast-Exit + Handoff Timeout Tuning + Runtime Feedback Expansion](#sprint-56--cancellation-fast-exit--handoff-timeout-tuning--runtime-feedback-expansion)
- [Sprint 5.7 — Complex Task Success: Recipe Fix + Multi-Block Protocol + Static Verifier](#sprint-57--complex-task-success-recipe-fix--multi-block-protocol--static-verifier)
- [Sprint 5.8 — Parametric Recipes + Multi-Block Scoping + Gear Reality Check](#sprint-58--parametric-recipes--multi-block-scoping--gear-reality-check)
- [Sprint 5.9 — Realism: Chamfers, Fillets, Visual Detail](#sprint-59--realism-chamfers-fillets-visual-detail)
- [Sprint 5.10 — Thread Position + Pitch Derivation (no hardcoded constants)](#sprint-510--thread-position--pitch-derivation-no-hardcoded-constants)
- [Sprint 5.11 — Thread Cut Actually Happens: makePipeShell + Volume Assertion](#sprint-511--thread-cut-actually-happens-makepipeshell--volume-assertion)
- [Sprint 5.12 — Truly Parametric Template: Placeholder Syntax + Parse Instructions + ISO 4014/4017](#sprint-512--truly-parametric-template-placeholder-syntax--parse-instructions--iso-40144017)
- [Sprint 5.13 — Naming Contract + defaults.py Bug Fixes (external audit)](#sprint-513--naming-contract--defaultspy-bug-fixes-external-audit)
- [Sprint 5.14 — Wireframe / Math Visualization + Vector 3D Guard](#sprint-514--wireframe--math-visualization--vector-3d-guard)
- [Sprint 5.15 — Cross-Platform Tiered API Key Storage](#sprint-515--cross-platform-tiered-api-key-storage)
- [Sprint 5.16 — Revolution Profile Diagnostics + No-Code Retry + Bevel Helper](#sprint-516--revolution-profile-diagnostics--no-code-retry--bevel-helper)
- [Сводная таблица: что изменилось от v0.1 → v1.9](#сводная-таблица-что-изменилось-от-v01--v19)

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
**Статус:** completed

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
- `NC-DEV-UI-007A` — completed.
- `NC-DEV-UI-007B` — completed.
- `NC-DEV-UI-007C` — completed.
- `NC-DEV-UI-007D` — completed.
- `NC-DEV-CORE-014A` — completed.
- `NC-PM-REVIEW-006A` — completed.

---

# Sprint 5.3 — Naming Consistency
**Нед. 13 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed

**Предусловие:** Sprint 5.2 остаётся corrective baseline. Sprint 5.3 не меняет capability scope, threading model или execution architecture; он закрывает точечную задачу консистентности naming contract.

## Цель

Привести transaction name к единому каноническому виду `NeuroCAD` во всём проекте вместо `NeuroCad`, чтобы исключить дальнейшее расхождение между кодом, тестами и sprint-документацией.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-015A    / Developer / Rename transaction name from NeuroCad to NeuroCAD      / completed
2. NC-DEV-UI-008A      / Developer / Stabilize input box height and bottom toolbar layout    / completed
3. NC-DEV-CORE-016A    / Developer / Fix blocked-import failures on supported CAD prompts    / completed
4. NC-PM-REVIEW-007A   / PM        / Review Sprint 5.3 naming, layout, and prompt consistency / completed
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-015A** | Developer | 1 | Заменить transaction name `"NeuroCad"` везде на `"NeuroCAD"` | `core/agent.py`, затронутые тесты, `doc/SPRINT_PLANS.md` при необходимости | `openTransaction()` использует `"NeuroCAD"`; тесты и документация не содержат старого transaction-name contract; изменение ограничено naming consistency и не меняет execution semantics | `TASK CODE: NC-DEV-CORE-015A` / Привести transaction name к единому виду `NeuroCAD` во всём проекте. Заменить все места, где transaction name используется как `"NeuroCad"`, на `"NeuroCAD"`. Обновить соответствующие тесты и sprint-документацию, если они закрепляют старое значение. Не менять worker, agent flow, rollback semantics, threading model, validator logic или capability scope; это только naming consistency fix. |
| **NC-DEV-UI-008A** | Developer | 2 | Привести input box к устойчивому vertical layout contract: минимальная высота контейнера, adaptive input growth и toolbar pinned to bottom | `ui/panel.py`, затронутые тесты | Красный input-container занимает минимальную высоту, но не меньше суммы внутренних элементов и отступов; синий input-area растёт по высоте под вводимый текст; рост input-area не приводит к тому, что весь красный контейнер становится выше половины высоты панели `NeuroCad`; после достижения лимита дальнейший рост идёт через внутренний скролл input widget; зелёный toolbar block всегда остаётся внизу красного контейнера | `TASK CODE: NC-DEV-UI-008A` / Исправить vertical layout contract нижнего input container в панели NeuroCad. Красный контейнер должен иметь минимальную высоту по содержимому и не занимать лишнее вертикальное пространство, но не может быть ниже суммы внутренних элементов, отступов и divider. Синий input widget должен автоматически увеличивать высоту по мере ввода текста. Рост input widget допускается только до тех пор, пока общая высота красного контейнера не достигнет половины общей высоты панели NeuroCad; после этого input widget должен переходить на внутренний скролл без дальнейшего роста контейнера. Зелёный toolbar row с кнопками `Snapshot`, `Export`, `Send` должен всегда быть прижат к нижней границе красного контейнера и не смещаться вверх при изменении высоты input widget. Добавить регрессионные тесты на минимальную высоту контейнера, adaptive growth input area, cap `<= 50%` высоты панели и bottom-pinned toolbar. Не менять worker, agent, executor, submit/data path, threading semantics или capability scope. |
| **NC-DEV-CORE-016A** | Developer | 2 | Устранить supported-case fail, когда LLM генерирует `import math`, а sandbox его блокирует | `config/defaults.py`, `core/prompt.py`, `core/agent.py`, затронутые тесты | Supported prompt вроде `10 кубов вокруг этого куба` не завершается user-visible fail из-за `Blocked token 'import'`; sandbox policy не ослабляется; forbidden imports по-прежнему блокируются executor; добавлен regression test на supported-case recovery path | `TASK CODE: NC-DEV-CORE-016A` / Исправить self-contradiction между LLM output и sandbox contract для supported CAD prompts. Не ослаблять sandbox policy в `executor`: `import` должен оставаться запрещённым. Усилить generation contract в prompt для circular/radial patterns без `import math`, добавить targeted regeneration path: если первый сгенерированный код падает именно по blocked token `import` или `from`, выполнить один corrective regeneration pass с явной инструкцией сгенерировать эквивалентный код без import statements. Добавить regression tests на supported prompt вроде `10 кубов вокруг этого куба`, чтобы blocked-token import failure не был финальным user-visible результатом на первом supported-case path. Не менять worker/threading/main-thread execution semantics. |
| **NC-PM-REVIEW-007A** | PM | 4 | Проверить консистентность Sprint 5.3 после Sprint 5.2 baseline | Закрытый checklist | Naming contract, input-layout contract и prompt/sandbox consistency закрыты без architectural drift; automated gate по изменённым файлам clean | (1) transaction name использует `NeuroCAD`, а не `NeuroCad` (2) input container не занимает лишнюю высоту и остаётся минимум по содержимому (3) input area растёт по тексту, но весь нижний контейнер не превышает `50%` высоты панели (4) toolbar row всегда pinned to bottom input container (5) supported prompt вроде `10 кубов вокруг этого куба` не деградирует в финальный blocked-import fail (6) sandbox policy на `import` не ослаблена (7) tests закрепляют новый layout contract, recovery contract и naming contract (8) execution semantics не изменены (9) pytest/ruff/mypy по изменённым файлам clean |

**Факт статуса на 2026-04-11:**
- `NC-DEV-CORE-015A` — completed.
- `NC-DEV-UI-008A` — completed.
- `NC-DEV-CORE-016A` — completed.
- `NC-PM-REVIEW-007A` — completed.

---

# Sprint 5.4 — LLM Integration, Auth UX, Multi-Step Execution, and Audit Logging
**Нед. 14 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed

**Предусловие:** Sprint 5.3 используется как baseline. Sprint 5.4 не меняет main-thread execution semantics, FreeCAD transaction path, sandbox policy или capability scope генерации CAD-кода; он системно доводит пользовательский контур взаимодействия с LLM: provider/model configuration, API key lifecycle, adapter diagnostics, session-vs-persistent auth behavior, multi-step execution contract и audit logging. При планировании/реализации опираться на текущий код как source of truth, а устаревшие naming-примеры в `doc/ARCH.md` трактовать как historical context, не как активный contract.

## Цель

Довести LLM integration до production-like пользовательского контура: понятная настройка провайдера, прозрачный источник API key, безопасное хранение ключа, предсказуемая работа `Save` / `Use once`, корректные ошибки при отсутствии keyring или key, диагностика adapter connectivity, корректное последовательное выполнение multi-step Python responses от LLM и структурированное audit logging для последующего анализа.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-017A    / Developer / Formalize API key source and adapter config contract      / completed
2. NC-DEV-UI-009A      / Developer / Redesign SettingsDialog UX for provider and auth storage   / completed
3. NC-DEV-UI-009B      / Developer / Surface adapter diagnostics in panel/runtime UI            / completed
4. NC-DEV-CORE-018A    / Developer / Execute multi-step LLM Python responses sequentially       / completed
5. NC-DEV-CORE-019A    / Developer / Define audit-log schema, redaction, and rotation contract  / completed
6. NC-DEV-CORE-020A    / Developer / Implement audit-log file sink and config toggle            / completed
7. NC-DEV-TEST-005A    / Developer / Regression matrix for key storage and adapter lifecycle    / completed
8. NC-DEV-TEST-005B    / Developer / Regression matrix for multi-step execution                 / completed
9. NC-DEV-TEST-005C    / Developer / Regression matrix for audit logging                        / completed
10. NC-PM-REVIEW-008A  / PM        / Review Sprint 5.4 LLM integration readiness                / completed
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-017A** | Developer | 1 | Формализовать contract источников API key и adapter configuration | `config/config.py`, `llm/registry.py`, затронутые тесты и docs | Явно определён и реализован precedence contract для API key: session key → environment variable → keyring → clear user-facing error; config file по-прежнему не хранит api_key; UI-only keys не протекают в adapter init; provider/model/base_url/timeout contract документирован и покрыт тестами | `TASK CODE: NC-DEV-CORE-017A` / Привести к явному и тестируемому виду contract источников API key и adapter configuration. В `config/config.py` и `llm/registry.py` зафиксировать precedence для ключа: temporary session key, environment variable, keyring, затем явная ошибка с инструкцией. Не писать API key в `config.json`. Убедиться, что UI-only config keys не попадают в adapter constructor. Обновить regression tests и sprint docs там, где нужно. Не менять worker, agent execution semantics, sandbox, main-thread path или capability scope.` |
| **NC-DEV-UI-009A** | Developer | 2 | Переработать SettingsDialog UX для provider, key storage и auth-state | `ui/settings.py`, затронутые тесты | Settings dialog явно показывает: выбранный provider, model, base_url, timeout, object limit, режим работы ключа (`save securely` vs `use once`), понятное состояние keyring availability, и различие между persistent key и session-only auth; write scope ограничен SettingsDialog | `TASK CODE: NC-DEV-UI-009A` / Переработать UX диалога настроек LLM без изменения runtime semantics. Пользователь должен видеть и понимать: выбранный provider, model, optional base_url, timeout, object limit, наличие/отсутствие secure storage, различие между `Save` и `Use once`. Добавить user-facing state labels/help text только в `ui/settings.py`. Не менять panel runtime surface, worker, executor, agent retry semantics, threading model или capability scope.` |
| **NC-DEV-UI-009B** | Developer | 3 | Вывести adapter/runtime diagnostics в panel-side UI без изменения execution path | `ui/panel.py`, затронутые тесты | Panel/user-facing runtime surface показывает понятные diagnostics при adapter init failure, missing key, missing keyring или invalid adapter config; scope ограничен panel-side messaging/status surface и не затрагивает SettingsDialog layout | `TASK CODE: NC-DEV-UI-009B` / Улучшить panel-side diagnostics для сценариев adapter init failure, missing key, missing keyring и invalid adapter config. Scope ограничен `ui/panel.py` и user-facing runtime messaging/status surface. Не менять SettingsDialog UX, worker, executor, agent retry semantics, threading model или capability scope.` |
| **NC-DEV-CORE-018A** | Developer | 3 | Научить agent/execution path корректно выполнять multi-step Python responses от LLM последовательно | `core/code_extractor.py`, `core/agent.py`, при необходимости `core/executor.py`, затронутые тесты | Если LLM возвращает несколько последовательных Python steps/subprograms в одном ответе, система не падает на этом как на malformed single-block case; steps выполняются в правильном порядке в рамках текущего transaction/execution contract; ошибки в одном step корректно прерывают дальнейшее выполнение и возвращают ясный feedback; main-thread execution semantics и sandbox policy не ослабляются | `TASK CODE: NC-DEV-CORE-018A` / Исправить execution contract для случаев, когда LLM возвращает несколько последовательных Python steps/subprograms в одном ответе. Система должна корректно распознавать и выполнять такие steps по порядку, а не выдавать общую ошибку только потому, что ответ не выглядит как один простой блок. Если один из steps не проходит sandbox/execution/validation, дальнейшие steps не выполняются, а пользователю возвращается понятный error path. Не ослаблять sandbox, не менять main-thread execution semantics, не переносить FreeCAD mutations из main thread. При необходимости скорректировать code extraction и agent orchestration, но не делать широкий рефакторинг.` |
| **NC-DEV-CORE-019A** | Developer | 4 | Зафиксировать audit-log contract: schema, redaction, caps и rotation policy | `config/config.py`, docs, при необходимости новый logging/audit schema module, targeted tests | Формат audit-log зафиксирован как JSONL; schema обязательных полей определена; redaction policy и preview caps определены числами; rotation/size policy определена числами; contract не двусмысленен для implementer | `TASK CODE: NC-DEV-CORE-019A` / Зафиксировать contract структурированного audit logging без реализации полного file sink. Выбрать и записать конкретные значения, а не общие слова. Обязательные решения: формат JSONL; путь вида `<app-data>/neurocad/logs/llm-audit.jsonl`; preview caps (`user_prompt_preview_chars`, `system_prompt_preview_chars`, `llm_response_preview_chars`, `code_preview_chars`) по 500 символов; `new_object_names` cap = 20; rotation policy = 5 файлов по 5 MB; toggle = `audit_log_enabled` в config; уровень логирования = event-only, без raw secret payloads. Зафиксировать обязательные и optional поля schema и redaction policy. Не менять execution semantics, worker/threading path или sandbox policy.` |
| **NC-DEV-CORE-020A** | Developer | 5 | Реализовать audit-log file sink и config toggle по утверждённому contract | `config/config.py`, `core/agent.py`, `llm/*`, при необходимости новый logging/audit module, targeted tests | При включённом `audit_log_enabled` создаётся JSONL file sink в app-data dir по согласованному пути; события пишутся последовательно; correlation IDs и timestamps присутствуют; redaction и caps соблюдаются; при выключенном toggle лог не создаётся; реализация следует schema/rotation contract из `NC-DEV-CORE-019A` | `TASK CODE: NC-DEV-CORE-020A` / Реализовать file sink для structured audit logging строго по contract из `NC-DEV-CORE-019A`. Писать JSONL в `<app-data>/neurocad/logs/llm-audit.jsonl`, поддерживать rotation policy 5x5 MB, уважать `audit_log_enabled`, писать correlation IDs, timestamps и event sequence от submit до final result. Не логировать API key, auth headers и raw secrets. Не менять main-thread execution semantics, sandbox policy или capability scope.` |
| **NC-DEV-TEST-005A** | Developer | 6 | Построить regression matrix для key storage и adapter lifecycle | `tests/test_config.py`, `tests/test_settings.py`, `tests/test_adapters.py`, при необходимости targeted tests | Есть автоматизированные сценарии: missing keyring, save without api_key, save with keyring, use-once session adapter, env var precedence, keyring precedence, unknown provider, adapter creation failure, UI does not persist session key | `TASK CODE: NC-DEV-TEST-005A` / Добавить и/или упорядочить regression matrix для key storage и adapter lifecycle. Тесты должны покрывать: отсутствие keyring, secure save, `Use once`, env/keyring precedence, unknown provider, invalid adapter config, session key not persisted, config file never contains api_key. Не смешивать эту задачу с multi-step execution и audit-log tests.` |
| **NC-DEV-TEST-005B** | Developer | 7 | Построить regression matrix для multi-step execution contract | `tests/test_agent.py`, при необходимости targeted execution tests | Multi-step Python response выполняется по шагам в правильном порядке; failure одного step останавливает последующие; sandbox policy не ослаблена; user-visible error path остаётся понятным | `TASK CODE: NC-DEV-TEST-005B` / Добавить deterministic tests на multi-step execution contract. Тесты должны покрывать: последовательное выполнение нескольких Python steps, остановку на ошибочном step, сохранение sandbox policy, и понятный final error path. Не смешивать эту задачу с auth/config или audit-log tests.` |
| **NC-DEV-TEST-005C** | Developer | 8 | Построить regression matrix для audit logging | `tests/test_agent.py`, `tests/test_config.py`, при необходимости новые targeted tests | Audit-log file создаётся только при включённом toggle; JSONL schema соблюдается; redaction policy соблюдается; correlation IDs, timestamps и rotation behavior покрыты тестами | `TASK CODE: NC-DEV-TEST-005C` / Добавить deterministic tests на structured audit logging. Тесты должны проверять: создание файла только при включённом `audit_log_enabled`, JSONL schema, наличие correlation IDs и timestamps, caps/redaction для preview fields, отсутствие API key и secrets в логе, и соблюдение rotation policy. Не смешивать эту задачу с key storage/adapters или multi-step execution tests.` |
| **NC-PM-REVIEW-008A** | PM | 9 | Проверить Sprint 5.4 как release-grade LLM integration baseline | Закрытый checklist | API key lifecycle, provider UX, adapter diagnostics, multi-step execution contract и audit logging доведены без architectural drift; automated gate по изменённым файлам clean; manual UX checklist для Settings / adapter init понятен | (1) API key precedence contract явно реализован и совпадает с docs (2) `config.json` не хранит api_key (3) `Save` и `Use once` отличаются и понятны пользователю (4) missing keyring и missing key дают ясные user-facing ошибки (5) panel-side diagnostics не получает UI-only config noise и не смешан с Settings UX (6) multi-step LLM Python response выполняется последовательно, а не падает как единый malformed case (7) failure одного step корректно останавливает последующие (8) audit-log contract зафиксирован конкретно: JSONL, schema, redaction caps, rotation policy, toggle, file path (9) audit-log file sink реализован по contract (10) worker/agent/threading semantics не изменены (11) pytest/ruff/mypy по изменённым файлам clean |

**Факт статуса на 2026-04-12:**
- `NC-DEV-CORE-017A` — completed.
- `NC-DEV-UI-009A` — completed.
- `NC-DEV-UI-009B` — completed.
- `NC-DEV-CORE-018A` — completed.
- `NC-DEV-CORE-019A` — completed.
- `NC-DEV-CORE-020A` — completed.
- `NC-DEV-TEST-005A` — completed.
- `NC-DEV-TEST-005B` — completed.
- `NC-DEV-TEST-005C` — completed.
- `NC-PM-REVIEW-008A` — completed.

---

# Sprint 5.5 — Math Namespace + Geometry Context + Placement Grounding
**Нед. 15 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑13)

**Предусловие:** Sprint 5.4 закрыт как baseline. Sprint 5.5 не меняет main-thread execution semantics, FreeCAD transaction path или threading model. Он устраняет конкретные классы провалов, зафиксированных в реальной dog-food сессии (лог 2026-04-13): провал шестерёнки из-за отсутствия тригонометрии, лишние итерации диалога из-за отсутствия размерного контекста объектов и незнания конвенции размещения Box в FreeCAD.

## Цель

Устранить три системных класса провалов, выявленных в реальной сессии пользователя:

1. **Math namespace gap**: LLM использует `App.cos()` / `App.sin()` (не существуют), потому что `import math` заблокирован, а prompt не предлагает рабочей альтернативы → 3 ретрая впустую → `max_retries_exhausted` на задаче шестерёнки.
2. **Context без размеров**: `DocSnapshot` содержит только `volume_mm3` и `placement`, но не геометрические параметры (`Length`, `Width`, `Height`, `Radius1`, `Radius2`) → LLM угадывает размеры → лишние попытки при позиционировании конуса на кубе, пропорциях рыбки.
3. **Незнание конвенции Box.Placement**: system prompt не объясняет, что `Part::Box.Placement` задаёт угол бокса, а не центр → 4 хода диалога на задачу соосности куба и конуса, которая решается одним кодом при правильном контексте.

Дополнительно: расширить `_categorize_error` для перехвата `module 'FreeCAD' has no attribute 'cos'` → `unsupported_api`, чтобы ошибка давала fast-fail вместо 3 одинаковых бесполезных ретраев.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-021A    / Developer / Pre-inject math into executor namespace + update prompt      / planned
2. NC-DEV-CORE-021B    / Developer / Extend _categorize_error for module attribute errors         / planned
3. NC-DEV-CORE-021C    / Developer / Enrich DocSnapshot with object-specific dimensions          / planned
4. NC-DEV-CORE-021D    / Developer / Add FreeCAD placement conventions to system prompt          / planned
5. NC-PM-REVIEW-009A   / PM        / Review Sprint 5.5 namespace + context grounding             / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-021A** | Developer | 1 | Pre-inject `math` в execution namespace и обновить prompt/defaults | `core/executor.py`, `config/defaults.py`, `tests/test_executor.py` | `math` модуль присутствует в namespace как ключ `"math"` в `_build_namespace()`; LLM-сгенерированный код `math.cos(x)`, `math.sin(x)`, `math.pi`, `math.sqrt(x)` выполняется без `import`; system prompt явно указывает, что `math` уже доступен и `import math` писать не нужно; sandbox policy остаётся: `import` по-прежнему блокируется tokenizer; тест подтверждает что `math.cos(0)` выполняется в namespace без import-строки | `TASK CODE: NC-DEV-CORE-021A` / Проблема: LLM генерирует `App.cos(t)` или `App.sin(t)` потому что prompt запрещает `import math`, а FreeCAD `App` модуль не содержит тригонометрию. Это приводит к `module 'FreeCAD' has no attribute 'cos'` и 3 бесполезным ретраям. Решение: в `neurocad/core/executor.py` в функции `_build_namespace(doc)` добавить `import math` внутри функции и включить `"math": math` в словарь namespace. Это не ослабляет sandbox: tokenizer по-прежнему блокирует слово `import` в пользовательском коде, а модуль `math` безопасен. В `neurocad/config/defaults.py` в `DEFAULT_SYSTEM_PROMPT` удалить запрещающие формулировки "Do not import the math module" и вместо них добавить явную инструкцию: `The math module is pre-loaded in the execution namespace. Use math.cos(), math.sin(), math.pi, math.sqrt(), math.atan2() etc. directly — no import statement needed or allowed.` Также убрать формулировку "Even for circular or radial patterns, do not import math" и заменить на позитивную: "For circular or radial patterns use math.cos(), math.sin(), math.pi directly." В `tests/test_executor.py` добавить regression: код `result = math.cos(0)` в namespace выполняется без ошибки; код с `import math` по-прежнему блокируется tokenizer. Не менять worker, agent, threading semantics, transaction path, sandbox policy для `import`-токена. |
| **NC-DEV-CORE-021B** | Developer | 1 | Расширить `_categorize_error` и `_make_feedback` для ошибок атрибутов модуля FreeCAD | `core/agent.py`, `tests/test_agent.py` | Ошибки вида `module 'FreeCAD' has no attribute 'cos'`, `module 'FreeCAD' has no attribute 'sin'`, `module 'App' has no attribute 'XXX'` категоризируются как `unsupported_api`, а не `runtime`; `unsupported_api` категория не ретраивает более одного раза (текущий fast-fail contract из Sprint 2.1 сохраняется); `_make_feedback` для этих случаев возвращает конкретное сообщение: `FreeCAD (App) module has no math functions. Use math.cos(), math.sin() etc. directly — math is pre-loaded.`; regression-тест подтверждает fast-fail без 3 ретраев | `TASK CODE: NC-DEV-CORE-021B` / Проблема: `_categorize_error` в `neurocad/core/agent.py` перехватывает `module 'part' has no attribute`, но не перехватывает `module 'freecad' has no attribute 'cos'` → ошибка попадает в `runtime` категорию → 3 одинаковых бесполезных ретрая. Решение: в `_categorize_error()` добавить паттерн до блока проверки `module 'part'`: если `"has no attribute" in error_lower` и в строке ошибки присутствует одно из имён `freecad`, `app`, `part`, `mesh`, `draft`, `sketcher`, `partdesign` как модуль — вернуть `"unsupported_api"`. В `_make_feedback()` для `"unsupported_api"` расширить ответ: если в ошибке встречается `'cos'`, `'sin'`, `'tan'`, `'sqrt'`, `'pi'`, `'atan'`, добавить конкретный hint: `FreeCAD modules have no math functions. Use math.cos(), math.sin() etc. — math is pre-loaded in the namespace.` Добавить regression тесты: `_categorize_error("module 'FreeCAD' has no attribute 'cos'")` → `unsupported_api`; `_categorize_error("module 'App' has no attribute 'sin'")` → `unsupported_api`; agent с этой ошибкой завершается через `execution_error` без 3 ретраев. Не менять threading semantics, transaction path, sandbox policy или capability scope. |
| **NC-DEV-CORE-021C** | Developer | 2 | Обогатить `DocSnapshot` геометрическими параметрами объектов | `core/context.py`, `tests/test_context.py` | `ObjectInfo` дополнен полем `properties: dict[str, float]`; `capture()` извлекает из каждого объекта доступные атрибуты из списка `("Length", "Width", "Height", "Radius", "Radius1", "Radius2", "Angle", "Pitch")`; `to_prompt_str()` выводит непустые properties компактно рядом с объектом: `L=50.0 W=50.0 H=50.0`; при отсутствии атрибута — не падает, просто пропускает; объём `max_chars=1000` для snapshot не снижается, при переполнении применяется текущая логика truncation; существующие тесты не регрессируют | `TASK CODE: NC-DEV-CORE-021C` / Проблема: `DocSnapshot` в `neurocad/core/context.py` содержит только `volume_mm3` и `placement`, но не геометрические параметры объектов (`Length`, `Width`, `Height`, `Radius1`, `Radius2` и т.д.). LLM не знает размеры существующих объектов и вынужден угадывать → лишние попытки при позиционировании и создании пропорциональных деталей. Решение: в `core/context.py` добавить поле `properties: dict[str, float] = field(default_factory=dict)` в `ObjectInfo`. В `capture()` после извлечения shape_type добавить цикл: `_GEOM_ATTRS = ("Length", "Width", "Height", "Radius", "Radius1", "Radius2", "Angle", "Pitch", "FirstAngle", "SecondAngle")`. Для каждого атрибута: `val = getattr(obj, attr, None); if val is not None: try: props[attr] = round(float(val), 2)` — c except-pass. Если `props` непустой, сохранить в `obj_info.properties`. В `to_prompt_str()` при выводе объекта: если `properties` непустой, добавить компактную строку `" props=" + " ".join(f"{k}={v}" for k, v in obj.properties.items())`. Обновить `tests/test_context.py`: mock-объект с `Length=50.0` появляется в prompt как `props=Length=50.0`; объект без геометрических атрибутов не ломает вывод. Не менять worker, agent, executor, threading semantics или sandbox policy. |
| **NC-DEV-CORE-021D** | Developer | 2 | Добавить FreeCAD placement conventions в system prompt | `config/defaults.py`, `tests/test_agent.py` или `tests/test_executor.py` | `DEFAULT_SYSTEM_PROMPT` содержит раздел с объяснением: `Part::Box.Placement` задаёт угол (0,0,0) бокса, не центр; центр Box(L,W,H) при Placement pos=(x,y,z) находится в (x+L/2, y+W/2, z+H/2); `Part::Cylinder` и `Part::Cone` Placement задаёт центр основания; примеры правильного позиционирования конуса соосно кубу; regression тест подтверждает, что эти строки присутствуют в build_system() output | `TASK CODE: NC-DEV-CORE-021D` / Проблема: system prompt не объясняет ключевую конвенцию FreeCAD: `Part::Box.Placement` задаёт позицию угла бокса, а не его центра. LLM не знает, что центр куба 50×50×50 при pos=(0,0,0) находится в (25,25,25), а не в (0,0,0). Это приводит к многоходовым исправлениям при позиционировании (4 хода в реальной сессии). Решение: в `neurocad/config/defaults.py` в конце `DEFAULT_SYSTEM_PROMPT` добавить раздел: `FreeCAD placement conventions: Part::Box.Placement sets the position of its corner (the vertex at minimum X,Y,Z), not its center. The center of a Box with Length=L, Width=W, Height=H placed at pos=(x,y,z) is at (x+L/2, y+W/2, z+H/2). Part::Cylinder and Part::Cone Placement sets the center of the base circle. Example: to place a Cone coaxially on top of a Box(50,50,50) placed at origin, use cone.Placement = App.Placement(App.Vector(25, 25, 50), ...)`. Не менять worker, agent, executor, sandbox policy, threading semantics или capability scope. Добавить smoke-тест: `build_system(snap)` содержит строку `Box.Placement sets the position of its corner`. |
| **NC-PM-REVIEW-009A** | PM | 3 | Проверить Sprint 5.5 как evidence-driven corrective scope | Закрытый checklist | Все 4 задачи закрыты без architectural drift; log-evidence явно соответствует каждой задаче; automated gate по изменённым файлам clean | (1) `math` pre-injected в `_build_namespace()`, доступен без `import` (2) sandbox policy: `import`-токен по-прежнему блокируется tokenizer (3) prompt указывает на pre-loaded `math` вместо запрета (4) `_categorize_error` ловит `module 'FreeCAD' has no attribute 'cos'` → `unsupported_api` (5) fast-fail без 3 ретраев для attribute errors (6) `ObjectInfo.properties` содержит L/W/H/Radius при наличии атрибутов (7) `to_prompt_str()` выводит properties компактно (8) system prompt содержит FreeCAD placement conventions (Box corner vs center) (9) build_system() output включает conventions (10) worker/agent/threading semantics не изменены (11) pytest/ruff/mypy по изменённым файлам clean |

**Правила останова Sprint 5.5:** ослабление sandbox policy для `import`-токена → rejected / расширение capability scope (новые FreeCAD API, новые объектные типы) без benchmark evidence → rejected / изменение main-thread execution semantics, transaction path или threading model → rejected / добавление streaming/export/settings вне scope → стоп / ответ без TASK CODE = невалиден.

---

# Sprint 5.6 — Cancellation Fast-Exit + Handoff Timeout Tuning + Runtime Feedback Expansion
**Нед. 16 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.5 закрыт как baseline. Sprint 5.6 не меняет main-thread execution semantics, FreeCAD transaction path, threading model или sandbox policy. Он устраняет четыре класса провалов, зафиксированных в dog-food-сессии 2026-04-14 (аудит-лог за 6 часов: 55 attempts, success rate 36%). Stop-button был добавлен пользовательским UX-слоем ранее, но agent retry loop его «не замечал» — Cancelled попадал в обычный runtime-цикл и тратил токены на бесполезные ретраи.

## Цель

Устранить четыре класса провалов, выявленных в реальной сессии пользователя:

1. **Cancellation retry leak**: после нажатия Stop экзекутор возвращает `error="Cancelled"`, agent трактует это как обычный runtime-error и делает MAX_RETRIES=3, расходуя 2 лишних LLM-запроса и дублируя сообщение `Max retries exceeded: Cancelled` в audit.
2. **Handoff timeout loop + слабый feedback**: хардкод 15 s в `worker._request_exec` срабатывает на сложных сборках (болт M24 с резьбой, bicycle frame); agent retryит тот же тяжёлый код и таймаутит снова; generic feedback «Execution timed out» не подсказывает LLM, что делать.
3. **`list index out of range` без hint**: частая ошибка `edge.Vertexes[1]` на круговых рёбрах (у них `len==1`), generic feedback не даёт направления для исправления.
4. **`Shape is invalid` vs `Shape is null`**: оба попадают в категорию `validation`, но причины и фиксы разные. `null` = shape не вычислена; `invalid` = вычислена, но OCCT считает её malformed (self-intersection, zero-area face).

Дополнительно: `exec_handoff_timeout_s` вынесен в `config.json` (default 60 s, раньше был хардкод 15 s); новые события `cancelled_by_user` и `handoff_timeout` в audit-лог для последующего анализа.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-022A  / Developer / Cancellation fast-exit в agent.run (нет retry после "Cancelled")   / planned
2. NC-DEV-CORE-022B  / Developer / Handoff timeout → config + feedback "разбей на блоки" (no retry)   / planned
3. NC-DEV-CORE-022C  / Developer / _make_feedback для "list index out of range" и "Shape is invalid" / planned
4. NC-DEV-DOC-006    / Developer / Обновить doc/SPRINT_PLANS.md + README + оглавление                / planned
5. NC-PM-REVIEW-010  / PM        / DoD-чеклист + ручные тесты для пользователя                       / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-022A** | Developer | 1 | Cancellation fast-exit: после первой «Cancelled» попытки agent завершается без retry | `core/agent.py`, `tests/test_agent.py` | В `_make_feedback` runtime-ветка первой проверкой распознаёт строку, начинающуюся на `"cancelled"` → возвращает `"Cancelled by user."`; в `agent.run` retry-loop перед `history.add(Role.FEEDBACK, ...)` — fast-exit: один `audit_log("agent_error", {"error_type": "cancelled_by_user", ...})` и `AgentResult(ok=False, attempts=<текущий>, error="Cancelled by user")`; regression-тест `test_run_cancellation_fast_exit` подтверждает `mock_exec.call_count == 1`, `result.attempts == 1`, `result.error == "Cancelled by user"` | `TASK CODE: NC-DEV-CORE-022A` / Проблема: воркер при нажатии Stop возвращает `{"ok": False, "error": "Cancelled"}`, agent.run трактует это как обычный runtime error → 3 retries подряд → `Max retries exceeded: Cancelled` в audit. Решение: (1) в `_make_feedback` runtime-ветка первой же проверкой ловит `error_lower.strip().startswith("cancelled")` и возвращает `"Cancelled by user."`; (2) в `agent.run` в ветке «At least one block failed» перед `history.add(Role.FEEDBACK, feedback)` вставить fast-exit: если `last_error.strip().lower().startswith("cancelled")` — записать один `audit_log("agent_error", {"error_type": "cancelled_by_user", ...})` и вернуть `AgentResult(ok=False, attempts=attempts, error="Cancelled by user", new_objects=[], rollback_count=total_rollback_count)`. Не менять `worker.cancel()`, `_on_stop()` панели, threading semantics или transaction path. |
| **NC-DEV-CORE-022B** | Developer | 1 | Handoff timeout: из конфига (default 60s) + actionable feedback «split the script» + fast-exit | `core/worker.py`, `core/agent.py`, `config/config.py`, `tests/test_worker.py`, `tests/test_agent.py`, `tests/test_config.py` | `load_config()` экспонирует `exec_handoff_timeout_s` (default 60.0); `worker._request_exec` читает это значение при каждом вызове (`try/except` → fallback 60.0); `_make_feedback` для `category="timeout"` при наличии подстроки «handoff» в error возвращает сообщение с фразой «Split the script»; в `agent.run` при `category == "timeout"` и `"handoff" in last_error.lower()` — fast-exit c `audit_log` типа `handoff_timeout`; regression-тесты подтверждают (a) timeout читается из конфига, (b) fallback-ветка работает, (c) agent не ретраит handoff timeout | `TASK CODE: NC-DEV-CORE-022B` / Проблема: в `worker._request_exec` хардкод `timeout=15.0` — слишком мало для сложных болтов с резьбой и сборок, поэтому exec handoff таймаутит; при этом agent ретраит тот же тяжёлый код → повторный таймаут. Решение: (1) в `config/config.py` добавить `DEFAULT_EXEC_HANDOFF_TIMEOUT_S = 60.0` и ключ `exec_handoff_timeout_s` в оба return-dict внутри `load()`; (2) в `core/worker.py` импортировать `from ..config.config import load as load_config`, и в `_request_exec` перед `self._exec_event.wait(...)` вычислить `timeout_s = float(load_config().get("exec_handoff_timeout_s", 60.0))` (с `try/except Exception: timeout_s = 60.0`); (3) в `_make_feedback` категория `"timeout"`: при наличии `"handoff" in error.lower()` вернуть расширенное сообщение с фразой «Split the script into 2–3 smaller fenced blocks»; (4) в `agent.run` в ветке handled-failure добавить fast-exit для handoff-timeout аналогично Cancellation (один `audit_log("agent_error", {"error_type": "handoff_timeout", ...})`). Не трогать threading model и transaction path. |
| **NC-DEV-CORE-022C** | Developer | 2 | Feedback-ветки для `list index out of range` и `Shape is invalid` | `core/agent.py`, `tests/test_agent.py` | В `_make_feedback` runtime-блок (после sketchobject/support, до must-be-bool) — ветка `"list index out of range" in error_lower` с упоминанием circular edges / `edge.Vertexes[1]` / `shape.Faces[0]` / `len()` перед индексом; в validation-блоке (ДО ветки `"shape is null"`) — ветка `"shape is invalid"` с рекомендацией `shape.fix()` / `shape.removeSplitter()` / `shape.isValid()`; regression-тесты подтверждают наличие ключевых фраз | `TASK CODE: NC-DEV-CORE-022C` / Проблема: `edge.Vertexes[1]` на круговых/арочных рёбрах → IndexError (у закрытой окружности `len == 1`); `Shape is invalid` отличается от `Shape is null` (вычислено, но malformed), но оба получают generic «Validation failed». Решение: (1) в `_make_feedback` в runtime-блоке добавить ветку `"list index out of range"` с конкретными FreeCAD-паттернами: `edge.Vertexes[1]` на круговой дуге, `shape.Faces[0]` на wire/compound, `doc.Objects[i]` на пустом документе; (2) в validation-блоке добавить ветку `"shape is invalid"` ПЕРЕД `"shape is null"` с hint-ами `shape.fix()`, `shape.removeSplitter()`, `shape.isValid()` между boolean операциями. Не менять сигнатуры, не расширять capability scope. |
| **NC-DEV-DOC-006** | Developer | 3 | Обновить `doc/SPRINT_PLANS.md` + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел «Sprint 5.6» присутствует в оглавлении и в теле документа в каноническом формате (Статус, Предусловие, Цель, Rolling Plan, Задачи-таблица, Правила останова); README отражает текущий статус Sprint 5.6; `doc/RELEASE_NOTES.md` содержит v0.9 ↔ Sprint 5.6 bullet-пункты; `grep -c "Sprint 5.6" doc/SPRINT_PLANS.md` ≥ 3 | `TASK CODE: NC-DEV-DOC-006` / Обновить sprint-doc в стиле Sprint 5.5 (заголовок, статус с датой, предусловие, цель, rolling plan, таблица задач, правила останова). В README поднять статус с Sprint 5.4/5.5 до Sprint 5.6. В RELEASE_NOTES добавить v0.9. Сводная таблица переименовывается в v0.1 → v0.9 с новыми строками: Cancellation, Handoff timeout, IndexError hint, Invalid shape hint. Не переписывать существующие спринты. |
| **NC-PM-REVIEW-010** | PM | 4 | DoD-чеклист + ручные тесты M1–M6 | Закрытый checklist | Все 10 пунктов DoD approved; пройдены шесть ручных сценариев M1–M6 в живом FreeCAD 1.1 | (1) `_make_feedback("Cancelled", "runtime")` → `"Cancelled by user."` (2) Cancelled exec → агент возвращается с `attempts == 1`, не ретраит (3) Audit логирует один `agent_error` с `error_type == "cancelled_by_user"` (4) `load_config()["exec_handoff_timeout_s"] == 60.0` по умолчанию (5) `worker._request_exec` использует значение из `load_config()` (6) `_make_feedback` для handoff timeout содержит «Split the script» (7) Handoff timeout → агент не ретраит (attempts == 1, audit `handoff_timeout`) (8) `_make_feedback` даёт конкретные hints для `list index out of range` и `Shape is invalid` (9) `doc/SPRINT_PLANS.md` содержит раздел Sprint 5.6 в каноническом формате (10) `pytest --tb=short` clean, существующие 204 теста не регрессируют |

**Правила останова Sprint 5.6:** изменение threading model / main-thread execution semantics / FreeCAD transaction path → rejected / ослабление sandbox policy (разблокировка `import`, whitelist новых модулей) → rejected / расширение capability scope (новые FreeCAD API, новые object types) без benchmark evidence → rejected / `Cancelled` или `handoff timeout` продолжают попадать в retry loop → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.7 — Complex Task Success: Recipe Fix + Multi-Block Protocol + Static Verifier
**Нед. 17 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.6 закрыт как baseline. Sprint 5.7 не меняет main-thread execution semantics, FreeCAD transaction path, threading model, sandbox policy или capability scope. Он чинит **корректность рецептов** в `DEFAULT_SYSTEM_PROMPT` и добавляет **multi-block protocol**, чтобы LLM перестал генерировать 9000-символьные монолиты. Мотивация — пользовательская цель: «Сделай сложный болт M30 с резьбой и шайбой» должен успешно выполняться, а не просто аккуратно проваливаться.

## Цель

Устранить три системных блокера успеха сложных запросов, которые Sprint 5.6 не мог исправить на feedback-уровне:

1. **Бракованный recipe в prompt**: `DEFAULT_SYSTEM_PROMPT` рекомендовал `Part::LinearPattern` / `Part::Array` как «always reliable» пример для многоходовой резьбы. Эти типы не существуют в Part WB — LLM честно копировал и падал с `is not a document object type`. Это внутреннее противоречие промпта: раздел `## Blocked` называл их несуществующими, а раздел `## PART V — Bolt` рекомендовал как основной вариант.
2. **Монолитный вывод**: промпт явно требовал `no markdown fences`, что вынуждало LLM выдавать весь болт+резьба+шайба одним блоком (9429 символов в dog-food-логе) → handoff timeout. Несколько fenced-блоков уже поддерживались executor-ом, но в промпте об этом не было ни слова.
3. **Отсутствие регрессии для recipe**: ручная ревизия прямых советов в промпте ловит ошибки не раньше dog-food-сессии. Нужен static verifier, который гарантирует: каждый `doc.addObject(TYPE)` / `body.newObject(TYPE)` в промпте использует реально существующий FreeCAD-тип.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-023A  / Developer / Починить recipe в defaults.py (убрать Part::LinearPattern из позитивных примеров)  / planned
2. NC-DEV-CORE-023B  / Developer / Multi-block protocol для assemblies в system prompt                                  / planned
3. NC-DEV-CORE-023C  / Developer / Static recipe verifier (tests/test_prompt_recipe.py)                                  / planned
4. NC-DEV-DOC-007    / Developer / Обновить doc/SPRINT_PLANS.md + README + RELEASE_NOTES                                / planned
5. NC-PM-REVIEW-011  / PM        / DoD-чеклист + ручные dog-food тесты на живом FreeCAD                                 / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-023A** | Developer | 1 | Починить recipe в `DEFAULT_SYSTEM_PROMPT` — убрать `Part::LinearPattern` из позитивных примеров | `config/defaults.py` | В промпте нет `doc.addObject("Part::LinearPattern", ...)` / `Part::PolarPattern` / `Part::MultiTransform` / `Part::Array` в позитивных code-примерах; рекомендации заменены на Python-loop + `Part.makeCompound`; три места исправлены: «Fake thread via stacked discs» (строка ~568), «Bolt assembly patterns» (строка ~674), «Decorative thread — full example» (строка ~731); раздел `## Blocked` сохранён — LLM должен продолжать видеть, что эти типы не существуют | `TASK CODE: NC-DEV-CORE-023A` / Проблема: `DEFAULT_SYSTEM_PROMPT` одновременно (a) рекомендует `Part::LinearPattern` в разделе "Decorative thread" как "always reliable" и (b) перечисляет его в разделе "Blocked" как несуществующий. LLM чаще следует позитивному примеру. Решение: в трёх местах (fake-thread comment-block, bolt assembly bullet, decorative-thread example) заменить `doc.addObject("Part::LinearPattern", ...)` на Python-loop: `copies = []; for i in range(...): c = shape.copy(); c.translate(...); copies.append(c); pat = doc.addObject("Part::Feature", "ThreadPat"); pat.Shape = Part.makeCompound(copies)`. Раздел `## Blocked` оставить — он нужен как пояснение для LLM после неудачи. Добавить в пример финальный `Part::Cut` шаг (режем compound из shank), чтобы LLM видел полный путь. |
| **NC-DEV-CORE-023B** | Developer | 1 | Multi-block protocol для assemblies в system prompt | `config/defaults.py` | Заголовок «Output format» разрешает fenced blocks для сложных сборок; новый раздел «Multi-block protocol for complex assemblies» со three-block canonical layout (bolt+thread+washer) и списком правил: ≤80 строк на блок, `doc.recompute()` в конце, переменные не persist между блоками → `doc.getObject("Name")`, Part::Cut изолированы в отдельный блок | `TASK CODE: NC-DEV-CORE-023B` / Проблема: промпт требовал `no markdown fences`, поэтому LLM генерировал один блок 9429 символов → handoff timeout на болте с резьбой. Executor уже поддерживает multi-block (`extract_code_blocks` возвращает список), но LLM об этом не знал. Решение: (1) в разделе "Output format" поменять "no markdown fences" на "simple → unfenced, complex → 2–3 fenced ```python``` blocks"; (2) добавить отдельный раздел "Multi-block protocol for complex assemblies" после "Workbench choice" — пример bolt+thread+washer в три блока (base primitives + initial fuse → thread helix/sweep/cut → washer separate), плюс 5 правил: doc.recompute() на конце, ≤80 строк, переменные не persist, doc.getObject() для re-fetch, block failure → skip subsequent. Не трогать executor и агент — multi-block поддержан с Sprint 5.4. |
| **NC-DEV-CORE-023C** | Developer | 2 | Static recipe verifier | `tests/test_prompt_recipe.py` | Новый файл теста с 5 проверками: (1) sanity — >20 addObject examples в промпте, (2) все типы из VALID_OBJECT_TYPES whitelist (~40 типов из Part / PartDesign / Sketcher / Draft WB), (3) BLOCKED_OBJECT_TYPES (LinearPattern/PolarPattern/MultiTransform/Array) не появляются как constructor args, (4) блокированные типы упомянуты хотя бы как warnings, (5) multi-block protocol раздел присутствует с ```python блоками и `doc.getObject` | `TASK CODE: NC-DEV-CORE-023C` / Создать `tests/test_prompt_recipe.py`. Использовать regex `(?:doc\|body\|\w+)\.(?:addObject\|newObject)\s*\(\s*["\']([A-Za-z]+::\w+)["\']` для извлечения типов из `DEFAULT_SYSTEM_PROMPT`. Whitelist VALID_OBJECT_TYPES — 40+ типов Part / PartDesign / Sketcher. Blocklist BLOCKED_OBJECT_TYPES — 4 несуществующих Part::LinearPattern etc. Тесты fail с явным форматом: line N: <unknown type> — чтобы легко находить. Тесты должны проходить после задач 023A и 023B. |
| **NC-DEV-DOC-007** | Developer | 3 | Обновить doc/SPRINT_PLANS.md + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел «Sprint 5.7» в каноническом формате; README указывает Sprint 5.7; RELEASE_NOTES содержит v1.0 ↔ Sprint 5.7 | `TASK CODE: NC-DEV-DOC-007` / Обновить документацию по аналогии с Sprint 5.5/5.6. Версия прыгает 0.9 → 1.0 (major prompt recipe fix + multi-block protocol — это граница MVP по корректности рецептов). |
| **NC-PM-REVIEW-011** | PM | 4 | DoD-чеклист + ручные dog-food тесты | Закрытый checklist | Все 8 пунктов DoD approved; пройдены ручные тесты R1–R4 на живом FreeCAD 1.1 | (1) Static verifier все 5 тестов зелёные (2) В промпте нет `Part::LinearPattern` / `Part::Array` / `Part::PolarPattern` / `Part::MultiTransform` как constructor args (3) Раздел "Multi-block protocol" присутствует в промпте (4) Все `doc.addObject` / `body.newObject` типы в промпте входят в VALID_OBJECT_TYPES whitelist (5) `pytest --tb=short` clean (6) README упоминает Sprint 5.7 (7) RELEASE_NOTES имеет раздел 5.7 (8) Ручной тест «Сделай болт M24 с резьбой» завершается успешно хотя бы в 3 из 5 прогонов |

**Правила останова Sprint 5.7:** изменение threading model / main-thread execution semantics / FreeCAD transaction path → rejected / ослабление sandbox policy → rejected / расширение capability scope (новые FreeCAD API, новые object types, новые workbenches) → rejected / возврат `Part::LinearPattern` в позитивные примеры → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.8 — Parametric Recipes + Multi-Block Scoping + Gear Reality Check
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.7 закрыт. Первый dog-food под новым multi-block протоколом выявил конкретные провалы: 2/9 (22%) вместо целевых 60%. Log analysis `scripts/dogfood_check.py --since "2026-04-18 10:00"` дал три чистых корневых причины: (1) LLM не переобъявляет параметры между блоками → `NameError` в 7/9 провалов; (2) `PartDesign::InvoluteGear` не существует как document-object-type в stock FreeCAD 1.1 (нужен Gears WB addon) — 2/9 провалов на шестерёнке; (3) Thread Cut → `['Touched', 'Invalid']` получает fillet-диагностику, хотя fillet не задействован — 3/9 провалов на болтах.

## Цель

Поднять dog-food success rate на R1–R4 с 22% до ≥ 60% за счёт правок **промпта и feedback-сообщений**, без изменений executor / threading / transaction / sandbox.

1. **Parameter header в каждом блоке.** Multi-block protocol из Sprint 5.7 имел одну строку "variables do NOT persist" — LLM её игнорирует. Новый протокол явно требует re-declare всех численных констант в начале каждого блока, и canonical пример теперь параметризован (`major_d`, `pitch`, `minor_d = major_d - 1.226 * pitch`) — LLM учится паттерну и может масштабировать на M8…M48, а не только M24.
2. **Gear без addon.** Заменить `PartDesign::InvoluteGear` (отсутствует в stock FreeCAD 1.1) на parametric Part WB approximation: base disc (Revolution) + trapezoidal tooth (Part::Box) + Python loop + makeCompound + MultiFuse. Добавить в `_make_feedback` конкретный hint если LLM всё равно попробует InvoluteGear. Удалить тип из VALID_OBJECT_TYPES whitelist, добавить в BLOCKED_OBJECT_TYPES.
3. **Thread-specific Touched/Invalid.** Расширить `_make_feedback` — если имя невалидного объекта содержит `Thread`/`Bolt`/`Sweep`/`Helix`/`Cut`, давать thread-specific чеклист (sweep.isValid, helix в пределах shank, ≤ 10 turns, Frenet=True, Cut напрямую от shank без intermediate cylinder).

**Non-goals:** изменение threading model / transaction path / sandbox policy; расширение capability scope на новые workbenches; добавление addon-зависимых API.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-024A  / Developer / Multi-block protocol: parameter header + parametric bolt example  / planned
2. NC-DEV-CORE-024B  / Developer / Убрать PartDesign::InvoluteGear из recipe + whitelist + feedback  / planned
3. NC-DEV-CORE-024C  / Developer / Thread-specific ветка в Touched/Invalid feedback                   / planned
4. NC-DEV-DOC-008    / Developer / Sprint 5.8 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES         / planned
5. NC-PM-REVIEW-012  / PM        / DoD + повторный dog-food через scripts/dogfood_check.py           / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-024A** | Developer | 1 | Переписать Multi-block protocol: parameter header + параметрический bolt пример | `config/defaults.py` | Раздел «Multi-block protocol for complex assemblies» содержит: блок `CRITICAL: every block is a FRESH Python namespace` с явным правилом о re-declare; блок `Parameter header` с ISO 261 pitch-таблицей и derived formulas (minor_d, shank_r, head_h); canonical bolt example полностью параметризован (major_d, pitch, thread_h = min(30.0, 10*pitch)); каждый из 3 блоков имеет собственный parameter header; правила пронумерованы и начинаются с "Parameter header first" | `TASK CODE: NC-DEV-CORE-024A` / Проблема: dog-food 2026-04-18 показал 7/9 провалов из-за `NameError: name 'pitch'/'head_height'/'major_diameter' is not defined` во втором или третьем блоке. LLM из Sprint 5.7 видит "variables do NOT persist" одной строкой и игнорирует. Решение: в `config/defaults.py` полностью переписать раздел "Multi-block protocol": (a) добавить CRITICAL-блок с жирным правилом: "Re-declare every numeric parameter at the top of every block"; (b) добавить "Parameter header" подраздел с ISO 261 coarse pitch таблицей и derived formulas; (c) переписать canonical 3-block пример: БЕЗ хардкода M24-specific чисел — использовать major_d/pitch/minor_d/shank_r/head_h/head_key/shank_h/thread_h; (d) каждый блок начинается с "parameter header" комментария + переобъявление; (e) thread_h = min(30.0, 10 * pitch) — явное ограничение ≤10 turns; (f) пересчитать rules list, поставив "Parameter header first" первым. Не трогать executor, transaction model или sandbox. |
| **NC-DEV-CORE-024B** | Developer | 1 | Убрать `PartDesign::InvoluteGear` из recipe + whitelist + feedback | `config/defaults.py`, `tests/test_prompt_recipe.py`, `core/agent.py`, `tests/test_agent.py` | В `defaults.py` раздел "Gear" заменён на Part WB approximation (parameter header + Revolution disc + Part::Box tooth + Python loop + makeCompound + MultiFuse); `VALID_OBJECT_TYPES` больше не содержит `PartDesign::InvoluteGear`; `BLOCKED_OBJECT_TYPES` его содержит; `_make_feedback` для `"PartDesign::InvoluteGear' is not a document object type"` возвращает actionable hint с инструкциями построения через Part::Revolution + Part::Box loop; regression-тест `test_make_feedback_involute_gear_not_a_type` зелёный; `test_default_prompt_does_not_use_blocked_types_as_positive_examples` зелёный | `TASK CODE: NC-DEV-CORE-024B` / Проблема: 2/9 провалов в dog-food — LLM следует нашему recipe `doc.addObject("PartDesign::InvoluteGear", "GearProfile")`, FreeCAD 1.1 возвращает "'PartDesign::InvoluteGear' is not a document object type". Этот тип требует внешнего Gears Workbench addon. Решение: (1) В `defaults.py` раздел "Gear" переписать под Part WB: parameter header (teeth_n, module_m, pitch_r = teeth_n*module_m/2, root_r, tip_r, tooth_w), base disc через Part::Revolution от 0 до root_r, trapezoidal tooth как Part::Box с Placement от root_r вдоль +X, Python loop `for i in range(teeth_n): c = tooth.Shape.copy(); c.rotate(...)`, Part::Feature + Part.makeCompound(copies), Part::MultiFuse для disc+teeth. (2) В `tests/test_prompt_recipe.py` удалить `"PartDesign::InvoluteGear"` из VALID_OBJECT_TYPES, добавить в BLOCKED_OBJECT_TYPES с комментарием про addon requirement. (3) В `core/agent.py::_make_feedback` в ветке "is not a document object type" добавить case для `bad_type == "PartDesign::InvoluteGear"` с полным рецептом через Part WB. (4) Не вводить зависимость от Gears WB — это addon, который может отсутствовать у пользователя. |
| **NC-DEV-CORE-024C** | Developer | 2 | Thread-specific ветка в Touched/Invalid feedback | `core/agent.py`, `tests/test_agent.py` | Функция `_re_search_invalid_name(error)` извлекает `NAME` из `"Validation failed for NAME: ..."`; в `_make_feedback` validation-ветке `touched and invalid`: если name содержит токен `thread`/`bolt`/`sweep`/`helix`/`cut`, возвращать thread-specific чеклист (sweep.Shape.isValid(), helix.Height < shank.Height, ≤10 turns, Frenet=True, Cut напрямую от body, retry с меньшим thread_h/depth); иначе — fallback на существующую fillet-диагностику; тест `test_make_feedback_touched_invalid_thread_specific` зелёный | `TASK CODE: NC-DEV-CORE-024C` / Проблема: 3/9 провалов dog-food — `"Validation failed for ThreadedBolt: ['Touched', 'Invalid']"`. Текущий feedback говорит "убери Fillet", но Fillet не задействован — OCCT валидирует сам Part::Cut результата sweep vs shank. Решение: добавить helper `_re_search_invalid_name(error) -> str | None` с regex `r"validation failed for (\S+?):"`, вернуть имя объекта. В `_make_feedback` в ветке `touched + invalid`: если name содержит substring из {thread, bolt, sweep, helix, cut} — выдать thread-специфичный чеклист (6 шагов: sweep.Shape.isValid(); helix.Height strictly ≤ shank.Height; thread ≤ 10 turns = thread_h ≤ 10*pitch; Frenet=True; Cut.Base=body, Cut.Tool=sweep без промежуточного Fuse; retry с shorter thread_h и меньшим thread_depth). Регрессия: существующий test_make_feedback_validation_touched_invalid (fillet-case) остаётся зелёным. |
| **NC-DEV-DOC-008** | Developer | 3 | Sprint 5.8 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел "Sprint 5.8" в каноническом формате; README поднят до Sprint 5.8; RELEASE_NOTES содержит v1.1 ↔ Sprint 5.8 с dog-food baseline (2/9=22%) и целевой планкой ≥60% | `TASK CODE: NC-DEV-DOC-008` / По шаблону Sprint 5.7. Версия 1.0 → 1.1. Упомянуть конкретные результаты dog-food baseline и три корневые причины. |
| **NC-PM-REVIEW-012** | PM | 4 | DoD + повторный dog-food через scripts/dogfood_check.py | Закрытый checklist | Все 8 пунктов DoD approved; новый dog-food прогон ≥ 60% на R1–R3 и 100% на R4 | (1) `VALID_OBJECT_TYPES` не содержит `PartDesign::InvoluteGear` (2) `BLOCKED_OBJECT_TYPES` содержит `PartDesign::InvoluteGear` (3) Прmpт содержит "Parameter header" секцию (4) Canonical bolt example использует `major_d`/`pitch`/`minor_d` вместо хардкода (5) `_make_feedback("... 'PartDesign::InvoluteGear' ...", "runtime")` содержит "Part WB" и "makeCompound" (6) Thread-related Touched/Invalid → чеклист с `Frenet`, `sweep.Shape.isValid()`, `10 * pitch` (7) pytest clean (229+ tests) (8) `python scripts/dogfood_check.py --since "..."` на новой сессии ≥ 60% pass rate |

**Правила останова Sprint 5.8:** изменение threading model / main-thread execution semantics / FreeCAD transaction path → rejected / ослабление sandbox policy → rejected / введение зависимости от addon (Gears WB, Fasteners WB) без явного fallback → rejected / возврат `PartDesign::InvoluteGear` в положительные рецепты → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.9 — Realism: Chamfers, Fillets, Visual Detail
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.8 закрыт — запросы выполняются, dog-food ~больше 60%. Пользовательский визуальный feedback: «результат выглядит сильно упрощенным: нет граней, закруглений, выдавливаний… возможно есть конкретная инструкция которая упрощает, надо её убрать». Приложены фото реальных болтов ISO для сравнения — головка с фаской на торце, резьбовой заход с фаской, отчётливые переходные элементы.

## Цель

Устранить неявную инструкцию упрощения, которая толкает LLM генерировать спартанские примитивы без фасок/скруглений. Диагноз из [defaults.py](neurocad/config/defaults.py):

1. **Canonical bolt example в multi-block protocol** не содержал ни одного `Part::Chamfer` — LLM копировал буквально и получал голый prism+cylinder.
2. **WARNING на строке 898** формулировался негативно («DO NOT apply fillets to the final threaded body») — LLM обобщал до «никогда не использовать фаски».

Фикс — две корректировки промпта:
- **Canonical bolt example** дополнен фасками на хэд (все рёбра) и шанк (только круговые рёбра, фильтр по `e.Curve.__class__.__name__ == "Circle"`) ДО Fuse. Это даёт хэд-фаски и резьбовой заход как у реальных болтов.
- **WARNING переформулирован в позитив**: «ИСПОЛЬЗУЙ фаски на примитивах ДО Fuse — поощряется». Технический ограничитель (не filet'ить финальное резьбовое тело после Cut) остался, но теперь выглядит как граничное условие, а не отговорка.
- Добавлен отдельный раздел «Realism — chamfers and fillets are the default» перед rules-list с конкретными рекомендованными глубинами (head_ch = 0.08 × major_d, shank_ch = 0.04 × major_d, washer edge break = 0.05 × flange_h, gear root fillet = 0.15 × module_m).

**Non-goals:** изменение threading/transaction/sandbox; расширение capability scope; новые FreeCAD API.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-025A  / Developer / Canonical bolt Block 1 + Part::Chamfer на хэд и шанк               / planned
2. NC-DEV-CORE-025B  / Developer / Переформулировать WARNING про fillets в позитивную рекомендацию    / planned
3. NC-DEV-CORE-025C  / Developer / Новый раздел «Realism» в промпте с рекомендованными размерами     / planned
4. NC-DEV-DOC-009    / Developer / Sprint 5.9 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES        / planned
5. NC-PM-REVIEW-013  / PM        / DoD + dog-food: визуальная проверка «болты выглядят реалистично» / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-025A** | Developer | 1 | Canonical bolt Block 1 + Part::Chamfer на head и shank | `config/defaults.py` | Block 1 содержит `Part::Chamfer "HeadChamfered"` на всех рёбрах hex prism (depth = `head_ch = 0.08 * major_d`); `Part::Chamfer "ShankChamfered"` на круговых рёбрах цилиндра (filter `e.Curve.__class__.__name__ == "Circle"`, depth = `shank_ch = 0.04 * major_d`); Fuse использует `head_chamfered` и `shank_chamfered` как Base/Tool, а не сырые примитивы; все промежуточные `.Visibility = False`; static verifier `tests/test_prompt_recipe.py` зелёный (типы в whitelist) | `TASK CODE: NC-DEV-CORE-025A` / Пользовательский feedback 2026-04-18: «нет граней, закруглений, выдавливаний». Canonical bolt recipe в multi-block protocol был слишком спартанским — LLM копировал буквально и выдавал голый prism+cylinder. Фикс: в Block 1 после создания head (Part::Prism) и shank (Part::Cylinder) добавить промежуточный Part::Chamfer каждый: (1) head_chamfered = Chamfer на ВСЕХ рёбрах hex prism с depth = head_ch; (2) shank_chamfered = Chamfer только на круговых рёбрах (filter `e.Curve.__class__.__name__ == "Circle"`) с depth = shank_ch — это thread-entry chamfer. Fuse принимает `head_chamfered` и `shank_chamfered`, не raw primitives. Параметр header расширен: head_ch = 0.08 * major_d, shank_ch = 0.04 * major_d. |
| **NC-DEV-CORE-025B** | Developer | 1 | Переформулировать WARNING про fillets в позитив | `config/defaults.py` | Строка ~898 ранее: `WARNING — DO NOT apply Part::Fillet or Part::Chamfer to the final assembled+threaded body.`; теперь: `Chamfers and fillets — ENCOURAGED for realism. ALWAYS add Part::Chamfer / Part::Fillet to individual primitives BEFORE fusing.` Хард-ограничитель про «не filet'ить финальное тело после Cut» сохранён, но теперь как конкретное условие, не как запрет вообще; пример позитивного использования приведён (chamfer на head + fuse + cut thread — уже в canonical example) | `TASK CODE: NC-DEV-CORE-025B` / Заменить WARNING-блок на позитивный recommendation-блок. Начало: `# Chamfers and fillets — ENCOURAGED for realism:`. Указать что фаски на примитивы ДО Fuse = нормально и рекомендовано. Перечислить хэд/шанк/flange/gear с рекомендованными depth-формулами. Сохранить хард-ограничитель: «The ONLY hard restriction: do not apply Part::Fillet / Part::Chamfer to the final threaded body AFTER the thread Cut» с коротким техническим объяснением про OCCT `[Touched, Invalid]`. |
| **NC-DEV-CORE-025C** | Developer | 2 | Раздел «Realism — chamfers and fillets are the default» | `config/defaults.py` | Новый раздел между Parameter header и Rules list; перечисляет конкретные рекомендации для hex head / cylindrical shank / fuse junction / washer edge / gear root; упоминает, что без явного "without simplifications" LLM ДОЛЖЕН добавить фаски; заканчивается hard rule «chamfers/fillets before Fuse, never after Cut» + ссылкой на canonical example | `TASK CODE: NC-DEV-CORE-025C` / Написать раздел непосредственно перед существующим `### Rules for multi-block code`. Заголовок: `### Realism — chamfers and fillets are the default, not an optional extra`. Список 5 пунктов с конкретными depth-формулами (hex head ~0.08×major_d, shank circles ~0.04×major_d, fuse junction fillet ~0.04×major_d, washer edge ~0.05×flange_h, gear root ~0.15×module_m). Завершить hard rule. |
| **NC-DEV-DOC-009** | Developer | 3 | Обновить sprint plan + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Оглавление sprint plan содержит Sprint 5.9; раздел Sprint 5.9 в каноническом формате; README upgrade до Sprint 5.9; RELEASE_NOTES содержит v1.2 с фото-based diagnosis (реальный vs упрощённый болт) | `TASK CODE: NC-DEV-DOC-009` / По шаблону Sprint 5.8. Версия 1.1 → 1.2. В RELEASE_NOTES включить картинку-based motivation: пользователь показал фото реальных ISO болтов, наш бывший вывод имел голый prism+cylinder без фасок. |
| **NC-PM-REVIEW-013** | PM | 4 | DoD + визуальная проверка | Закрытый checklist | (1) canonical bolt Block 1 содержит два Part::Chamfer (head + shank) (2) parameter header extended: head_ch, shank_ch (3) WARNING заменён на ENCOURAGED (4) раздел «Realism» присутствует до Rules list (5) static verifier зелёный (6) pytest 229+ без регрессий (7) визуальный dog-food: hex-head с видимыми фасками на корневой 3D-модели | — |

**Правила останова Sprint 5.9:** изменение threading / transaction / sandbox → rejected / применение fillet/chamfer к финальному резьбовому телу после Cut → rejected / убрать canonical bolt example целиком → rejected / добавить instruction "simplify" / "no fillets" обратно → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.10 — Thread Position + Pitch Derivation (no hardcoded constants)
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.9 закрыт. Пользователь прогнал 6 dog-food запросов с фотографиями реальных ISO-болтов рядом: «проблема с резьбой во всех случаях, напоминаю ничего не должно быть захардкожено». Визуально: резьба располагается на **верхней** половине шанка (рядом с головой), а нижняя (свободный конец / tip) остаётся гладкой. У реальных ISO-болтов — ровно наоборот. Плюс в canonical example явно захардкожено `major_d = 24.0`, `pitch = 3.0`, `thread_h = min(30.0, 10 * pitch)` — 30-mm cap произвольный.

## Цель

Две правки промпта устраняют оба замечания:

1. **Thread position fix.** В canonical Block 2 LLM получал `helix.Placement` по умолчанию (z=0,0,0), что при шанке `z=[0, shank_h]` клеит резьбу **у головы**, а не у кончика. Новый Block 2 явно вычисляет `thread_z_start = shank_h - thread_h` и ставит `helix.Placement` в эту точку — резьба от tip'а к голове с гладким плечом под головой (как на реальных ISO-болтах).

2. **Выкинуть хардкод.** Единственная hand-set константа в parameter header теперь — `major_d` (берётся из user request, «M24» → 24.0). Остальное полностью деривативно:
   - `pitch = _ISO_COARSE_PITCH[int(major_d)]` из встроенной ISO 261 таблицы (M3–M48)
   - `shank_h = 3.0 * major_d` (можно override из user request)
   - `thread_h = min(shank_h - major_d, 10 * pitch)` (без произвольного 30-mm cap)
   - `thread_z_start = shank_h - thread_h`
   - Все чамферы, flange dimensions, tooth profile — через ratio × major_d

**Non-goals:** изменение threading/transaction/sandbox; capability scope; worker/agent — только правка `DEFAULT_SYSTEM_PROMPT`.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-026A  / Developer / Canonical Block 2 ставит helix на tip (shank_h - thread_h)     / planned
2. NC-DEV-CORE-026B  / Developer / ISO 261 coarse-pitch lookup table вместо хардкода pitch       / planned
3. NC-DEV-CORE-026C  / Developer / Thread_h без произвольного cap, через shank_h и pitch         / planned
4. NC-DEV-DOC-010    / Developer / Sprint 5.10 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES   / planned
5. NC-PM-REVIEW-014  / PM        / DoD + dog-food: резьба на свободном конце шанка              / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-026A** | Developer | 1 | Canonical Block 2 ставит helix на tip шанка | `config/defaults.py` | В Block 2 parameter header — `shank_h = 3.0 * major_d` (должен совпадать с Block 1); `thread_z_start = shank_h - thread_h`; `helix.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, thread_z_start), FreeCAD.Rotation(0, 0, 0))`; профиль triangle смещён с `thread_z_start` в абсолютных координатах; комментарий объясняет layout (head z<0, shank z=[0, shank_h], tip at z=shank_h) | `TASK CODE: NC-DEV-CORE-026A` / Проблема: Фото M24/M30 показывают резьбу у головы, гладкая часть внизу. LLM генерировал helix.Placement по умолчанию (z=0), шанк занимает z=[0, shank_h], и резьба в итоге от z=0 вверх — т.е. у головы. Реальные ISO-болты: резьба от tip'а (свободного конца), гладкое плечо под головой. Решение: (1) в Block 2 header добавить shank_h = 3.0 * major_d (совпадает с Block 1); (2) thread_z_start = shank_h - thread_h; (3) helix.Placement задать в thread_z_start; (4) profile triangle переписать в абсолютные координаты со сдвигом thread_z_start; (5) комментарий объясняет layout. |
| **NC-DEV-CORE-026B** | Developer | 1 | ISO 261 coarse-pitch lookup table | `config/defaults.py` | Parameter header в Block 1 и Block 2 содержит `_ISO_COARSE_PITCH = {3: 0.5, 4: 0.7, ..., 48: 5.0}`; `pitch = _ISO_COARSE_PITCH[int(major_d)]` заменяет хардкод `pitch = 3.0`; комментарий «the ONLY hand-set value» явно маркирует major_d как единственную точку ввода | `TASK CODE: NC-DEV-CORE-026B` / Вместо `pitch = 3.0 # для M24` ввести lookup table для всех ISO 261 coarse series (M3–M48), pitch выводится из major_d. Это делает recipe действительно параметрическим: пользовательское «M30» в промпте → LLM подставляет только major_d=30.0, pitch=3.5 берётся автоматически. |
| **NC-DEV-CORE-026C** | Developer | 2 | Thread_h без произвольного cap | `config/defaults.py` | `thread_h = min(shank_h - major_d, 10 * pitch)` — без литерала 30.0 или иного абсолютного cap'а; комментарий указывает: full shank minus ~1×d shoulder под головой, capped at 10 turns для OCCT reliability | `TASK CODE: NC-DEV-CORE-026C` / Заменить `thread_h = min(30.0, 10 * pitch)` на формулу `min(shank_h - major_d, 10 * pitch)`. Произвольный 30-mm cap удалить — он применим только для средних M-размеров, для M8 слишком много, для M48 слишком мало. Thread length = full shank минус плечо ~1×d под головой, capped at 10 turns. |
| **NC-DEV-DOC-010** | Developer | 3 | Sprint 5.10 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.10 в каноническом формате; README up to 5.10; RELEASE_NOTES содержит v1.3 с описанием thread-position-bug и его фикса | `TASK CODE: NC-DEV-DOC-010` / По шаблону 5.9. Версия 1.2 → 1.3. |
| **NC-PM-REVIEW-014** | PM | 4 | DoD + dog-food | Закрытый checklist | (1) parameter header включает _ISO_COARSE_PITCH и в Block 1, и в Block 2 (2) major_d помечено "the ONLY hand-set value" (3) thread_z_start = shank_h - thread_h присутствует в Block 2 (4) helix.Placement задан в thread_z_start (5) profile triangle в абсолютных координатах (6) нет хардкод 30.0 в thread_h (7) pytest 229+ clean (8) dog-food визуально: резьба НА СВОБОДНОМ КОНЦЕ шанка, гладкое плечо под головой | — |

**Правила останова Sprint 5.10:** изменение threading / transaction / sandbox → rejected / возврат хардкода `pitch = 3.0` без деривации из major_d → rejected / thread_h cap с литералом 30.0 → rejected / перестановка головы на положительный Z без соответствующего фикса helix.Placement → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.11 — Thread Cut Actually Happens: makePipeShell + Volume Assertion
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.10 закрыт — резьба теперь на свободном конце шанка, `pitch` деривативен. Новый dog-food под 5.10: резьба выглядит как "пояски на поверхности шанка", а не реальные V-гроувы. Пользовательский вердикт: «выглядит как будто резьба есть, но она не вырезана из болта». Close-up фото подтверждает: диаметр шанка в резьбовой зоне не уменьшается, гроувы не углублены.

## Цель

Устранить silent-fail `Part::Sweep` doc-object'а на треугольном профиле резьбы. Подтверждённый диагноз из dog-food (Sprint 5.10 logs `11:27`):

- LLM генерировал canonical Block 2 как положено: Helix + ThreadProf (Face) + Part::Sweep (Solid=True, Frenet=True) + Part::Cut.
- Но `Part::Sweep` при такой конфигурации нередко возвращает **degenerate/self-intersecting shell** без валидного объёма.
- Последующий `Part::Cut` на пустом объёме возвращает Base без изменений → шанк выглядит с «поясками» (это edges сохранённого sweep-shell), но диаметр не меняется.

Две правки canonical Block 2:

1. **Wire-level sweep через `helix_wire.makePipeShell([profile_wire], True, True)`.** `Part.makeHelix(pitch, height, radius)` возвращает Wire напрямую; `Part.makePolygon([...])` возвращает closed Wire (не Face); `makePipeShell` — прямой OCCT-вызов, который Part::Sweep оборачивает но иногда портит. FreeCAD-документация явно указывает `makePipeShell` как «simpler and faster than Part::Sweep» (раздел `/PART III — Advanced`).
2. **Sanity assertion перед Cut.** `assert thread_shape.isValid()` и `assert thread_shape.Volume > 0` — если sweep вырождается, ошибка будет видна немедленно, а не проявится как невидимая резьба после «успешного» Cut. Это поднимает категорию ошибки на `validation` с thread-specific feedback (см. Sprint 5.8).

**Non-goals:** изменение threading model / executor / agent / sandbox / capability scope — только правка `DEFAULT_SYSTEM_PROMPT` Block 2.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-027A  / Developer / Canonical Block 2: helix_wire.makePipeShell вместо Part::Sweep       / planned
2. NC-DEV-CORE-027B  / Developer / Assertion thread_shape.isValid() + Volume > 0 перед Cut             / planned
3. NC-DEV-DOC-011    / Developer / Sprint 5.11 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES         / planned
4. NC-PM-REVIEW-015  / PM        / DoD + dog-food: фактический cut (диаметр шанка уменьшается в гроувах) / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-027A** | Developer | 1 | Canonical Block 2: wire-level sweep вместо Part::Sweep | `config/defaults.py` | Block 2 использует `Part.makeHelix(pitch, thread_h, shank_r)` (возвращает Wire) + `Part.makePolygon([...])` (Wire, не Face) + `helix_wire.makePipeShell([profile_wire], True, True)`; результат обёрнут в `Part::Feature "Thread"`; `Part::Cut` принимает `thread` как Tool; комментарий объясняет почему НЕ Part::Sweep | `TASK CODE: NC-DEV-CORE-027A` / Проблема: dog-food 2026-04-18 визуально показал резьбу как «пояски», т.е. Part::Sweep silent-fail'ит на треугольном профиле, Part::Cut на degenerate shell возвращает Base. Решение: (1) заменить `Part::Helix` doc object на `helix_wire = Part.makeHelix(pitch, thread_h, shank_r)` — Wire, не doc object; (2) `helix_wire.Placement` задаётся на Wire, не на doc; (3) profile — `Part.makePolygon([...])` возвращает closed Wire (не Face, т.к. makePipeShell ожидает Wire); (4) anchor point берётся из `helix_wire.Vertexes[0].Point`; (5) `thread_shape = helix_wire.makePipeShell([profile_wire], True, True)` — args makeSolid=True, isFrenet=True; (6) результат обёрнут в Part::Feature "Thread" (не Part::Sweep); (7) Part::Cut принимает thread как Tool. Комментарий объясняет rationale: Part::Sweep doc object frequently produces degenerate solid, makePipeShell — direct OCCT call, более надёжен. |
| **NC-DEV-CORE-027B** | Developer | 1 | Assertion `thread_shape.isValid()` + `Volume > 0` | `config/defaults.py` | Canonical Block 2 содержит `assert thread_shape.isValid(), "thread sweep produced an invalid shape"` и `assert thread_shape.Volume > 0, "thread sweep produced zero volume"` ДО создания Part::Feature; comment объясняет что assertion обеспечивает fail-fast вместо silent-fail | `TASK CODE: NC-DEV-CORE-027B` / Проблема: если thread_shape всё же degenerate (edge case), Part::Cut молча возвращает Base и пользователь видит «поверхностные пояски». Решение: после `helix_wire.makePipeShell(...)` добавить два assert: isValid() и Volume > 0. При срабатывании — AssertionError распространится в executor, будет пойман как runtime error, LLM получит thread-specific feedback (Sprint 5.8) и перегенерирует. Это намного лучше чем silent success. |
| **NC-DEV-DOC-011** | Developer | 2 | Sprint 5.11 в doc/SPRINT_PLANS.md + README + RELEASE_NOTES | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.11 в каноническом формате; версия v1.3 → v1.4 | `TASK CODE: NC-DEV-DOC-011` / По шаблону 5.10. |
| **NC-PM-REVIEW-015** | PM | 3 | DoD + dog-food | Закрытый checklist | (1) Block 2 использует makeHelix и makePipeShell, не Part::Helix + Part::Sweep (2) assertion isValid + Volume > 0 присутствует (3) profile — Wire (makePolygon), не Face (4) pytest clean 229+ (5) dog-food визуально: в резьбовой зоне диаметр шанка УМЕНЬШАЕТСЯ (реальные V-гроувы), а не «пояски» | — |

**Правила останова Sprint 5.11:** изменение threading / transaction / sandbox → rejected / возврат Part::Sweep doc object в canonical Block 2 → rejected (документация показывает что он ненадёжен для thread профилей) / убрать assertion «чтобы не ломалось» → rejected (это главная защита от silent-fail) / ответ без TASK CODE = невалиден.

---

# Sprint 5.12 — Truly Parametric Template: Placeholder Syntax + Parse Instructions + ISO 4014/4017
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.11 закрыт — резьба теперь реально вырезается (`makePipeShell` + volume assertion). Новый раунд dog-food. Пользователь: «Это выглядит как хардкод (… `major_d = 24.0` …) — дефолт должен быть универсальным, давать инструкции LLM для правильного определения параметров. Не упрощай себе работу, задолбал». Фото показывает болт M24 с шайбой — визуально корректно, но в промпте literal `24.0` заставляет LLM копировать его дословно при любом размере резьбы.

## Цель

Превратить canonical bolt+washer recipe из **конкретного M24-примера** в **настоящий параметрический шаблон**. Два механизма:

1. **Placeholder-синтаксис `<MAJOR_D_FROM_REQUEST>`** — синтаксически невалидный Python, LLM не может оставить его в выводе дословно. В отличие от комментариев `# ← the ONLY hand-set value`, которые LLM игнорирует, placeholder **физически не парсится** и принуждает LLM к substitute.
2. **Явный "Parsing rules" preamble** — таблица `user text → extract`, описывающая как из разных форм запроса («болт M24», «M24x80», «M30 ISO», «болт полностью резьбовой») извлечь `major_d`, `shank_h`, `standard`. Плюс ISO 4014/4017 thread-length table (b = 2d+6 / 2d+12 / 2d+25 по бендам `shank_h ≤ 125 / 200 / >200`).

Блоки 1/2/3 теперь начинаются одинаково:
```
major_d = <MAJOR_D_FROM_REQUEST>     # MUST equal the value used in Block 1
shank_h = <SHANK_H_FROM_REQUEST>     # MUST equal the value used in Block 1
standard = <ISO_STANDARD_FROM_REQUEST>   # "ISO4014" (default) or "ISO4017"
```

LLM вынужден подставить `24.0` / `80.0` / `"ISO4014"` — оставить `<...>` = SyntaxError на execute.

Также добавлены:
- **Conditional for thread_h** — ветка ISO4014/ISO4017 через `if standard == "ISO4017"`, с реальной длиной резьбы по ISO table.
- **Conditional for Block 3** — «Emit Block 3 ONLY if the user requested a washer / шайба / flange. Otherwise skip entirely». Раньше шайба генерилась всегда.

**Non-goals:** изменение threading / transaction / sandbox / executor / agent / worker. Только правка `DEFAULT_SYSTEM_PROMPT`.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-028A  / Developer / Placeholder syntax <...> в canonical Block 1/2/3 vs M24-literals   / planned
2. NC-DEV-CORE-028B  / Developer / ISO 4014 / ISO 4017 thread-length table + derivation в Block 2     / planned
3. NC-DEV-CORE-028C  / Developer / Parse instructions preamble: таблица user text → extract           / planned
4. NC-DEV-CORE-028D  / Developer / Conditional Block 3 (washer only if user asked)                   / planned
5. NC-DEV-DOC-012    / Developer / Sprint 5.12 + RELEASE_NOTES v1.5                                   / planned
6. NC-PM-REVIEW-016  / PM        / DoD + dog-food: «болт M48 без шайбы» / «болт M8 полностью резьбовой» / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-028A** | Developer | 1 | Placeholder syntax в canonical Block 1/2/3 | `config/defaults.py` | В Block 1: `major_d = <MAJOR_D_FROM_REQUEST>`, `shank_h = <SHANK_H_FROM_REQUEST>`. В Block 2: те же + `standard = <ISO_STANDARD_FROM_REQUEST>`. В Block 3: `major_d = <MAJOR_D_FROM_REQUEST>`. Комментарий сразу после каждого placeholder показывает пример substitution («example: 24.0 for "M24"»). Нет literal 24.0 в placeholder-lines | `TASK CODE: NC-DEV-CORE-028A` / Проблема: `major_d = 24.0` комментируется как «ONLY hand-set value», LLM pattern-matches и копирует 24.0. Решение: заменить literal на `<MAJOR_D_FROM_REQUEST>` — syntactically invalid → LLM не может оставить. Комментарий `# example: 24.0 for "M24" / 30.0 for "M30"` показывает substitution паттерн без priming на конкретное значение. То же для `shank_h`, и для Block 2 — плюс `standard` для ISO 4014 vs ISO 4017. |
| **NC-DEV-CORE-028B** | Developer | 1 | ISO 4014 / 4017 thread-length table | `config/defaults.py` | Block 2 содержит conditional: `if standard == "ISO4017": _b_nominal = shank_h - 0.5 * major_d; else: _b_nominal = (2*d+6 if shank_h ≤ 125 else 2*d+12 if ≤ 200 else 2*d+25)`. Reliability cap: `thread_h = min(_b_nominal, 10*pitch, shank_h - 0.5*major_d)`. Убран произвольный cap `min(shank_h - major_d, 10 * pitch)` из Sprint 5.10 | `TASK CODE: NC-DEV-CORE-028B` / Sprint 5.10 ввёл `thread_h = min(shank_h - major_d, 10 * pitch)` — это произвольная формула, не ISO. Решение: использовать реальную ISO 4014 табличную формулу с тремя бендами по shank_h (≤125 / ≤200 / >200). Для ISO 4017 fully threaded — shank_h минус плечо 0.5*d. Reliability cap ≤10 turns по-прежнему применяется как min(). |
| **NC-DEV-CORE-028C** | Developer | 2 | Parse instructions preamble | `config/defaults.py` | Перед Block 1 — раздел «How to parse the user's request» с markdown-таблицей: `user text → extract`. 6 строк минимум: M<N>, M<N>x<L>, no length, fully threaded, ISO 4017, fine pitch. Плюс ISO 261 coarse-pitch dict (verbatim). Плюс ISO 4014 thread-length формула | `TASK CODE: NC-DEV-CORE-028C` / Перед canonical layout добавить раздел «#### How to parse the user's request — MANDATORY before emitting code». Markdown-таблица с 6+ правилами, blockquote с ISO_COARSE_PITCH, blockquote с b-формулой. Подчеркнуть: «Do NOT leave <PLACEHOLDER> tokens in the code you emit — they will not parse». |
| **NC-DEV-CORE-028D** | Developer | 2 | Conditional Block 3 | `config/defaults.py` | Заголовок Block 3 дополнен: «Emit Block 3 ONLY if the user requested a washer / шайба / flange. Otherwise skip this block entirely». LLM не пишет Block 3 если в запросе нет упоминания шайбы | `TASK CODE: NC-DEV-CORE-028D` / Раньше canonical example показывал все 3 блока как обязательные. Болт без шайбы получал лишний Washer. Решение: в начале Block 3 markdown-секции явно сказать «Emit ONLY if user asked for washer». |
| **NC-DEV-DOC-012** | Developer | 3 | Sprint 5.12 + RELEASE_NOTES v1.5 | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.12 в каноническом формате; README to 5.12; RELEASE_NOTES содержит v1.5 с объяснением placeholder mechanism | `TASK CODE: NC-DEV-DOC-012` / По шаблону 5.11. Версия 1.4 → 1.5. |
| **NC-PM-REVIEW-016** | PM | 4 | DoD + dog-food | Закрытый checklist | (1) ни одного `= 24.0` в canonical blocks (2) placeholder syntax присутствует в Block 1/2/3 (3) ISO 4014/4017 thread-length conditional (4) ISO 261 pitch dict сохранён (5) «Emit ONLY if» для Block 3 (6) pytest 229+ clean (7) dog-food: «болт M48 без шайбы» → Block 3 пропущен (8) dog-food: «болт M8 полностью резьбовой» → standard=ISO4017, thread_h ≈ shank_h - 0.5*d | — |

**Правила останова Sprint 5.12:** изменение threading / transaction / sandbox → rejected / возврат literal `24.0` в placeholder-позиции → rejected / убрать ISO 4014 thread-length table ради «упрощения» → rejected / оставить Block 3 обязательным (шайба всегда) → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.13 — Naming Contract + defaults.py Bug Fixes (external audit)
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.12 закрыт. Внешний аудит (patches + AUDIT_REPORT от co-author) выявил **дominантную причину 14+ провалов в dog-food 2026-04-18** — cross-block naming drift: LLM в Block 1 пишет `major_d`, а в Block 2 — уже `major_diameter` → `NameError` → `max_retries_exhausted`. Также 7 накопленных мелких багов в `defaults.py`, включая сломанные docstrings вида `""..""` (SyntaxError при копировании LLM).

## Цель

Три одновременных удара по главной проблеме:

1. **Canonical naming table в промпте** (FIX 8) — три таблицы (bolt / gear / wheel) с каноническими именами и «NEVER use» колонкой. LLM получает жёсткий контракт имён, а не «пример, от которого можно отклоняться».
2. **Block-aware `_make_feedback`** (PATCH 1) — сигнатура расширена `block_idx`/`total_blocks`. В Block ≥ 2 при NameError выдаётся thread-specific диагноз: «CRITICAL: fresh namespace, must re-declare with IDENTICAL names». Перечисляет конкретные drift-паттерны: `major_d vs major_diameter / diameter / d`, `shank_h vs shank_length / length / L`, etc.
3. **Observability** (OBS) — `failed_block_idx` в `audit_log("agent_attempt", ...)` при failure. Будущий dog-food анализ сможет grep'ать «сколько % NameError в Block ≥ 2» без парсинга сообщений.

Плюс 7 fix'ов из аудита:
- **FIX 1** (critical): `""Vertical through-hole..""` docstrings в 3 helper-функциях (строки 770–784) → SyntaxError при копировании LLM. Заменены на `#` комментарии.
- **FIX 2**: `Part.RegularPolygon(center, radius, 6)` — hallucinated API, его нет. Заменено на `6 Part.LineSegment + Equal-length + Symmetric constraints`.
- **FIX 3**: `PartDesign::Draft` example с закомментированными Base/Angle/NeutralPlane → создаёт broken feature при recompute. Весь блок завёрнут в comment-template.
- **FIX 4**: `helix.LocalCoord # 0 = right-hand, 1 = left-hand` — неверный коммент; LocalCoord это coordinate-system mode. Для left-hand — отрицательный `Pitch`.
- **FIX 5**: `Draft.move(obj, ...)` с необъявленным `obj` → NameError при LLM-копировании. Завёрнуто в comment-template.
- **FIX 6**: `import copy; shapes=[]; s = original_shape.copy()` — `import copy` здесь лишний, `.copy()` это Shape метод.
- **FIX 7**: `REFUSAL_KEYWORDS = [file, import, url, http, https]` — слишком широкий, ни разу не сработал за 586 событий, при этом блокировал легитимные запросы типа «импорт STEP». Сужён до `[download, fetch url, wget, curl]`.
- **FIX 9**: добавлен anti-pattern для `Part.makeInvoluteGear` (deprecated в FreeCAD 1.x) в секцию `## Blocked`.

**Non-goals:** изменение threading / transaction / sandbox / capability scope / executor / worker. Правки в `config/defaults.py` (промпт) и `core/agent.py` (feedback signature + audit field).

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-029A  / Developer / FIX 1 — broken docstrings → comments (critical)              / planned
2. NC-DEV-CORE-029B  / Developer / FIX 8 — Canonical naming tables (bolt/gear/wheel)           / planned
3. NC-DEV-CORE-029C  / Developer / PATCH 1 — _make_feedback block-aware NameError              / planned
4. NC-DEV-CORE-029D  / Developer / OBS — failed_block_idx в audit_log                          / planned
5. NC-DEV-CORE-029E  / Developer / FIX 2–7, 9 — defaults.py cleanup из аудита                 / planned
6. NC-DEV-CORE-029F  / Developer / Tests: regression + test_make_feedback_nameerror_block_scoping / planned
7. NC-DEV-DOC-013    / Developer / Sprint 5.13 + RELEASE_NOTES v1.6                            / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-029A** | Developer | 1 | FIX 1 — broken `""..""` docstrings → `#` comments | `config/defaults.py` | В helper-функциях `add_hole`, `add_horizontal_hole`, `add_countersunk_hole` (строки 770–784) все `""..""` заменены на `# ..` однострочные комментарии; grep `^    ""` возвращает 0 match'ей | `TASK CODE: NC-DEV-CORE-029A` / Проблема: внутри module-level `DEFAULT_SYSTEM_PROMPT = """..."""` нельзя использовать `"""..."""` для docstring'ов — приходится либо экранировать, либо заменить на `#`. Текущий `""..""` = invalid SyntaxError при exec. Решение: заменить все 3 вхождения на `# ..`. |
| **NC-DEV-CORE-029B** | Developer | 1 | FIX 8 — Canonical naming tables | `config/defaults.py` | После "CRITICAL: every block is a FRESH Python namespace" и ДО "Parameter header" — раздел "### Canonical variable names — MANDATORY contract across all blocks" с 3 таблицами (bolt, gear, wheel); каждая имеет колонки Canonical / Meaning / NEVER use; заключительная строка: "Naming drift between blocks is the #1 cause of regeneration cycles" | `TASK CODE: NC-DEV-CORE-029B` / 14+ провалов в dog-food из-за naming drift (major_d → major_diameter etc.). Решение: жёсткий контракт имён в виде markdown-таблиц. Каждая таблица с колонкой NEVER use перечисляет типовые variants, которые LLM склонен использовать. Три scope'а: bolt/thread, gear, wheel. |
| **NC-DEV-CORE-029C** | Developer | 1 | PATCH 1 — _make_feedback block-aware NameError | `core/agent.py`, `tests/test_agent.py` | `_make_feedback(error, category, block_idx=1, total_blocks=1)` — два новых kwarg'а с дефолтом 1 (backward-compatible); NameError ветка: если `total_blocks > 1 and block_idx > 1` — специализированное сообщение про fresh namespace + конкретный список drift-patterns; call-site в `agent.run` передаёт `block_idx=idx, total_blocks=len(blocks)`; regression-тест `test_make_feedback_nameerror_block_scoping_diagnosis` | `TASK CODE: NC-DEV-CORE-029C` / Текущая NameError ветка говорит «Variable from previous request» или «defined inside if block» — ни то ни другое не соответствует cross-block drift. Решение: расширить сигнатуру, в multi-block fail'е выдавать thread-specific диагноз. |
| **NC-DEV-CORE-029D** | Developer | 1 | OBS — failed_block_idx в audit_log | `core/agent.py` | В agent.run в failure-audit-блоке добавлено поле `"failed_block_idx": failed_block_idx`; переменная `failed_block_idx` инициализируется `None` в начале цикла попыток и устанавливается в `idx` при block failure | `TASK CODE: NC-DEV-CORE-029D` / Для будущего анализа: grep `failed_block_idx >= 2` → процент NameError из-за drift без парсинга сообщений. |
| **NC-DEV-CORE-029E** | Developer | 2 | FIX 2, 3, 4, 5, 6, 7, 9 | `config/defaults.py`, `tests/test_agent.py` | FIX 2: `Part.RegularPolygon` убран, заменён на LineSegment+constraints. FIX 3: PartDesign::Draft example в comment-template. FIX 4: helix.LocalCoord коммент исправлен (coord system, not handedness). FIX 5: Draft.move в comment-template. FIX 6: import copy убран. FIX 7: REFUSAL_KEYWORDS сужен до `[download, fetch url, wget, curl]`; тесты `test_contains_refusal_intent` и `test_run_early_refusal` обновлены. FIX 9: makeInvoluteGear anti-pattern в секции Blocked | `TASK CODE: NC-DEV-CORE-029E` / По patch_02_defaults_fixes.py. |
| **NC-DEV-CORE-029F** | Developer | 3 | Regression + новый тест | `tests/test_agent.py` | 230+ tests clean; `test_make_feedback_nameerror_block_scoping_diagnosis` проверяет Block 2/3 специализацию и fallback для single-block | — |
| **NC-DEV-DOC-013** | Developer | 4 | Sprint 5.13 + RELEASE_NOTES v1.6 | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.13 в каноническом формате; версия v1.5 → v1.6 | — |

**Правила останова Sprint 5.13:** изменение threading / transaction / sandbox → rejected / возврат `""..""` docstrings → rejected / возврат широкого REFUSAL_KEYWORDS без dog-food evidence → rejected / убрать Canonical naming table как «избыточное» → rejected / ответ без TASK CODE = невалиден.

---

# Sprint 5.14 — Wireframe / Math Visualization + Vector 3D Guard
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Sprint 5.13 закрыт (naming contract + 7 defaults.py fixes). Новый dog-food, запрос «Пентеракт / 5D hypercube» — 5 провалов подряд, 4 разных корневых причины. Это новый класс задач — wireframe-визуализация абстрактных объектов, не solid assembly. В текущем промпте нет рецепта для такого класса.

## Цель

Закрыть два конкретных класса провалов, выявленных пентеракт-сессией:

1. **`FreeCAD.Vector(x1, x2, x3, x4, x5)` → TypeError** — LLM трактует «пятимерный куб» буквально и пытается записать 5 координат в 3D-вектор, плюс обращается к несуществующим `.w` / `.t` атрибутам. Промпт не говорит явно, что `FreeCAD.Vector` строго 3D.
2. **Нет рецепта для wireframe-визуализации.** Все canonical примеры в промпте про solids + booleans (bolt, gear, wheel, house). Пентеракт / графы / полиэдры / узлы требуют принципиально другого workflow: точки (маленькие сферы) + рёбра (тонкие цилиндры) + никаких «ячеек» / «граней» (при линейных проекциях nD→3D они коллапсируют в zero-thickness и Validator отклоняет).

Плюс частая невидимая бомба: `math.acos(cos_angle)` без clamp'а на `[-1, 1]` падает на `ValueError: math domain error` когда float noise даёт `1.0000001` — рано или поздно срабатывает даже на болтах.

**Non-goals:** executor / agent / threading не трогаем; новые FreeCAD API не добавляем; capability scope не расширяем.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-030A  / Developer / FreeCAD.Vector is 3D warning в Placement conventions section  / planned
2. NC-DEV-CORE-030B  / Developer / Canonical wireframe recipe (PART VI) + make_edge_cylinder helper / planned
3. NC-DEV-DOC-014    / Developer / Sprint 5.14 + RELEASE_NOTES v1.7                                 / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-030A** | Developer | 1 | `FreeCAD.Vector` is ALWAYS 3D — предупреждение в промпте | `config/defaults.py` | После раздела `## Placement conventions` добавлен блок: `## FreeCAD.Vector is ALWAYS 3D — (x, y, z), three arguments maximum`; перечисление атрибутов (`.x/.y/.z` exist; `.w/.t/.u` do NOT); пример 5D→3D projection через плоские tuples с последующим конструированием Vector | `TASK CODE: NC-DEV-CORE-030A` / Проблема: LLM пишет `FreeCAD.Vector(x1, x2, x3, x4, x5)` → TypeError; обращается к `.w`, `.t` → AttributeError. Решение: одна секция с явным warning и примером корректного паттерна (5D coords в tuples, projection → FreeCAD.Vector). |
| **NC-DEV-CORE-030B** | Developer | 1 | Canonical wireframe recipe (PART VI) | `config/defaults.py` | Новая секция `## PART VI — Wireframe / mathematical visualization (hypercubes, graphs, polytopes, knots, fractals)`; содержит: (a) стратегию «sphere per vertex + cylinder per edge, no faces/cells»; (b) `make_edge_cylinder(doc, start, end, radius, name)` helper с acos clamp'ом и degenerate-edge skip (`if L < 1e-6: return None`); (c) паттерн hypercube через `itertools.product` + edge detection по Hamming distance == 1 | `TASK CODE: NC-DEV-CORE-030B` / Промпт не содержит рецепта для wireframe-визуализации — LLM fallback'ит на Part::Box для «ячеек» 5D, которые при проекции коллапсируют в zero-thickness и Validator отклоняет. Решение: новая секция PART VI (параллельная PART V для fasteners), с helper-функцией для ребра-как-цилиндр (с clamp'ом acos для float noise) и каноническим hypercube pattern. Explicit rule: `DO NOT try to render nD faces/cells — they project degenerately`. |
| **NC-DEV-DOC-014** | Developer | 2 | Sprint 5.14 + RELEASE_NOTES v1.7 | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.14 в каноническом формате; версия v1.6 → v1.7 | — |

**Правила останова Sprint 5.14:** изменение threading / transaction / sandbox → rejected / добавление numpy или других nD-math библиотек в whitelist без benchmark evidence → rejected / убрать acos clamp «для простоты» → rejected (невидимая бомба) / ответ без TASK CODE = невалиден.

---

# Sprint 5.15 — Cross-Platform Tiered API Key Storage
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** FreeCAD 1.1 bundled Python **не содержит** пакет `keyring`. Текущая реализация при отсутствии `keyring` показывала alarming модальный диалог «API key could not be stored securely… You will need to provide the key again next time», и ключ физически никуда не сохранялся. Пользователь был вынужден вводить ключ при каждом запуске FreeCAD.

## Цель

Tiered кросс-платформенное хранилище API-ключа, которое работает без pip-зависимостей, с явным выбором tier'а в UI:

1. **Strategy-классы backend'ов** в новом модуле `neurocad/config/key_storage.py`:
   - `KeyringBackend` — использует pip-пакет `keyring` если установлен
   - `MacOSKeychainBackend` — `security add/find-generic-password` CLI (macOS, без pip)
   - `LinuxSecretToolBackend` — `secret-tool store/lookup` CLI (Linux / GNOME Keyring, без pip)
   - `PlaintextFileBackend` — JSON в config dir с `chmod 0600` (универсальный last-resort)
2. **Orchestration** `save_key(provider, key, tier)` / `load_key(provider)` / `delete_key(provider)` — пробует backend'ы по приоритету safe → universal, возвращает `(backend_name, error)`.
3. **Settings UI** — radio-buttons: Automatic (recommended) / Plaintext file (owner-only) / Session only. Inline status line заменяет модальный warning. Показывает, где ключ сейчас хранится при загрузке диалога.
4. **`_resolve_api_key`** в `registry.py` — precedence: session → env-var `NEUROCAD_API_KEY_<PROVIDER>` → `key_storage.load_key()` (пробует все backend'ы).

**Non-goals:** шифрование plaintext-файла (нет мастер-пароля — security theater); автоматическая установка `keyring` в FreeCAD Python (хрупко, остаётся опциональным шагом в DEV_SETUP.md).

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-031A  / Developer / neurocad/config/key_storage.py — strategy classes + orchestration  / planned
2. NC-DEV-CORE-031B  / Developer / config.py::save_api_key / load_api_key / delete_api_key — wire     / planned
3. NC-DEV-CORE-031C  / Developer / registry.py::_resolve_api_key — использует key_storage.load_key   / planned
4. NC-DEV-UI-031D    / Developer / settings.py — radio, inline status, remove alarming modal          / planned
5. NC-DEV-TEST-031E  / Developer / tests/test_key_storage.py (22 теста) + update test_settings/config/adapters / planned
6. NC-DEV-DOC-015    / Developer / Sprint 5.15 + README + RELEASE_NOTES v1.8                          / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-031A** | Developer | 1 | Strategy-классы backend'ов в новом `neurocad/config/key_storage.py` | `config/key_storage.py` (новый файл) | Базовый `class KeyStorageBackend` с 4 методами (`is_available`, `save`, `load`, `delete`); concrete backend'ы: `KeyringBackend`, `MacOSKeychainBackend`, `LinuxSecretToolBackend`, `PlaintextFileBackend`; module-level функции `save_key(provider, key, tier)` / `load_key(provider)` / `delete_key(provider)` / `available_backends()` / `_all_backends()`; константы `TIER_AUTOMATIC / TIER_SESSION / TIER_PLAINTEXT`; все OS-native backend'ы используют `subprocess.run`, не требуют pip-deps | `TASK CODE: NC-DEV-CORE-031A` / Создать новый модуль `neurocad/config/key_storage.py` с иерархией backend'ов. Ключ никогда не логируется. PlaintextFileBackend использует atomic write (tmp + rename) и `os.chmod(path, 0o600)` на Unix. macOS backend использует `security add-generic-password -U` для update-if-exists. Linux backend передаёт secret через stdin (`secret-tool store` reads from stdin). `save_key` перебирает backend'ы до первого успеха, возвращает `(backend_name, error_or_None)`. Никогда не raises. |
| **NC-DEV-CORE-031B** | Developer | 1 | Wire `config.py::save_api_key` / `load_api_key` / `delete_api_key` на key_storage | `config/config.py`, `tests/test_config.py` | `save_api_key(provider, key, tier=TIER_AUTOMATIC) -> (backend_name, error)` — delegates to `key_storage.save_key`, не raises; новые `load_api_key(provider) -> (key, backend_name)` и `delete_api_key(provider) -> list[backend_name]`; удалён `import keyring` из `config.py`; тест `test_save_api_key_delegates_to_key_storage` + `test_save_api_key_never_raises_when_all_backends_fail` | `TASK CODE: NC-DEV-CORE-031B` / Удалить `try: import keyring except ImportError: keyring = None` из `config.py`. Добавить `from neurocad.config import key_storage`. Переписать `save_api_key` чтобы вызывал `key_storage.save_key(provider, key, tier=tier)`. Сигнатура `save_api_key(provider, key, tier=key_storage.TIER_AUTOMATIC) -> tuple[str, str \| None]` — backward-incompatible (раньше raise'ил RuntimeError, теперь возвращает tuple). Updated callers: settings.py. |
| **NC-DEV-CORE-031C** | Developer | 1 | `registry.py::_resolve_api_key` использует `key_storage.load_key` | `llm/registry.py`, `tests/test_adapters.py` | `_resolve_api_key` precedence: session → env-var `NEUROCAD_API_KEY_<PROVIDER>` → `key_storage.load_key(provider)`; сообщение об ошибке включает `available_backends()` names; тесты обновлены (`test_api_key_precedence_order` patches `key_storage.load_key`, не `keyring`) | `TASK CODE: NC-DEV-CORE-031C` / Удалить `import keyring` из registry.py. Переписать `_resolve_api_key` используя `key_storage.load_key`. ValueError message перечисляет available backends вместо «install the `keyring` package». |
| **NC-DEV-UI-031D** | Developer | 2 | Settings UI — radio, inline status, remove modal | `ui/settings.py`, `tests/test_settings.py` | Три RadioButton: Automatic / Plaintext file / Session only в QButtonGroup; `_selected_tier()` method; `_storage_status: QLabel` с RichText; `_set_status(html, color)` helper; `_on_save` показывает inline result (имя backend'а) вместо modal; `_load_current()` отображает текущий backend storage ключа для выбранного provider'а; `_on_provider_changed` обновляет storage status; все `QMessageBox.warning/information/critical` в save/use_once пути удалены | `TASK CODE: NC-DEV-UI-031D` / Переписать `ui/settings.py`. Radio в auth_layout ниже API Key поля. На Save: не всплывает модал, только inline `_storage_status.setText(...)` с цветовыми кодами (green = success, orange = plaintext warning, red = error). Settings dialog при открытии вызывает `key_storage.load_key(provider)` и показывает «🔑 Key currently stored in: <backend_name>». Qt.RichText через `from .compat import Qt`. |
| **NC-DEV-TEST-031E** | Developer | 3 | Tests — key_storage (22 теста) + updated settings/config/adapters | `tests/test_key_storage.py` (новый), `tests/test_settings.py` (переписан), `tests/test_config.py`, `tests/test_adapters.py` | `test_key_storage.py`: plaintext roundtrip / multi-provider / overwrite / chmod 0600 / delete / corrupted file recovery / macOS save-load-delete с mock subprocess / Linux save via stdin / session tier / automatic fallback chain / all-backends-fail / load precedence / delete_key purges all backends; `test_settings.py` переписан под новый UI (radio buttons, inline status, no modal); `test_config.py::test_save_api_key_delegates_to_key_storage` + `test_save_api_key_never_raises_when_all_backends_fail`; `test_adapters.py` патчит `key_storage.load_key` вместо `keyring` | `TASK CODE: NC-DEV-TEST-031E` / 22 теста в test_key_storage.py (по одному на каждую ветку backend'а + orchestration). test_settings.py: helper `_mock_ui(dialog, api_key, tier)` + 12 тестов покрытия всех tier веток. test_adapters.py: `patch("neurocad.llm.registry.key_storage.load_key")`. |
| **NC-DEV-DOC-015** | Developer | 4 | Sprint 5.15 + README + RELEASE_NOTES v1.8 | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.15 в каноническом формате; версия 1.7 → 1.8; README upgrade; RELEASE_NOTES содержит описание tier'ов и миграцию | — |

**Правила останова Sprint 5.15:** изменение threading / transaction / sandbox / executor → rejected / добавление pip зависимости `keyring` в `pyproject.toml` как обязательной (она mandatory для dev, но не для runtime) → rejected / шифрование plaintext файла без мастер-пароля → rejected (security theater) / возврат `save_api_key` raises RuntimeError → rejected (теперь возвращает tuple) / ответ без TASK CODE = невалиден.

---

# Sprint 5.16 — Revolution Profile Diagnostics + No-Code Retry + Bevel Helper
**Нед. 18 · Python 3.11 · FreeCAD 1.1**
**Статус:** completed (2026‑04‑18)

**Предусловие:** Dog-food на запросе «Сделай ось колёсной пары РУ1-Ш по ГОСТ 33200-2014» (сложный ступенчатый вал + галтели R=20/25/40 + центровые отверстия) выявил три узкие дыры:

1. **Shape-invalid feedback не покрывает Revolution profile self-intersection.** Ошибка `Validation failed for WheelAxisRevolution: Shape is invalid` получала generic boolean/sweep диагноз из Sprint 5.6, хотя корневая причина была в self-intersecting 2D-профиле.
2. **`no_code_generated` — фатально на первой же попытке.** После shape-invalid LLM вернул prose вместо нового кода; `extract_code_blocks` дал `[]`; агент немедленно вернул `AgentResult(no_code_generated)` БЕЗ retry. При MAX_RETRIES=3 у LLM должен был быть второй шанс.
3. **Hand-rolled arc approximation — типовой источник self-intersection.** LLM посчитал `center_z = z_start + R, center_r = r_start + R` для галтели от (205, 65) до (235, 82.5) с R=20 — при `t=0` получил point (205, 85) вместо (205, 65), опорная линия из (205, 65) не стыкуется с началом дуги → self-intersecting polygon → invalid revolution.

## Цель

Три узкие правки, все prompt/feedback-уровневые:

1. **Revolution-specific ветка в `_make_feedback('shape is invalid')`** — если `_re_search_invalid_name(error)` даёт name, содержащее `revolution / revolved / axis / profile / wire / ring`, выдаём 5-пунктовый чеклист: `wire.isValid()`, closed polygon (первая вершина == последняя), все точки на одной стороне оси (radius ≥ 0), проверка стыка arc-start = previous-segment-end, избегание точки exactly at axis. Fallback на старый boolean-диагноз для всех остальных имён.

2. **`no_code_generated` теперь retriable.** В `agent.run`, при `not blocks`: добавить stronger feedback в history, `audit_log("agent_attempt", ..., error_category="no_code")`, и — если `attempts < MAX_RETRIES` — `continue` вместо `return`. Stronger feedback: «The ONLY valid response is a fenced ```python``` block. Do NOT apologize, do NOT describe the problem… re-emit the complete code».

3. **`fillet_arc_points(r_start, z_start, r_end, z_end, n_pts=7)` helper в defaults.py PART III.** Линейный bevel interpolation — never self-intersects. Явная инструкция в prompt: «when in doubt about tangent-fillet geometry, USE THIS HELPER; true tangent-fillet requires control points that satisfy both tangencies — if R doesn't fit the step, any hand-rolled arc will under/over-shoot».

**Non-goals:** executor / agent threading / transaction / sandbox не трогаем. Алгоритмы правильной геометрии tangent-fillet (с SLERP / двумя tangency constraints) откладываются.

**Rolling Plan (старт)**
```
1. NC-DEV-CORE-032A  / Developer / Revolution ветка в _make_feedback(shape invalid)         / planned
2. NC-DEV-CORE-032B  / Developer / no_code_generated retries + stronger feedback            / planned
3. NC-DEV-CORE-032C  / Developer / fillet_arc_points helper в defaults.py PART III          / planned
4. NC-DEV-TEST-032D  / Developer / 3 новых теста в test_agent.py                            / planned
5. NC-DEV-DOC-016    / Developer / Sprint 5.16 + RELEASE_NOTES v1.9                         / planned
```

---

## Задачи

| Task Code | Роль | Фаза | Задача | Артефакт | Acceptance | Промт |
|---|---|---|---|---|---|---|
| **NC-DEV-CORE-032A** | Developer | 1 | Revolution-specific ветка в `_make_feedback('shape is invalid')` | `core/agent.py` | Если `_re_search_invalid_name(error)` содержит token из `{revolution, revolved, axis, profile, wire, ring}` — выдать 5-пунктовый чеклист с `isValid()`, closed polygon, all points on one side of axis, arc-segment stitching check, avoid axis-touching; иначе — fallback на существующий boolean/sweep message; test `test_make_feedback_shape_invalid_revolution_specific` | `TASK CODE: NC-DEV-CORE-032A` / Расширить validation-ветку `shape is invalid` на имена Revolution/Profile/Wire/Ring. Использовать helper `_re_search_invalid_name` из Sprint 5.8. |
| **NC-DEV-CORE-032B** | Developer | 1 | `no_code_generated` retriable + stronger feedback | `core/agent.py`, `tests/test_agent.py` | `if not blocks:` теперь добавляет feedback про "ONLY valid response is a fenced block", пишет audit_attempt с category=no_code, и если `attempts < MAX_RETRIES` — `continue`; только на последней попытке возвращает `AgentResult(no_code_generated)`; тест `test_run_no_code_generated_retries` подтверждает `mock_adapter.complete.call_count == 3`; тест `test_run_no_code_generated_feedback_is_stronger` проверяет «fenced»/«apologize» в feedback | `TASK CODE: NC-DEV-CORE-032B` / В agent.run ветка `if not blocks:`: убрать немедленный return; добавить history feedback "The ONLY valid response is a fenced python block. Do NOT apologize, do NOT describe the problem, re-emit the complete code"; audit_log("agent_attempt", ...error_category=no_code); `continue` если `attempts < MAX_RETRIES`; в последней попытке — финальный audit_log("agent_error", error_type=no_code_generated) + return. |
| **NC-DEV-CORE-032C** | Developer | 2 | `fillet_arc_points` bevel helper | `config/defaults.py` | После section `### Part::Revolution` добавлен раздел `### Fillet/galtel transitions in Revolution profiles — use the SAFE BEVEL HELPER` с функцией `fillet_arc_points(r_start, z_start, r_end, z_end, n_pts=7)` (линейная интерполяция через `#` comment, НЕ triple-quote docstring — иначе ломает внешний DEFAULT_SYSTEM_PROMPT); usage-example для ступенчатого вала с `wire.isValid()` assertion; комментарий «if true tangent-fillet with specific R required — user must supply control points» | `TASK CODE: NC-DEV-CORE-032C` / Добавить helper в PART III после existing Revolution recipe. Использовать `#` comments, НЕ `"""..."""` — последний ломает внешний DEFAULT_SYSTEM_PROMPT (та же ошибка что FIX 1 в Sprint 5.13). Usage-example демонстрирует ступенчатый вал, включая mirror для симметрии и wire.isValid() ассерцию. |
| **NC-DEV-TEST-032D** | Developer | 3 | Tests | `tests/test_agent.py` | `test_make_feedback_shape_invalid_revolution_specific` (Revolution vs boolean fallback), `test_run_no_code_generated_retries` (3 attempts, not 1), `test_run_no_code_generated_feedback_is_stronger` (feedback-text check) — все зелёные | — |
| **NC-DEV-DOC-016** | Developer | 4 | Sprint 5.16 + RELEASE_NOTES v1.9 | `doc/SPRINT_PLANS.md`, `README.md`, `doc/RELEASE_NOTES.md` | Раздел Sprint 5.16 в каноническом формате; версия 1.8 → 1.9 | — |

**Правила останова Sprint 5.16:** изменение threading / transaction / sandbox → rejected / `"""..."""` внутри `DEFAULT_SYSTEM_PROMPT` (повтор SyntaxError-бага FIX 1) → rejected / возврат `no_code_generated` как фатальной немедленно → rejected / помпезные «Claude вычислит tangent-fillet через SLERP» добавки без benchmark → отложено / ответ без TASK CODE = невалиден.

---

**Deferred (not in this sprint):**
- Блокировка `ViewObject` в executor — низкий приоритет, ViewObject не опасен; добавить лишь warning что в headless-контексте modification не persist.
- Audit field `failed_block_idx` уже добавлен в Sprint 5.13 — можно прогнать статистику за сутки после следующего dog-food, чтобы количественно подтвердить снижение naming drift.

---

## Сводная таблица: что изменилось от v0.1 → v1.7

| Компонент | v0.1 (оригинал) | v0.8 (финал) |
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
| Transaction name | `"CADCopilot"` (расхождение) | `"NeuroCAD"` везде |
| Input guard | нет | `_set_busy(True/False)` в panel |
| Exporter | `exportStep(str(path))` без guard | + `Part.OCCError` catch + null shape filter |
| Benchmark evidence | не определено | ручной FreeCAD benchmark принят как baseline; Sprint 4 переводит его в release-grade safety gate |
| Recovery after Sprint 4 | не определено | поднят в `Sprint 4.1` как merged-scope из утраченных Sprint 5/6 + отдельный bootstrap/installability gate |
| Math в namespace | отсутствует; prompt запрещал import | `math` pre-injected в `_build_namespace()`; prompt явно указывает на pre-loaded math (Sprint 5.5) |
| Тригонометрия | `App.cos()` → runtime error → 3 ретрая | `math.cos()` без import → работает; `_categorize_error` ловит attribute errors → fast-fail (Sprint 5.5) |
| Context объектов | только `volume_mm3` + `placement` | `ObjectInfo.properties` с L/W/H/Radius; `to_prompt_str()` выводит размеры (Sprint 5.5) |
| Placement conventions | не описаны в prompt | `Box.Placement` = угол, не центр; `Cylinder/Cone` = центр основания; примеры в system prompt (Sprint 5.5) |
| Stop button retry | `Cancelled` → 3 retries + `max_retries_exhausted` | fast-exit после 1 attempt; audit `cancelled_by_user` (Sprint 5.6) |
| Handoff timeout | хардкод 15 s + retry того же тяжёлого кода | `exec_handoff_timeout_s` в конфиге (default 60 s); fast-exit + actionable feedback «Split the script» (Sprint 5.6) |
| IndexError feedback | generic «Execution failed» | конкретный hint про `edge.Vertexes[1]` на круговых рёбрах, `shape.Faces[0]` на wire/compound (Sprint 5.6) |
| Invalid shape feedback | `Shape is invalid` смешан с `Shape is null` | отдельная ветка с `shape.fix()` / `removeSplitter()` / `isValid()` (Sprint 5.6) |
| Prompt recipe корректность | `Part::LinearPattern` рекомендовался как «always reliable» + параллельно помечен как «не существует» | Python loop + `Part.makeCompound` в единственном recipe; static verifier защищает от регрессий (Sprint 5.7) |
| Output format | жёсткое «no markdown fences» → LLM пишет 9000-символьный монолит | simple → unfenced, complex → 2–3 fenced ```python``` блока (Sprint 5.7) |
| Multi-block protocol | отсутствует в промпте, хотя executor это поддерживал с 5.4 | явный canonical layout bolt+thread+washer в три блока, правила для `doc.getObject()` между блоками (Sprint 5.7) |
| Static recipe verifier | нет — ошибки в промпте ловятся только dog-food-сессией | `tests/test_prompt_recipe.py` проверяет, что каждый тип в `doc.addObject(...)` whitelisted (Sprint 5.7) |
| Multi-block scoping | «variables do NOT persist» одной строкой; LLM игнорировал | явный CRITICAL-блок + Parameter header в каждом блоке + параметрический canonical bolt (major_d/pitch/minor_d, ISO 261 pitch table) (Sprint 5.8) |
| Bolt recipe | хардкод M24-specific: `shank_r = 12.0; Height = 15.0; ...` | полностью параметризован: `shank_r = major_d/2; head_h = 0.6*major_d; head_key = 1.5*major_d; minor_d = major_d - 1.226*pitch; thread_h = min(30, 10*pitch)` — работает для M8…M48 (Sprint 5.8) |
| Gear recipe | `PartDesign::InvoluteGear` — не существует в stock FreeCAD 1.1 | Part WB approximation: Part::Revolution disc + Part::Box tooth + Python loop + makeCompound + Part::MultiFuse; feedback направляет LLM на этот паттерн (Sprint 5.8) |
| Touched/Invalid feedback | одна ветка «убери Fillet», даже когда fillet не задействован | thread-specific чеклист (sweep.Shape.isValid(), helix fits shank, ≤10 turns, Frenet=True, Cut direct) + fallback на fillet-ветку для не-thread объектов (Sprint 5.8) |
| Canonical bolt reality | голый prism+cylinder fuse, LLM копировал буквально → результат выглядел «сильно упрощённым» без фасок | Block 1 содержит `Part::Chamfer` на hex head (все рёбра, 0.08×major_d) + shank (только круговые рёбра, 0.04×major_d = thread-entry chamfer) (Sprint 5.9) |
| Fillet/Chamfer framing | WARNING «DO NOT apply fillets to final body» → LLM обобщал до «никогда не fillet'ить» | Раздел «Realism — chamfers are the default» + переформулировка warning в ENCOURAGED с конкретными depth-формулами для head/shank/washer/gear (Sprint 5.9) |
| Thread position | helix.Placement по умолчанию (z=0) → резьба у головы, гладко на свободном конце | `thread_z_start = shank_h - thread_h`, `helix.Placement` явно в tip'овой позиции, profile triangle в абсолютных координатах (Sprint 5.10) |
| Pitch | захардкожено `pitch = 3.0` для M24 | `_ISO_COARSE_PITCH = {3: 0.5, ..., 48: 5.0}` — pitch выводится из major_d автоматически (Sprint 5.10) |
| Thread_h cap | литерал 30.0 — произвольное ограничение | `min(shank_h - major_d, 10 * pitch)` — full shank минус плечо под головой, capped by reliability limit (Sprint 5.10) |
| major_d семантика | параметр с M24-specific комментом | единственная hand-set константа, явно помеченная «from user request `M<N>` → N» (Sprint 5.10) |
| Thread sweep reliability | Part::Sweep doc object silent-fail на треугольном профиле → Cut на degenerate shell → резьба видна как «пояски» без гроувов | wire-level `helix_wire.makePipeShell([profile_wire], True, True)` + assertion `isValid()` и `Volume > 0` перед Cut (Sprint 5.11) |
| Thread profile type | `Part.Face(Part.makePolygon(...))` для Part::Sweep Sections | `Part.makePolygon(...)` closed Wire для makePipeShell (не Face) (Sprint 5.11) |
| major_d как example-literal | `major_d = 24.0` с комментарием "the ONLY hand-set value" → LLM копирует 24.0 дословно | `major_d = <MAJOR_D_FROM_REQUEST>` placeholder syntax (syntactically invalid → LLM вынужден substitute) (Sprint 5.12) |
| Parse instructions | неявные / комментарии | явный раздел «How to parse the user's request» с markdown-таблицей user text → extract (Sprint 5.12) |
| Thread length derivation | `thread_h = min(shank_h - major_d, 10 * pitch)` (произвольная формула) | ISO 4014 table: `2d+6 / 2d+12 / 2d+25` по бендам shank_h; ISO 4017 ветка для fully threaded (Sprint 5.12) |
| Block 3 (washer) | всегда эмитится | conditional: «Emit ONLY if user requested a washer / шайба» (Sprint 5.12) |
| Cross-block naming drift | нет явного контракта → 14+ NameError/день в Block ≥ 2 | Canonical naming table (bolt/gear/wheel) с колонкой «NEVER use»; block-aware `_make_feedback` специализированный диагноз при NameError в Block ≥ 2 (Sprint 5.13) |
| Broken docstrings в helpers | `""Vertical through-hole..""` → SyntaxError при LLM-копировании | заменены на `# ..` comments (Sprint 5.13) |
| `Part.RegularPolygon` в Sketcher рекомендациях | hallucinated API, не существует | заменено на `LineSegment + Equal-length + Symmetric constraints` (Sprint 5.13) |
| `PartDesign::Draft` incomplete example | `addObject("PartDesign::Draft")` без Base/Angle/NeutralPlane → broken feature | весь блок в comment-template (Sprint 5.13) |
| `helix.LocalCoord` коммент | "0=right-hand, 1=left-hand" — неверно | coordinate-system mode; для left-hand — отрицательный Pitch (Sprint 5.13) |
| `Draft.move(obj, ...)` с undefined `obj` | копируется LLM → NameError | comment-template с `some_obj` placeholder (Sprint 5.13) |
| REFUSAL_KEYWORDS over-broad | `[file, import, url, http, https]` — ни разу не сработал за 586 событий, но мог блокировать легитимные запросы | `[download, fetch url, wget, curl]` — только явные fetch-from-network (Sprint 5.13) |
| Audit observability | `failed_block_idx` отсутствовал | добавлен в `audit_log("agent_attempt", ...)` при failure (Sprint 5.13) |
| FreeCAD.Vector dimensionality | не задокументировано → LLM пишет `Vector(x1..x5)` на nD-запросах | явный warning «ALWAYS 3D» + пример nD→3D projection через tuples (Sprint 5.14) |
| Wireframe / math viz recipe | отсутствовал → LLM fallback на Part::Box → degenerate solids на nD projection | canonical PART VI: sphere-per-vertex + cylinder-per-edge + `make_edge_cylinder` helper с acos clamp и degenerate-edge skip (Sprint 5.14) |
| `math.acos` float noise | без clamp'а → `ValueError: math domain error` на edge cases (параллельные векторы) | обязательный clamp `max(-1.0, min(1.0, cos_a))` в canonical helper (Sprint 5.14) |
| API key storage | только `keyring` pip, при его отсутствии (FreeCAD bundle) модал «can't save» + ключ пропадает | tiered cross-platform: keyring → macOS `security` CLI → Linux `secret-tool` → plaintext-0600 file; radio-buttons в Settings; inline status вместо модала (Sprint 5.15) |
| Settings UX | alarming modal при отсутствии keyring, без выбора | Settings dialog: Automatic / Plaintext file / Session only + показывает текущий backend storage ключа при открытии (Sprint 5.15) |
| `save_api_key` API | raises `RuntimeError` если keyring missing | returns `(backend_name, error_or_None)` — никогда не raises, UI показывает результат inline (Sprint 5.15) |
| Shape-invalid feedback для Revolution | общий boolean/sweep диагноз не про self-intersecting 2D-профиль | Revolution-specific ветка: 5 пунктов про closed wire / one-side-of-axis / arc stitching / avoid-axis-touch (Sprint 5.16) |
| `no_code_generated` | фатально на первой же попытке — ни одного retry | retriable: stronger feedback про «fenced block only, re-emit complete code»; retry до MAX_RETRIES (Sprint 5.16) |
| Hand-rolled arc approximation | LLM кривит center (например `center_r = r_start + R` — самое наивное и самое частое) → self-intersection | `fillet_arc_points(r_start, z_start, r_end, z_end, n_pts=7)` linear-bevel helper в defaults.py; never self-intersects (Sprint 5.16) |
