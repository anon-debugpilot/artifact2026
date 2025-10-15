DebugPilot (default):

1. Set `benchmark`:
    One legal example is `benchmark\Chart_18`
2. Set `user_driven.json`:
```
{"command": 0}
```
1. Run `interaction.py`:
``` python
  python interaction.py <project_id> <bug_id>
```

Use different `user_driven["command"]` for feedback.