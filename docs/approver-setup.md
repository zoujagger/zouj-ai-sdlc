# Approver setup (signed approvals)

The `team` and `strict` profiles accept an approval only as a commit signed by a key in
`.aiops/config/allowed-signers`. Set up a key once per approver:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aiops_signing -C "aiops approvals"   # a dedicated key, WITH a passphrase (or an sk- key)
git config --global gpg.format ssh                       # global: repo-local signing settings are refused
git config --global user.signingkey ~/.ssh/aiops_signing.pub
ssh-add -d ~/.ssh/aiops_signing 2>/dev/null              # keep it OUT of ssh-agent, which would sign silently
echo "$(git config user.email) namespaces=\"git\" $(cat ~/.ssh/aiops_signing.pub)" >> .aiops/config/allowed-signers
sdlc legacy-approvals --write                           # once, when upgrading: records older unsigned approvals
git add .aiops/config && git commit -m "chore(aiops): approver keys"   # lands via PR; CI trusts the target branch's list
```

How strong each signing-key option is: [approval isolation](architecture.md#approval-isolation).

The escape hatch `"approval_key_policy": "any"` (in `.aiops/config.json`) accepts any key. Its cost: anything running
as you can then sign approvals.

## Checking and approving
`sdlc doctor` checks the setup.

Under the default `approval_key_policy: "human"`, `sdlc approve` refuses before stamping anything unless each
signature needs you:
- a passphrase key not loaded in ssh-agent, or
- an `sk-` key (touch).

How to approve, by key type:
- **Any key:** approve in your own terminal with
  `/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN intent|spec|plan`. It asks for the passphrase. `sdlc where` and
  the status card print the exact path.
- **An `sk-` key:** typing `Plan Approved NNNN` in Claude also works.
- **A passphrase key:** Claude tells you the exact terminal command instead.
