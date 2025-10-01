# Git Cheat Sheet (practical)

## Identity (once per machine or per repo)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
# or per-repo (omit --global)

## New / Clone
git init
git clone https://github.com/<you>/<repo>.git

## Status & history
git status
git log --oneline --graph --decorate -n 20

## Stage & commit
git add <path>           # stage changes
git add -p               # interactively stage hunks
git commit -m "message"

## Diff & restore
git diff                 # unstaged
git diff --staged        # staged
git restore <file>       # discard unstaged changes
git restore --staged <file>  # unstage

## Branches
git branch               # list
git switch -c feature/x  # create & switch
git switch main          # switch
git merge feature/x      # merge into current
git rebase main          # rebase onto main (careful)

## Stash
git stash push -m "msg"
git stash list
git stash pop

## Remote workflow
git remote -v
git remote add origin https://github.com/<you>/<repo>.git
git fetch origin
git pull --ff-only
git push -u origin main
git push origin --tags

## Tags
git tag -a v1.0.0 -m "msg"
git push origin v1.0.0

## Undo (choose carefully)
git reset --soft HEAD~1   # keep changes staged
git reset --mixed HEAD~1  # keep changes unstaged (default)
git reset --hard HEAD~1   # DROP changes
git revert <commit>       # make inverse commit (safe)

## Git LFS (large files)
git lfs install
git lfs track "*.pdf"
git add .gitattributes
git commit -m "Enable LFS for PDFs"

## Line endings (Windows-friendly)
# .gitattributes
* text=auto eol=lf
# Or per-language overrides as needed.

## Useful config
git config --global pull.ff only
git config --global init.defaultBranch main
git config --global core.autocrlf false

## GitHub CLI (optional)
gh auth login
gh pr create --base main --head feature/x -t "Feature X" -b "Details"
gh pr merge --squash --delete-branch
