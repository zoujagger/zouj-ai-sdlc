# Demo recording

`demo.tape` is a [vhs](https://github.com/charmbracelet/vhs) script for the README's demo GIF. In about a minute of
footage it shows:
1. Claude trying to write code before a plan exists, and the hook blocking it (`BLOCKED [G-…]`);
2. the human opening the gates by typing `Intent Approved 0001`, `Spec Approved 0001` and `Plan Approved 0001`;
3. Claude running TDD: a failing test first, then the code, then `make check` green.

## Recording
The tape drives a live Claude Code session, so a human records it.

Prerequisites:
- `vhs` (and its `ttyd`, `ffmpeg`);
- `claude` signed in;
- `ruff`, `mypy` and `pytest` on PATH (`Makefile.demo`, the demo repo's Makefile, wires them for Python).

Run it from the plugin's checkout: the tape loads the plugin with `claude --plugin-dir $PWD`, so it records the
working tree, not the installed release.

```bash
mkdir -p ~/.cache/vhs && TMPDIR=~/.cache/vhs vhs docs/demo/demo.tape   # writes docs/demo/demo.gif; works in /tmp/sdlc-demo, deletes it first
```

Tips:
- **Long waits are hidden.** The model's answers vary in length, so the tape hides the waits (`Hide`/`Show`) and
  shows only the moments that matter.
- **If a `Wait` times out,** the model worded its reply differently. Adjust the pattern, or raise `WaitTimeout`.
- **The plan's stress test** (its 3 hardest questions) is answered by the tape with the recommended options.
- **If the brainstorming interview asks questions,** answer them in the session. The intent text in the tape keeps
  them few.
- **Frames go to `$TMPDIR`,** hidden ones included: a full run fills a small tmpfs `/tmp`, hence `TMPDIR` above.
- **Keep the GIF small.** Aim for under 5 MB. If it isn't, re-encode it:
  `ffmpeg -i demo.gif -vf "fps=10,scale=1024:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" small.gif`

Commit `docs/demo/demo.gif` once it looks right. The README embeds it.
