"""Human gates. An approval stamps the artifact (status + approved-* fields) and, by default, commits it alone
with an `AIOps-Approval:` trailer so CI can audit who opened each gate. Only two callers exist: the
UserPromptSubmit hook (the human typed `Plan Approved`) and `sdlc approve` run by a human in a terminal.
"""
import datetime
import os
import re

from . import artifacts as A
from .machine import SCHEMAS, config, evaluate, gate, git, read
from .schema import validate

TRAILER = "AIOps-Approval"
CLAUDE_TRAILER_RE = re.compile(r"^Co-Authored-By:.*\bClaude\b", re.I | re.M)


def running_under_agent():
    return os.environ.get("CLAUDECODE") == "1" or os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1"


def approver(root):
    name = git(root, "config", "user.name") or os.environ.get("USER") or "unknown"
    email = git(root, "config", "user.email")
    return f"{name} <{email}>" if email else name


SIGNING_HELP = (
    "Set up SSH commit signing, then approve again:\n"
    "  git config gpg.format ssh\n"
    "  git config user.signingkey ~/.ssh/id_ed25519.pub\n"
    "and make sure your key is in .aiops/config/allowed-signers (human-owned), e.g.\n"
    "  echo \"$(git config user.email) namespaces=\\\"git\\\" $(cat ~/.ssh/id_ed25519.pub)\" >> .aiops/config/allowed-signers\n"
    "Prefer a passphrase-protected key (or ssh-add -c) so nothing can sign silently as you.")


def signing_problem(root):
    """Why a signed approval commit can't be made here, or None."""
    cfg = config(root)
    if not cfg.get("require_signed_approvals"):
        return None
    if not cfg["commit_approvals"]:
        return "require_signed_approvals needs commit_approvals: true in .aiops/config.json"
    if not git(root, "config", "user.signingkey"):
        return "git has no signing key configured (user.signingkey)"
    if (git(root, "config", "gpg.format") or "openpgp") != "ssh":
        return "git signing is not set to SSH (gpg.format ssh)"
    return None


def approve(root, d, kind, via, who=None):
    """(ok, message). Refuses unless the artifact validates and the upstream gate is open."""
    schema = SCHEMAS[kind]
    if not schema["gate"]:
        return False, f"{kind}.md is not a human gate; the human's final decision is the merge."
    ident = d.name[:4]
    text = read(d, kind)
    if text is None:
        return False, f"{kind}.md does not exist for {d.name}; nothing to approve."
    if schema["requires"]:
        ok, why = gate(d, schema["requires"])
        if not ok:
            return False, f"{schema['requires']}.md for {ident} is not approved ({why}); approve it first."
    errors, _ = validate(d, kind)
    if errors:
        return False, f"{kind}.md for {ident} does not validate, so it was NOT approved:\n- " + "\n- ".join(errors)
    if gate(d, kind)[0]:
        return True, f"{kind}.md for {ident} was already approved and is unchanged."
    problem = signing_problem(root)
    if problem:
        return False, f"{kind}.md for {ident} was NOT approved: {problem}.\n{SIGNING_HELP}"
    signed = bool(config(root).get("require_signed_approvals"))
    who = who or approver(root)
    digest = A.approval_hash(kind, text)
    stamped = A.set_fields(text, {
        "status": schema["gate"], "approved-by": who,
        "approved-at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "approved-via": via, "approved-sha256": digest})
    path = d / f"{kind}.md"
    path.write_text(stamped)
    note = ""
    if config(root)["commit_approvals"] and git(root, "rev-parse", "--git-dir") is not None:
        rel = str(path.relative_to(root))
        title = f"chore(aiops): {schema['approval_phrase']} {ident}"
        body = f"{TRAILER}: {kind} {ident} sha256={digest}\nApproved-By: {who}"
        sign = ["-S"] if signed else []
        if git(root, "add", "--", rel) is None or \
                git(root, "commit", "-q", *sign, "-m", title, "-m", body, "--", rel) is None:
            if signed:   # an unsigned stamp would never pass the audit: roll it back
                path.write_text(text)
                git(root, "reset", "-q", "--", rel)
                return False, (f"{kind}.md for {ident} was NOT approved: the signed commit failed (is your key "
                               f"unlocked / in ssh-agent?).\n{SIGNING_HELP}")
            note = "\n(The approval is in the working tree, but committing it failed. Commit it yourself.)"
        else:
            note = f"\nCommitted as `{title}`."
    st = evaluate(root, d)
    return True, (f"{schema['approval_phrase']}: {kind}.md for {ident} approved by {who}.{note}\n"
                  f"Intent {ident} is now in state {st.state} {st.name}. Next: {st.next}")


def close(root, d, who=None):
    path = d / "intent.md"
    if not path.is_file():
        return False, "intent.md does not exist"
    path.write_text(A.set_fields(path.read_text(), {"status": "Closed", "closed-by": who or approver(root)}))
    return True, f"Intent {d.name[:4]} closed."


def audit(root, d, kind):
    """CI check: an open gate must come from a human approval commit, not from an agent-authored commit."""
    text = read(d, kind)
    a = A.parse(text or "")
    if a.get("status") != SCHEMAS[kind]["gate"]:
        return []
    ok, why = gate(d, kind)
    if not ok:
        return [f"{kind}.md is marked {a.get('status')} but {why}"]
    if not a.get("approved-by"):
        return [f"{kind}.md is approved without approved-by"]
    rel = str((d / f"{kind}.md").relative_to(root))
    log = git(root, "log", "--format=%H%x00%B%x1e", "-S", f"approved-sha256: {a.get('approved-sha256')}", "--", rel)
    if not log:
        return [f"{kind}.md approval is not committed (expected a commit with an `{TRAILER}:` trailer)"]
    oldest = [e for e in log.split("\x1e") if e.strip()][-1]   # git log is newest first
    sha, _, msg = oldest.strip().partition("\x00")
    if f"{TRAILER}: {kind} {d.name[:4]}" not in msg:
        return [f"{kind}.md approval was introduced by {sha[:10]}, which is not an approval commit"]
    if CLAUDE_TRAILER_RE.search(msg):
        return [f"{kind}.md approval commit {sha[:10]} is co-authored by Claude: agents cannot approve gates"]
    if f"sha256={a.get('approved-sha256')}" not in msg:
        return [f"{kind}.md approval commit {sha[:10]} has a trailer whose sha256 doesn't match the stamp"]
    touched = (git(root, "show", "--name-only", "--format=", sha) or "").split()
    if touched != [rel]:
        return [f"{kind}.md approval commit {sha[:10]} must change only {rel} (it also touches "
                f"{', '.join(t for t in touched if t != rel)[:120]})"]
    signers = root / ".aiops" / "config" / "allowed-signers"
    if config(root).get("require_signed_approvals") and git(
            root, "-c", f"gpg.ssh.allowedSignersFile={signers}", "log", "-1", "--format=%G?", sha) not in ("G", "U"):
        return [f"{kind}.md approval commit {sha[:10]} is not signed (require_signed_approvals is on)"]
    return []
