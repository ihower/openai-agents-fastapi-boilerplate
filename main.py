from dotenv import load_dotenv
load_dotenv(".env", override=True)

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 掛載靜態文件目錄
app.mount("/static", StaticFiles(directory="static"), name="static")

# 首頁路由
@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

# 引入 routers
from app.agent_controller import router as agent_controller
from app.test_controller import router as test_controller

app.include_router(agent_controller)
app.include_router(test_controller)        