# Git Cheat Sheet (practical)

## Identity (once per machine or per repo)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"

## New / Clone
git init
git clone https://github.com/<you>/<repo>.git

## Status & history
git status
git log --oneline --graph --decorate -n 20

## Stage & commit
git add <path>
git add -p
git commit -m "message"

## Diff & restore
git diff
git diff --staged
git restore <file>
git restore --staged <file>

## Branches
git branch
git switch -c feature/x
git switch main
git merge feature/x
git rebase main

## Stash
git stash push -m "msg"
git stash list
git stash pop

## Remote workflow
git remote -v
git fetch origin
git pull --ff-only
git push -u origin main
git push origin --tags

## Tags
git tag -a v1.0.0 -m "msg"
git push origin v1.0.0

## Undo (pick carefully)
git reset --soft HEAD~1
git reset --mixed HEAD~1
git reset --hard HEAD~1
git revert <commit>

## Git LFS
git lfs install
git lfs track "*.pdf"
git add .gitattributes
git commit -m "Enable LFS for PDFs"

## Line endings
# .gitattributes
* text=auto eol=lf

## Useful config
git config --global pull.ff only
git config --global init.defaultBranch main
git config --global core.autocrlf false

## GitHub CLI (optional)
gh auth login
gh pr create --base main --head feature/x -t "Feature X" -b "Details"
gh pr merge --squash --delete-branch
