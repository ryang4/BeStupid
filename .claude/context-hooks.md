# Context Hooks for AI Assistant

When Ryan starts a new conversation, run these to get oriented quickly:

## Quick Context Check
```bash
python3 scripts/context_briefing.py
```

This shows:
- Active goals (3 main projects: Startup, Half Ironman, ML Engineering)
- Current daily habits (simplified to 2: AI automation + yoga)
- Today's plan and todos
- Memory system stats

## Additional Context Commands

### View today's log
```bash
cat content/logs/$(date +%Y-%m-%d).md
```

### Check recent conversation topics
```bash
python scripts/memory.py search "[topic]"
```

### View current weekly protocol
```bash
ls -t content/config/protocol_*.md | head -1 | xargs cat
```

## Key Context Notes

**Ryan's Goals:**
1. **Startup** (Priority 1): Daily planning product → First $1 by May 2026
   - Currently dogfooding own system
   - Blockers: LinkedIn integration, network mapping

2. **Half Ironman** (Priority 1): Race October 2026
   - Current: Beginner swim/bike, strong running base
   - Weekly targets: 800-1000m swim, 60-90min bike, 8-12mi run, 2x strength

3. **ML Engineering** (Priority 2): Ship ML feature by Dec 2026
   - Learning through building personal tools
   - Weekly: 10-15 learning hours

**Daily Habits (Simplified):**
- Build and share one AI automation (combines learning + content + startup work)
- 10 min yoga (recovery for training)

**Recent System Changes:**
- Simplified from 8 habits to 2 (Jan 29)
- Created end-of-day reminder system (9 PM Telegram)
- Still working on startup (not pivoted to AI automations yet)

**Memory System Usage:**
```bash
python scripts/memory.py [command]
# people add/get/update/list/delete
# projects add/get/update/list
# decisions add/list/revoke
# commitments add/list/complete/cancel
# search "query"
```

**Important Files:**
- Daily logs: `content/logs/YYYY-MM-DD.md`
- Projects: `content/projects/*.md`
- Habits config: `content/config/habits.md`
- Weekly protocol: `content/config/protocol_*.md`
- Memory: `memory/*.json`
