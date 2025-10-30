from dataclasses import dataclass
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool, RunContextWrapper, ModelSettings, set_default_openai_client,  WebSearchTool, FileSearchTool
from tavily import AsyncTavilyClient
from datetime import datetime
from openai import AsyncOpenAI
import braintrust
import os
import asyncio
import aiosqlite
import json

braintrust_logger = None
openai_client = None

DB_PATH = "data/agent.db"

async def get_previous_items(thread_id: str) -> list:
    """
    根據 thread_id 從 agent_turns 取得最後一筆對話的 raw_items
    如果沒有找到，返回空列表
    """
    input_items = []

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT raw_items FROM agent_turns WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
            (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()

            if row and row[0]:
                try:
                    raw_items_list = json.loads(row[0])
                    for item_str in raw_items_list:
                        parsed_item = json.loads(item_str)
                        input_items.append(parsed_item)
                    print(f"Loaded {len(input_items)} items from previous conversation")
                except Exception as e:
                    print(f"Error loading raw_items: {e}")

    return input_items

async def save_agent_turn(thread_id: str, user_id: int, query: str, chunks_result: list, raw_items: list, metadata: dict):
    """
    儲存對話記錄到 agent_turns
    如果是新的 thread_id，也會在 agent_threads 建立記錄
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 檢查 thread_id 是否已存在於 agent_threads
        async with db.execute(
            "SELECT id FROM agent_threads WHERE thread_id = ?",
            (thread_id,)
        ) as cursor:
            thread_exists = await cursor.fetchone()

        if not thread_exists:
            # 建立新的 thread
            await db.execute(
                "INSERT INTO agent_threads (thread_id, user_id) VALUES (?, ?)",
                (thread_id, user_id)
            )
            print(f"Created new thread: {thread_id}")

        # 準備要儲存的資料
        raw_items_json = json.dumps(raw_items, ensure_ascii=False)
        output_json = json.dumps(chunks_result, ensure_ascii=False)
        metadata_json = json.dumps(metadata, ensure_ascii=False)

        # 插入新的 agent_turn
        await db.execute("""
            INSERT INTO agent_turns (thread_id, user_id, input, output, raw_items, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (thread_id, user_id, query, output_json, raw_items_json, metadata_json))

        await db.commit()
        print(f"Saved conversation to database for thread: {thread_id}")

def init_braintrust():
    global braintrust_logger, openai_client
    braintrust_logger = braintrust.init_logger(project=os.getenv("BRAINTRUST_PROJECT"))
    openai_client = braintrust.wrap_openai(AsyncOpenAI())
    set_default_openai_client(openai_client) # 設定 OpenAI Agents SDK 預設的 OpenAI Client 改用 braintrust 包裝過的版本
    return braintrust_logger, openai_client

tavily_client = None
def get_tavily_client():
    global tavily_client
    tavily_client = AsyncTavilyClient()
    return tavily_client

# Custom Agent Context
@dataclass
class CustomAgentContext:
    search_source: dict

# Function Tools
@function_tool
@braintrust.traced
async def knowledge_search(wrapper: RunContextWrapper[CustomAgentContext], query: str) -> str:
    """
    Search the web for information

    Args:
        query: The query keyword to search the web for.
    """

    print(f"  ⚙️ Calling knowledge_search with query: {query}")

    response = await get_tavily_client().search(query)

    wrapper.context.search_source[query] = response

    result = [ x["content"] for x in response["results"] ]

    print(f"  ⚙️ knowledge_search result: {result}")

    return str(result)

class GuardrailResult(BaseModel):
    is_investment_question: bool
    refusal_answer: str = Field(description="The answer to the user's question if is_investment_question is False, otherwise leave it blank.")

class ExtractFollowupQuestionsResult(BaseModel):
    followup_questions: list[str] = Field(description="3 follow-up questions exploring different aspects of the topic.")

# Agent Factory Functions
def create_guardrail_agent() -> Agent:
    """Create and return a guardrail agent instance"""
    return Agent(
        name="Guardrail Agent",
        instructions="""Your task is to determine if the user's question is related to investment or finance.
If yes, return "is_investment_question": true.
If not, return "is_investment_question": false and "refusal_answer": 解釋為何我不能回答這個問題. Always respond in Traditional Chinese.
""",
        model="gpt-4.1-mini",
        output_type=GuardrailResult,
    )

def create_followup_questions_agent() -> Agent:
    """Create and return a follow-up questions extraction agent instance"""
    return Agent(
        name="Extract Followup Questions Agent",
        instructions="""Your task is to extract 3 follow-up questions from the user's question and return them as "followup_questions": ["question1", "question2", "question3"].""",
        model="gpt-4.1",
        output_type=ExtractFollowupQuestionsResult,
    )

def create_lead_agent() -> Agent[CustomAgentContext]:
    """Create and return a lead agent instance"""
    today = datetime.now().strftime("%Y-%m-%d")
    return Agent[CustomAgentContext](
        name="Lead Agent",
        instructions=f"""You are a helpful assistant that can answer questions and help with tasks. Always respond in Traditional Chinese. Today's date is {today}.""",
        #tools=[knowledge_search],
        tools=[
            WebSearchTool(), 
            #FileSearchTool(
            #  max_num_results=5,
            #  vector_store_ids=[os.getenv("OPENAI_VECTOR_STORE_ID")],                
            #)
        ],
        model="gpt-5-mini",
        model_settings=ModelSettings(
            reasoning={
                "effort": "low",
                "summary": "auto"
            }
        )
    )

# Just for demo, not used in the actual system
@braintrust.traced
async def extract_user_background():
    await asyncio.sleep(2)

    background = """
User name: Foobar
User age: 30
User gender: Male
User occupation: Software Engineer
User income: 100000
User education: Bachelor's degree
User marital status: Married
User has children: Yes
User has pets: No
"""
    return background

@braintrust.traced
async def check_input_guardrail(input_items):
    input_guardrail_agent = create_guardrail_agent()

    result = await Runner.run(input_guardrail_agent, input=input_items)
    return result    