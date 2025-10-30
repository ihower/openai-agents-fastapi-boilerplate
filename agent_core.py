from dataclasses import dataclass
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool, RunContextWrapper, ModelSettings, set_default_openai_client,  WebSearchTool, FileSearchTool
from tavily import AsyncTavilyClient
from datetime import datetime
from openai import AsyncOpenAI
import braintrust
import os
import asyncio

braintrust_logger = None
openai_client = None

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
    await asyncio.sleep(3)

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