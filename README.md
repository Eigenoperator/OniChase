# OniChase full worktree backup

Backup ID: onichase-full-2026-05-11-165555
Created at: 2026-05-11T16:59:21-07:00
Source commit: 1d124dcbf61e8b3b0d46d5d17038b3b5a856bdf8
Archive size: 666M
Archive SHA256: d50fc1feb099be260dca00049870bcc85a3feda62864bbf451134e8e091ceae9

This branch is an off-main disaster-recovery backup. It stores the full working tree snapshot excluding .git, including tracked, modified, and untracked project files present at backup time.

Restore:

1. Clone the main repository:
   git clone git@github.com:Eigenoperator/OniChase.git OniChase
2. Fetch this backup branch:
   cd OniChase
   git fetch origin backup/full-onichase-full-2026-05-11-165555
3. Download the archive from this branch with Git LFS enabled, or checkout this branch in a separate directory.
4. Verify:
   sha256sum archive/OniChase-worktree-full.tar.zst
5. Extract onto a clean clone/workdir:
   tar -I zstd -xf archive/OniChase-worktree-full.tar.zst -C /path/to/OniChase

The manifest folder records git status, tracked/untracked/modified file lists, remotes, source HEAD, and disk usage at backup time.
