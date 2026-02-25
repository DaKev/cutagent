# CutAgent demo: probe → scenes → execute EDL → error recovery
# Run from project root: vhs docs/demo.tape
# Prereq: pip install -e .  (or pip install cutagent)
# Requires: cutagent, ffmpeg, ttyd (for vhs)

Output docs/demo.gif
Require cutagent
Require ffmpeg

Set FontSize 14
Set Width 900
Set Height 550
Set TypingSpeed 80ms

# Setup: create test video (hidden from recording)
# demo_edit.json lives in docs/ — execute uses it via path
Hide
Type "ffmpeg -y -f lavfi -i testsrc=duration=5:size=320x240:rate=30 -f lavfi -i sine=frequency=440:duration=5 -c:v libx264 -preset ultrafast -c:a aac -pix_fmt yuv420p demo.mp4 2>/dev/null"
Enter
Sleep 3s
Show

# 1. Probe
Type "cutagent probe demo.mp4"
Enter
Sleep 2s

# 2. Detect scenes
Type "cutagent scenes demo.mp4 --threshold 0.3"
Enter
Sleep 2s

# 3. Execute EDL
Type "cutagent execute docs/demo_edit.json -q"
Enter
Sleep 2s

# 4. Error recovery (end beyond duration)
Type "cutagent trim demo.mp4 --start 0 --end 999 -o out.mp4"
Enter
Sleep 2s

# Cleanup (hidden)
Hide
Type "rm -f demo.mp4 clip.mp4 out.mp4"
Enter
Sleep 500ms
Show
