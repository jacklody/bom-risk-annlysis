import os, sys
os.chdir(r'D:\1项目清单\交期风险排查\交期风险排查V4\backend')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

import uvicorn
print("Attempting to start uvicorn on 0.0.0.0:8000 ...")
sys.stdout.flush()
try:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
except Exception as e:
    print(f"uvicorn error: {e}")
    sys.stdout.flush()
