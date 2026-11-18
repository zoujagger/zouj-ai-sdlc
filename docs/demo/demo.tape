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
Set WaitTimeout 300s
Set PlaybackSpeed 1.0

# --- off camera: a throwaway repo with the plugin set up (solo profile) and an approved intent and spec ---------
Hide
Type "rm -rf /tmp/sdlc-demo && mkdir /tmp/sdlc-demo && cd /tmp/sdlc-demo && git init -q && git commit -q --allow-empty -m init && clear"
Enter
Type "claude"
Enter
Wait+Screen /for shortcuts/
Type "/zouj-ai-sdlc:setup solo"
Enter
Wait+Screen /chore\(aiops\)|profile solo/
Type "Commit the scaffold with the command from the reply."
Enter
Wait+Screen /adopt zouj-ai-sdlc/
Type "/clear"
Enter
Show

# --- 1. Claude tries to write code before a plan exists, and the hook blocks it ---------------------------------
Type "Write src/greet.py with a function that greets people in French."
Sleep 500ms
Enter
Wait+Screen /BLOCKED \[G-/
Sleep 4s

# --- 2. The workflow instead: intent, then the human opens each gate by typing the phrase ------------------------
Type "/zouj-ai-sdlc:intent greet people in French, no options needed"
Enter
Hide
Wait+Screen /Intent Approved 0001/
Show
Sleep 2s
Type "Intent Approved 0001"
Enter
Wait+Screen /Approved|approved/
Sleep 2s
Hide
Type "/zouj-ai-sdlc:spec"
Enter
Wait+Screen /Spec Approved 0001/
Type "Spec Approved 0001"
Enter
Wait+Screen /Approved|approved/
Type "/zouj-ai-sdlc:plan"
Enter
Wait+Screen /Plan Approved 0001/
Show
Sleep 2s
Type "Plan Approved 0001"
Enter
Wait+Screen /EXECUTION|Approved/
Sleep 3s

# --- 3. Execution: a failing test first, then the code, then make check green -----------------------------------
Type "/zouj-ai-sdlc:implement"
Enter
Hide
Wait+Screen /Red:|FAILED|failed/
Show
Sleep 4s
Hide
Wait+Screen /PRE-REVIEW|make check/
Show
Sleep 5s
