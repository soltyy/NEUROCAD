# NeuroCad

AI‑powered CAD assistant for FreeCAD.

**This project is under active development.**  

For installation and development instructions, see [DEV_SETUP.md](DEV_SETUP.md).  
For architecture and sprint plans, see the `doc/` directory.

Current implementation status (Sprint 5.4, April 2026):
- LLM integration (OpenAI, Anthropic) with configurable provider, model, and API key management
- Multi‑step Python code execution from LLM responses with rollback on error
- Secure API key storage via system keyring, environment variables, or session‑only use
- Structured audit logging (JSONL) with redaction, rotation, and config toggle
- Modern UI with Claude‑style layout, adaptive input, and panel‑side diagnostics
- Full geometry generation, validation, and export (STEP/STL)
- Settings dialog for provider configuration and persistent vs. session‑only auth

## License

MIT
