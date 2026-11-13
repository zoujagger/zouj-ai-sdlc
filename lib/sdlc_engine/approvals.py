"""Human gates. An approval stamps the artifact (status + approved-* fields) and, by default, commits it alone
with an `AIOps-Approval:` trailer so CI can audit who opened each gate. Only two callers exist: the
UserPromptSubmit hook (the human typed `Plan Approved`) and `sdlc approve` run by a human in a terminal.
"""

import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import artifacts as A
from .machine import DEFAULT_CONFIG, GIT, PLUGIN_ROOT, SCHEMAS, config, evaluate, gate, git, intent_dirs, read
from .schema import validate

TRAILER = "AIOps-Approval"
CLAUDE_TRAILER_RE = re.compile(r"^Co-Authored-By:.*\bClaude\b", re.I | re.M)


def running_under_agent():
    return os.environ.get("CLAUDECODE") == "1" or os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1"


def approver(root):
    name = git(root, "config", "user.name") or os.environ.get("USER") or "unknown"
    email = git(root, "config", "user.email")
    return f"{name} <{email}>" if email else name


PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").is_file() else "python3"


def approve_command(ident="NNNN", kind="intent|spec|plan"):
    """The terminal command that approves: the plugin's absolute path (consumer repos have no bin/sdlc), run by an
    absolute, isolated python so nothing earlier on PATH or in the user site runs inside the approval."""
    return f"{PYTHON} -I {shlex.quote(str(PLUGIN_ROOT / 'bin' / 'sdlc'))} approve {ident} {kind}"


SIGNING_HELP = (
    "Set up SSH commit signing with a dedicated key (global config: repo-local signing settings are refused), then\n"
    "approve again:\n"
    '  ssh-keygen -t ed25519 -f ~/.ssh/aiops_signing -C "aiops approvals"   # set a passphrase\n'
    "  git config --global gpg.format ssh\n"
    "  git config --global user.signingkey ~/.ssh/aiops_signing.pub\n"
    "and make sure your key is in .aiops/config/allowed-signers (human-owned), e.g.\n"
    '  echo "$(git config user.email) namespaces=\\"git\\" $(cat ~/.ssh/aiops_signing.pub)" >> .aiops/config/allowed-signers\n'
    "Keep the key out of ssh-agent (or use an sk- key): `sdlc doctor` checks it."
)


KEY_HELP = (
    "Approvals need a human for each signature: use a passphrase-protected key that is NOT loaded in ssh-agent\n"
    "(add one with `ssh-keygen -p -f ~/.ssh/aiops_signing`; unload with `ssh-add -d ~/.ssh/aiops_signing`), or a FIDO\n"
    f"`sk-` key that needs a touch. Then approve in your own terminal: `{approve_command()}`\n"
    '(it asks for the passphrase). Escape hatch (human-owned): "approval_key_policy": "any" in .aiops/config.json.'
)


# The approval commit always signs with the system's ssh-keygen and without hooks, whatever the repo's config says:
# anything an agent can write (repo git config, .git/hooks) must not sit between the human and the signature.
SSH_KEYGEN = (
    "/usr/bin/ssh-keygen" if Path("/usr/bin/ssh-keygen").is_file() else (shutil.which("ssh-keygen") or "ssh-keygen")
)
SSH_ADD = "/usr/bin/ssh-add" if Path("/usr/bin/ssh-add").is_file() else (shutil.which("ssh-add") or "ssh-add")
PINNED = (
    "-c",
    "gpg.format=ssh",
    "-c",
    f"gpg.ssh.program={SSH_KEYGEN}",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.attributesFile=/dev/null",
)
# Repo-local (and worktree) config may only hold keys that can't run code or redirect signing; read with includes.
LOCAL_ALLOWED_RE = re.compile(
    r"^(core\.(repositoryformatversion|filemode|bare|logallrefupdates|ignorecase|precomposeunicode|symlinks|"
    r"autocrlf|eol|safecrlf|quotepath|sparsecheckout|worktree)|extensions\..+|remote\..+|branch\..+|"
    r"user\.(name|email)|commit\.gpgsign|tag\.gpgsign|pull\.\w+|push\.\w+|fetch\.\w+|init\.defaultbranch|"
    r"submodule\.[^.]+\.(url|active|branch)|gc\.\w+|maintenance\..+)$",
    re.I,
)


def _signing_key_files(root):
    """(public key text, private key path or None) for git's user.signingkey."""
    key = git(root, "config", "user.signingkey") or ""
    if key.startswith("key::"):
        return key[5:], None
    path = Path(key).expanduser()
    if path.suffix == ".pub":
        return (path.read_text() if path.is_file() else ""), path.with_suffix("")
    pub = Path(f"{path}.pub")
    return (pub.read_text() if pub.is_file() else ""), path


def _signer_options(root, blob):
    """The options (`namespaces=…`, `no-touch-required`, …) of the allowed-signers entry for a key blob."""
    f = root / SIGNERS
    for line in (f.read_text() if f.is_file() else "").splitlines():
        words = line.split()
        if blob in words and not line.lstrip().startswith("#"):
            opts = words[1 : words.index(blob) - 1]  # principals [options] keytype key
            return {o.split("=", 1)[0].strip().lower() for o in ",".join(opts).split(",") if o}  # case-insensitive
    return set()


def key_protection(root):
    """Why the signing key could sign without the human, or None: an `sk-` key (a touch per signature) or a
    passphrase-protected key that isn't cached in the reachable ssh-agent."""
    pubtext, private = _signing_key_files(root)
    parts = pubtext.split()
    if parts and parts[0].startswith("sk-"):
        if len(parts) >= 2 and _signer_options(root, parts[1]) & {"no-touch-required"}:
            return "the sk- key is allow-listed with no-touch-required, so it would sign without a touch"
        return None
    if private is None or not private.is_file():
        return "the signing key's private file can't be found, so its protection can't be checked"
    unlocked = subprocess.run([SSH_KEYGEN, "-y", "-P", "", "-f", str(private)], capture_output=True)
    if unlocked.returncode == 0:
        return "the signing key has no passphrase, so anything running as you could sign approvals"
    if os.environ.get("SSH_AUTH_SOCK") and len(parts) >= 2:
        loaded = subprocess.run([SSH_ADD, "-L"], capture_output=True, text=True)
        if loaded.returncode == 0 and parts[1] in loaded.stdout:
            return "the signing key is loaded in ssh-agent, so it would sign without asking you"
    return None


def local_config_keys(root):
    """Repo-local or worktree config keys (includes followed) outside the allow-list."""
    listing = git(root, "config", "--list", "--show-scope", "--includes") or ""
    keys = set()
    for line in listing.splitlines():
        scope, _, entry = line.partition("\t")
        key = entry.split("=", 1)[0]
        if scope in ("local", "worktree") and not LOCAL_ALLOWED_RE.match(key):
            keys.add(key)
    return sorted(keys)


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _commit_alone(root, rel, title, body, sign):
    """Commit `rel` as it is in the working tree, alone, with plumbing: the blob is hashed without filters, the
    tree is built in a throwaway index, and `commit-tree` signs it. Attributes come from the empty tree, so no hook,
    fsmonitor, filter or worktree scan runs in the human's approval. Returns (sha, fix) where fix is a command the
    human must run when the real index couldn't follow, or None if the commit failed."""
    base_env = {**os.environ, "GIT_ATTR_SOURCE": EMPTY_TREE}

    def run(*args, index=None):
        env = {**base_env, "GIT_INDEX_FILE": index} if index else base_env
        r = subprocess.run([GIT, *PINNED, *args], cwd=root, env=env, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    blob = run("hash-object", "-w", "--no-filters", "--", rel)
    head = run("rev-parse", "-q", "--verify", "HEAD^{commit}")
    if not blob:
        return None
    entry = f"{'100755' if os.access(root / rel, os.X_OK) else '100644'},{blob},{rel}"
    with tempfile.TemporaryDirectory() as tmp:
        index = str(Path(tmp) / "index")
        if (head and run("read-tree", head, index=index) is None) or run(
            "update-index", "--add", "--cacheinfo", entry, index=index
        ) is None:
            return None
        tree = run("write-tree", index=index)
    if not tree:
        return None
    sha = run("commit-tree", tree, *(["-p", head] if head else []), *sign, "-m", title, "-m", body)
    if not sha or run("update-ref", "-m", title, "HEAD", sha, *([head] if head else [])) is None:
        return None
    if run("update-index", "--add", "--cacheinfo", entry) is None:  # the real index follows the commit
        return sha, f"git reset -q -- {rel}"
    return sha, None


KEY_POLICIES = ("human", "sk", "any")  # team: a human per signature · strict: a touch key only · solo/escape hatch


def signing_problem(root):
    """Why a signed approval commit can't be made here, or None."""
    cfg = config(root)
    if not cfg.get("require_signed_approvals"):
        return None
    if not cfg["commit_approvals"]:
        return "require_signed_approvals needs commit_approvals: true in .aiops/config.json"
    keys = local_config_keys(root)
    if keys:
        return (
            f"repo-local git config sets {', '.join(keys)}: signing settings must come from your global git "
            f"config (`git config --global …`), and the repo's own config may only hold basics (user.name/email, "
            f"remote.*, branch.*, core file settings), never keys that run code or change signing "
            f"(remove with `git config --local --unset <key>`)"
        )
    if not git(root, "config", "user.signingkey"):
        return "git has no signing key configured (user.signingkey)"
    if (git(root, "config", "gpg.format") or "openpgp") != "ssh":
        return "git signing is not set to SSH (gpg.format ssh)"
    policy = cfg.get("approval_key_policy", "human")
    if policy not in KEY_POLICIES:
        return (
            f"unknown approval_key_policy {policy!r} in .aiops/config.json (use one of: "
            f'{", ".join(KEY_POLICIES)}); an unknown value is refused, never treated as "any"'
        )
    if policy == "sk" and not _signing_key_files(root)[0].startswith("sk-"):
        return (
            'the strict profile (approval_key_policy "sk") accepts only a FIDO sk- key that needs a touch per '
            f"signature.\n{KEY_HELP}"
        )
    if policy in ("human", "sk"):
        weak = key_protection(root)
        if weak:
            return f"{weak}.\n{KEY_HELP}"
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
    if (d / f"{kind}.md").is_symlink():
        return False, f"{kind}.md for {ident} is a symlink; approvals are committed only for regular files."
    errors, _ = validate(d, kind)
    if errors:
        return False, f"{kind}.md for {ident} does not validate, so it was NOT approved:\n- " + "\n- ".join(errors)
    if gate(d, kind)[0]:
        return True, f"{kind}.md for {ident} was already approved and is unchanged."
    problem = signing_problem(root)
    if problem:
        setup = "" if KEY_HELP in problem else f"\n{SIGNING_HELP}"
        return False, (
            f"{kind}.md for {ident} was NOT approved: {problem.rstrip('.')}.{setup}\n"
            f"Approve in your own terminal: `{approve_command(ident, kind)}`."
        )
    signed = bool(config(root).get("require_signed_approvals"))
    who = who or approver(root)
    digest = A.approval_hash(kind, text)
    stamped = A.set_fields(
        text,
        {
            "status": schema["gate"],
            "approved-by": who,
            "approved-at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "approved-via": via,
            "approved-sha256": digest,
        },
    )
    path = d / f"{kind}.md"
    path.write_text(stamped)
    note = ""
    if config(root)["commit_approvals"] and git(root, "rev-parse", "--git-dir") is not None:
        rel = str(path.relative_to(root))
        title = f"chore(aiops): {schema['approval_phrase']} {ident}"
        body = f"{TRAILER}: {kind} {ident} sha256={digest}\nApproved-By: {who}"
        sign = ["-S"] if signed else []
        sha, fix = _commit_alone(root, rel, title, body, sign) or (None, None)
        if sha is None:
            if signed:  # an unsigned stamp would never pass the audit: roll it back
                path.write_text(text)
                return False, (
                    f"{kind}.md for {ident} was NOT approved: the signed commit failed (signing needs "
                    f"you: a passphrase or touch, which needs a terminal). Approve in your own terminal: "
                    f"`{approve_command(ident, kind)}`."
                )
            note = "\n(The approval is in the working tree, but committing it failed. Commit it yourself.)"
        else:
            note = f"\nCommitted as `{title}`." + (
                f" The index was busy and still holds the old {kind}.md: run `{fix}` before your next commit."
                if fix
                else ""
            )
    st = evaluate(root, d)
    return True, (
        f"{schema['approval_phrase']}: {kind}.md for {ident} approved by {who}.{note}\n"
        f"Intent {ident} is now in state {st.state} {st.name}. Next: {st.next}"
    )


def close(root, d, who=None):
    path = d / "intent.md"
    if not path.is_file():
        return False, "intent.md does not exist"
    path.write_text(A.set_fields(path.read_text(), {"status": "Closed", "closed-by": who or approver(root)}))
    return True, f"Intent {d.name[:4]} closed."


SIGNERS, LEGACY, CONFIG = ".aiops/config/allowed-signers", ".aiops/config/legacy-approvals", ".aiops/config.json"


class BaseRefError(Exception):
    """The trust anchor (`--base`) doesn't resolve: fail closed rather than trusting the change itself."""


def trust(root, base=None, warnings=None):
    """(config, allowed-signers text, legacy approval shas): from `base` when given, else the working tree.
    A PR must not be able to vouch for itself, so CI passes the target branch as `base`. Only when the base has
    no signer list at all (the change that introduces signing) does the working tree count, with a warning."""

    def tree(rel):
        f = root / rel
        return f.read_text() if f.is_file() else None

    def at_base(rel):
        return git(root, "show", f"{base}:{rel}")

    src = tree
    if base is not None:
        if not base.strip() or git(root, "rev-parse", "-q", "--verify", f"{base}^{{commit}}") is None:
            raise BaseRefError(
                f"base ref {base!r} does not resolve to a commit; refusing to audit against the change "
                "itself (fetch the target branch, e.g. actions/checkout with fetch-depth: 0)"
            )
        if at_base(SIGNERS) is None:
            if warnings is not None:
                warnings.append(
                    f"bootstrap: {base} has no {SIGNERS}, so this change's signer list is trusted. "
                    "It must get CODEOWNERS review."
                )
        else:
            src = at_base
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(src(CONFIG) or "{}"))
    except ValueError:
        pass
    legacy = {
        ln.split()[0] for ln in (src(LEGACY) or "").splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    }
    return cfg, src(SIGNERS) or "", legacy


def signature(root, sha, signers):
    """git's %G? for `sha`, verified against `signers` (G = good signature by an allow-listed key)."""
    with tempfile.NamedTemporaryFile("w", suffix=".allowed-signers", delete=False) as f:
        f.write(signers)
    try:
        return git(root, "-c", f"gpg.ssh.allowedSignersFile={f.name}", "log", "-1", "--format=%G?", sha) or "N"
    finally:
        os.unlink(f.name)


def approval_commit(root, d, kind, digest):
    """(sha, message) of the oldest commit that introduced `approved-sha256: digest`, or None."""
    rel = str((d / f"{kind}.md").relative_to(root))
    log = git(root, "log", "--format=%H%x00%B%x1e", "-S", f"approved-sha256: {digest}", "--", rel)
    if not log:
        return None
    oldest = [e for e in log.split("\x1e") if e.strip()][-1]  # git log is newest first
    sha, _, msg = oldest.strip().partition("\x00")
    return sha, msg


FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def commit_problems(root, d, kind):
    """(approval sha or None, [problems]) for an open gate: every audit check except the signature."""
    text = read(d, kind)
    a = A.parse(text or "")
    if a.get("status") != SCHEMAS[kind]["gate"]:
        return None, []
    ok, why = gate(d, kind)
    if not ok:
        return None, [f"{kind}.md is marked {a.get('status')} but {why}"]
    if not a.get("approved-by"):
        return None, [f"{kind}.md is approved without approved-by"]
    rel = str((d / f"{kind}.md").relative_to(root))
    found = approval_commit(root, d, kind, a.get("approved-sha256"))
    if not found:
        return None, [f"{kind}.md approval is not committed (expected a commit with an `{TRAILER}:` trailer)"]
    sha, msg = found
    if f"{TRAILER}: {kind} {d.name[:4]}" not in msg:
        return sha, [f"{kind}.md approval was introduced by {sha[:10]}, which is not an approval commit"]
    if CLAUDE_TRAILER_RE.search(msg):
        return sha, [f"{kind}.md approval commit {sha[:10]} is co-authored by Claude: agents cannot approve gates"]
    if f"sha256={a.get('approved-sha256')}" not in msg:
        return sha, [f"{kind}.md approval commit {sha[:10]} has a trailer whose sha256 doesn't match the stamp"]
    touched = (git(root, "show", "--name-only", "--format=", sha) or "").split()
    if touched != [rel]:
        return sha, [
            f"{kind}.md approval commit {sha[:10]} must change only {rel} (it also touches "
            f"{', '.join(t for t in touched if t != rel)[:120]})"
        ]
    return sha, []


KEY_TYPE_RE = re.compile(r"^(sk-|ssh-|ecdsa-)")


def signer_entries(signers):
    """[(line, options, keytype, blob)] for each allowed-signers line: principals [options] keytype key."""
    out = []
    for line in signers.splitlines():
        words = line.split()
        if not words or line.lstrip().startswith("#"):
            continue
        i = next((n for n, w in enumerate(words[1:], 1) if KEY_TYPE_RE.match(w)), None)
        if i is None or i + 1 >= len(words):
            continue
        opts = {o.split("=", 1)[0].strip().lower() for o in ",".join(words[1:i]).split(",") if o}  # as OpenSSH may
        out.append((line.strip(), opts, words[i], words[i + 1]))
    return out


def non_touch_signers(signers):
    """Allowed-signers lines that can sign without a touch: not an sk- key, or allow-listed with no-touch-required."""
    return [
        line
        for line, opts, ktype, _ in signer_entries(signers)
        if not ktype.startswith("sk-") or "no-touch-required" in opts
    ]


def _fingerprint(ktype, blob):
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as f:
        f.write(f"{ktype} {blob}\n")
    try:
        r = subprocess.run([SSH_KEYGEN, "-l", "-f", f.name], capture_output=True, text=True)
        return r.stdout.split()[1] if r.returncode == 0 and len(r.stdout.split()) > 1 else None
    finally:
        os.unlink(f.name)


def signer_needs_touch(root, sha, signers):
    """True if `sha` was signed by an allow-listed sk- key that needs a touch (the strict profile's proof)."""
    with tempfile.NamedTemporaryFile("w", suffix=".allowed-signers", delete=False) as f:
        f.write(signers)
    try:
        fp = git(root, "-c", f"gpg.ssh.allowedSignersFile={f.name}", "log", "-1", "--format=%GK", sha)
    finally:
        os.unlink(f.name)
    return (
        any(
            _fingerprint(ktype, blob) == fp and ktype.startswith("sk-") and "no-touch-required" not in opts
            for _line, opts, ktype, blob in signer_entries(signers)
        )
        if fp
        else False
    )


def audit(root, d, kind, base=None, warnings=None):
    """CI check: an open gate must come from a single-file approval commit signed by an allow-listed key
    (or listed, by full sha, in legacy-approvals), never from an agent-authored commit."""
    sha, problems = commit_problems(root, d, kind)
    if problems or sha is None:
        return problems
    try:
        cfg, signers, legacy = trust(root, base, warnings)
    except BaseRefError as exc:
        return [str(exc)]
    if cfg.get("require_signed_approvals") and sha not in {x for x in legacy if FULL_SHA_RE.match(x)}:
        verdict = signature(root, sha, signers)
        if verdict != "G":
            return [
                f"{kind}.md approval commit {sha[:10]} is not signed by an allow-listed signer "
                f"(git %G? = {verdict}; signers from {base or 'the working tree'})"
            ]
        if cfg.get("approval_key_policy") == "sk" and not signer_needs_touch(root, sha, signers):
            return [
                f"{kind}.md approval commit {sha[:10]} is signed by a key that doesn't need a touch; the strict "
                'profile (approval_key_policy "sk") requires an allow-listed sk- key without no-touch-required'
            ]
    return []


def unsigned_approvals(root):
    """Approval commits of open gates that don't verify against the working-tree signer list but pass every other
    audit check, are on main, and predate the commit that introduced the signer list there: only those may become
    legacy (a forged approval, or one made after signing started, must never be grandfathered)."""
    _, signers, _ = trust(root)
    main = config(root)["main_branch"]
    intro = (git(root, "log", main, "--diff-filter=A", "--format=%H", "--", SIGNERS) or "").split()
    out = []
    for d in intent_dirs(root):
        for kind in ("intent", "spec", "plan"):
            sha, problems = commit_problems(root, d, kind)
            if not sha or problems or signature(root, sha, signers) == "G":
                continue
            if not _is_ancestor(root, sha, main) or (
                intro and not (sha != intro[-1] and _is_ancestor(root, sha, intro[-1]))
            ):
                continue
            out.append((sha, f"{d.name}/{kind}.md"))
    return out


def _is_ancestor(root, a, b):
    return subprocess.run([GIT, "merge-base", "--is-ancestor", a, b], cwd=root, capture_output=True).returncode == 0
