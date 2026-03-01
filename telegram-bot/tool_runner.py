#!/usr/bin/env python3
"""
CLI bridge for BeStupid bot tools.

Called by Claude Code CLI during the main conversation loop:
    python tool_runner.py <tool_name> '<json_args>' [chat_id]

Invokes execute_tool() from tools.py and prints the result to stdout.
"""

import asyncio
import json
import sys


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <tool_name> '<json_args>' [chat_id]", file=sys.stderr)
        sys.exit(1)

    tool_name = sys.argv[1]
    try:
        tool_args = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(f"Invalid JSON args: {e}", file=sys.stderr)
        sys.exit(1)

    chat_id = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    from tools import execute_tool

    result = asyncio.run(execute_tool(tool_name, tool_args, chat_id=chat_id))
    print(result)


if __name__ == "__main__":
    main()
