# zouj-ai-sdlc demo: a blocked early edit, a human approval, then TDD.
# Record it with vhs (https://github.com/charmbracelet/vhs): `vhs docs/demo/demo.tape` writes docs/demo/demo.gif.
# It drives a live Claude Code session, so each run differs; see docs/demo/README.md before recording.

Output docs/demo/demo.gif

Require git
Require claude

Set Shell "bash"
Set FontSize 16
Set Width 1280
Set Height 760
Set Padding 20
Set TypingSpeed 40ms
Set WaitTimeout 900s
Set PlaybackSpeed 1.0
Set Framerate 20

# --- off camera: a throwaway repo with the plugin set up (solo profile) and an approved intent and spec ---------
Hide
Type "PLUGIN_DIR=$PWD && rm -rf /tmp/sdlc-demo && mkdir /tmp/sdlc-demo && cd /tmp/sdlc-demo && git init -q -b main && git commit -q --allow-empty -m init && cp $PLUGIN_DIR/docs/demo/Makefile.demo Makefile && git add Makefile && git commit -qm 'build: Makefile wired for python' && clear"
Enter
Type "PYTHONDONTWRITEBYTECODE=1 CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1 claude --plugin-dir $PLUGIN_DIR"
Enter
Wait+ Screen /\/tmp\/sdlc-demo/
Sleep 2 s
Type "/zouj-ai-sdlc:setup solo"
Enter
Wait+ Screen /chore\(aiops\)|profile solo/
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Type "! git add -A && git commit -m 'chore: adopt zouj-ai-sdlc (profile solo)'"
Enter
Wait+Screen /create mode/
Sleep 2s
Type "/clear"
Enter
Sleep 3s
Show

# --- 1. Claude tries to write code before a plan exists, and the hook blocks it ---------------------------------
Type "Use the Write tool right now to create src/greet.py with def greet(name): return f'Bonjour, {name} !' — do not run /zouj-ai-sdlc:intent first."
Sleep 500ms
Enter
Wait+Screen /BLOCKED \[G-/
Sleep 4s

# --- 2. The workflow instead: intent, then the human opens each gate by typing the phrase ------------------------
Type "/zouj-ai-sdlc:intent greet people in French: formal 'Bonjour, <name> !', return 'Bonjour !' when empty or whitespace-only, strip outer spaces, str-only, Python module src/greet.py only, set Open questions to None"
Enter
Hide
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Show
Sleep 2s
Type "Intent Approved 0001"
Enter
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Sleep 2s
Hide
Type "/zouj-ai-sdlc:spec — accept all recommended defaults and do not open interactive questions"
Enter
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Sleep 2s
Type "Spec Approved 0001"
Enter
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Sleep 2s
Type "/zouj-ai-sdlc:plan — use all recommended defaults and do not open interactive questions"
Enter
Sleep 3s
# The plan skill always asks its 3 hardest questions: take each recommended answer, then Submit.
# (If it asked none, these Enters land on an empty prompt and do nothing.)
Wait+Screen /Enter to select|· done \d+:\d+ [AP]M\s+─+\s+❯/
Sleep 1s
Enter
Sleep 1s
Enter
Sleep 1s
Enter
Sleep 1s
Enter
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Sleep 2s
Show
Sleep 2s
Type "Plan Approved 0001"
Enter
Sleep 3s
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Sleep 3s

# --- 3. Execution: a failing test first, then the code, then make check green -----------------------------------
Type "/zouj-ai-sdlc:implement"
Enter
Hide
Wait+Screen /Red:|FAILED|failed/
Show
Sleep 4s
Hide
Wait+Screen /· done \d+:\d+ [AP]M\s+(●[^❯]*)?─+\s+❯/
Show
Sleep 5s
