IMPORTANT:

Do not run the following command inside the `viva_safeland` folder:

```bash
isaac_run pegasus/pegasus_viva.py
```

You must run `pegasus_viva.py` outside the `viva_safeland` folder to prevent `uv` from attempting to install packages in the `ISAAC_PYTHON` packages folder.
    
Execute this when Waiting for first hearbeat is showing
pgrep -a px4 2>/dev/null | head -5
kill 579140 579299 2>/dev/null; sleep 1; pgrep -a px4 | wc -l