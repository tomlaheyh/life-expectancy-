@echo off
echo ============================================
echo  Fixing .gitignore and cleaning Exclude-DIR
echo ============================================
echo.

REM Step 1: Remove the incorrectly named gitignore
echo Step 1: Removing old 'gitignore' from Git...
git rm gitignore
echo.

REM Step 2: Rename to .gitignore if needed
if exist gitignore (
    echo Step 2: Renaming gitignore to .gitignore...
    ren gitignore .gitignore
) else if not exist .gitignore (
    echo Step 2: Creating .gitignore...
    echo Exclude-DIR/> .gitignore
) else (
    echo Step 2: .gitignore already exists, skipping...
)
echo.

REM Step 3: Remove Exclude-DIR from Git tracking (keeps files on disk)
echo Step 3: Removing Exclude-DIR from Git tracking...
echo          (Files will remain on your disk, just untracked)
git rm -r --cached Exclude-DIR/
echo.

REM Step 4: Stage the .gitignore
echo Step 4: Staging .gitignore...
git add .gitignore
echo.

REM Step 5: Show what will be committed
echo ============================================
echo  Preview of changes:
echo ============================================
git status
echo.
echo ============================================
echo  Ready to commit. Press any key to commit
echo  and push, or Ctrl+C to cancel.
echo ============================================
pause

REM Step 6: Commit and push
git commit -m "fix: remove Exclude-DIR from tracking, add proper .gitignore"
git push
echo.
echo Done! Exclude-DIR is now untracked.
pause
