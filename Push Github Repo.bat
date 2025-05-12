git init
git add .
git commit -m "first commit"
git branch -M main
@REM only run git remote add once
@REM git remote add origin https://github.com/AhmadAC/ESP32S3-CircuitPython.git
git push -u origin main

@REM git rm -r --cached __pycache__/  # Remove cached __pycache__ folders
@REM git rm --cached tempCodeRunnerFile.py  # Remove the temp file if tracked