<!-- Thanks for contributing to pace-tutor! 💛 Keep PRs focused — one subject / one fix. -->

**What & why**
<!-- e.g. "Add Music theory backbone (EN), 6 concepts" -->

**Type**
- [ ] 📚 New subject / backbone (data only)
- [ ] ❓ Quiz questions
- [ ] 🌍 Translation / wording
- [ ] 🐛 Bug fix
- [ ] ✨ Feature / engine / UI

**Checks** (deterministic — no LLM/network needed)
- [ ] `verify_*.py` pass (at least `verify_backbone.py`)
- [ ] `cd ui && npm run build` succeeds (if you touched the UI)
- [ ] New backbone loads: `Backbone.from_jsons(sorted(glob.glob("data/backbone_*.json")))`

**Notes for reviewers** (optional)
<!-- For quality changes (extraction/structure), before/after eval_*.py numbers are 🔥 -->
