---
date: 2026-03-16
topic: coaching-heartbeat
---

# Coaching Heartbeat

## What We're Building

Replace the current system-metrics heartbeat with an adaptive coaching check-in. Each message is a Claude-generated response based on Ryan's actual day — not a template, not a canned nudge. It reads the daily log, weekly protocol (including workout schedule), and recent check-in history, then says whatever's actually useful right now.

## Why This Approach

The current heartbeat sends uptime/memory/job stats hourly. Ryan ignores it because it's not actionable. A coaching heartbeat that adapts to the day and feels like a real person is worth reading.

## Key Decisions

### Tone: Honest and human, not performative
- No cheerleader ("Great job!"), no drill sergeant ("You failed to...")
- Talks like a friend who knows Ryan well
- Doesn't repeat things he already committed to
- Short when the day is going well, honest (not preachy) when things slip
- Reads the room — supportive when Ryan's having a rough day, direct when he's in a good headspace

### Frequency: Adaptive, 7am–9pm
- Morning kickoff (~7am) and evening wind-down (~8:30–9pm) always fire
- Midday/afternoon check-ins fire by default, skipped if Ryan's been active with bot in last hour
- Extra check-ins trigger when: habits unchecked past usual time, no meals logged by afternoon, low task completion
- Never more than 1 message per hour
- Mute command: Ryan can say "mute for 2 hours" (or similar) to pause check-ins during deep focus

### Context the coach reads each time
- Today's daily log (tasks, habits, meals, weight, mood, metrics)
- Current weekly protocol (workout schedule, training goals, weekly targets)
- Recent check-in history (last 3-4 messages sent, so it doesn't repeat itself)
- Time of day (morning vs evening framing)
- Mute status

### Interactive
- Replies to a coaching check-in route back to Claude for a quick back-and-forth
- The coach has the same context as the check-in that triggered the reply

### Conversational check-ins (not isolated pings)
- Check-ins are part of the main conversation history — not separate one-off messages
- When Ryan replies to a check-in, it's a normal conversation turn with full context
- The coach remembers what it said earlier today and what Ryan replied
- This means the coaching heartbeat injects messages into the existing ConversationState, not a sidecar
- Check-in history persists across restarts (already handled by conversation_history.json)

### Implementation approach
- Each heartbeat = a Claude call via the **CLI backend** (`claude -p`) using the Max subscription ($0/token)
- Coaching system prompt lives in a separate file (`coaching_prompt.md`) for easy iteration on tone/rules
- Adaptive scheduler replaces the fixed-interval loop
- Mute state stored in memory (resets on restart, which is fine)
- Workout schedule comes from the weekly protocol file (no separate file needed)
- System health metrics move to /health command only (not in coaching messages)
- The coach assembles context the same way the main bot does (via v2 context assembler) so it sees daily log, weekly protocol, etc.

### What the old heartbeat becomes
- System health (uptime, memory, jobs) stays available via /health command
- The hourly Telegram ping is fully replaced by the coaching heartbeat
- Heartbeat file for Docker health check continues to update (no user-facing change)

## Resolved Questions
- **Coaching prompt location:** Separate file (`coaching_prompt.md`) — easy to iterate without code changes
- **Cost control:** Uses CLI backend with Max subscription, $0/token. No per-call cost concern.
- **Check-in history:** Persisted as part of the main conversation history. Coach and bot share context.

## Next Steps
→ `/workflows:plan` for implementation details
