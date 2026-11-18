# Demo recording

`demo.tape` is a [vhs](https://github.com/charmbracelet/vhs) script for the README's demo GIF. In about 40 seconds of
footage it shows:
1. Claude trying to write code before a plan exists, and the hook blocking it (`BLOCKED [G-…]`);
2. the human opening the gates by typing `Intent Approved 0001`, `Spec Approved 0001` and `Plan Approved 0001`;
3. Claude running TDD: a failing test first, then the code, then `make check` green.

## Recording
The tape drives a live Claude Code session, so a human records it.

Prerequisites:
- `vhs` (and its `ttyd`, `ffmpeg`);
- `claude` signed in;
- the plugin installed (`/plugin install zouj-ai-sdlc@zouj`).

```bash
vhs docs/demo/demo.tape          # writes docs/demo/demo.gif; works in /tmp/sdlc-demo, deletes it first
```

Tips:
- **Long waits are hidden.** The model's answers vary in length, so the tape hides the waits (`Hide`/`Show`) and
  shows only the moments that matter.
- **If a `Wait` times out,** the model worded its reply differently. Adjust the pattern, or raise `WaitTimeout`.
- **If the brainstorming interview asks questions,** answer them in the session. The intent text in the tape keeps
  them few.
- **Keep the GIF small.** Aim for under 5 MB: lower `Width`/`Height` or raise `PlaybackSpeed` if it isn't.

Commit `docs/demo/demo.gif` once it looks right. The README embeds it.
