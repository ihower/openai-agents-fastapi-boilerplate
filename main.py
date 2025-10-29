from dotenv import load_dotenv
load_dotenv(".env", override=True)

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import braintrust

app = FastAPI()

# 掛載靜態文件目錄
app.mount("/static", StaticFiles(directory="static"), name="static")


from agents import Runner, trace, ItemHelpers
from custom_sqlite_session import CustomSQLiteSession
from agent_core import (
    CustomAgentContext,
    ExtractFollowupQuestionsResult,
    create_guardrail_agent,
    create_followup_questions_agent,
    create_lead_agent,
    init_braintrust
)

braintrust_logger, openai_client = init_braintrust()

@app.get("/api/v3/agent_stream")
async def get_agent_stream_v3(query: str, thread_id: str):
    response = StreamingResponse(generate_agent_stream_v3(query, thread_id), media_type="text/event-stream")
    response.headers["X-Accel-Buffering"] = "no"
    return response

async def generate_agent_stream_v3(query: str, thread_id: str):

    # Create agents using factory functions
    guardrail_agent = create_guardrail_agent()
    extract_followup_questions_agent = create_followup_questions_agent()
    lead_agent = create_lead_agent()

    session = CustomSQLiteSession(thread_id, "data/conversations.db", agent=lead_agent)
    custom_agent_context = CustomAgentContext(search_source={})

    chunks_result = []
    tags = []

    with braintrust_logger.start_span(name="agent_v3") as braintrust_span:        
        with trace("FastAPI Agent v3", trace_id=f"trace_{thread_id}"):

            braintrust_span.log(input={ "query": query },
                                metadata={ "thread_id": thread_id })

            result = await Runner.run(guardrail_agent, input=query)

            if not result.final_output.is_investment_question:
                content = { "content": result.final_output.refusal_answer }                
                yield f"data: {json.dumps(content)}\n\n"
                chunks_result.append(content)
                tags.append("gg") 
            else:

                follow_up_questions_task = asyncio.create_task(  Runner.run(extract_followup_questions_agent, input=query, session=session) )

                result = Runner.run_streamed(lead_agent, input=query, session=session, context=custom_agent_context)

                async for event in result.stream_events():
                    #print(event)

                    if event.type == "raw_response_event" and event.data.type == "response.output_text.delta":
                        #print(event.data.delta)
                        data = { "content": event.data.delta }
                        yield f"data: {json.dumps(data)}\n\n"

                    elif event.type == "raw_response_event" and event.data.type == "response.output_item.added" and event.data.item.type == "reasoning":
                        think_chunk = {
                            "message": "THINK_START",
                        }
                        yield f"data: {json.dumps(think_chunk)}\n\n"                                   
                        chunks_result.append(think_chunk)
                    elif event.type == "raw_response_event"  and event.data.type == "response.reasoning_summary_text.done":
                        think_chunk = {
                            "message": "THINK_TEXT",
                            "text": event.data.text
                        }
                        yield f"data: {json.dumps(think_chunk)}\n\n"   
                        chunks_result.append(think_chunk)
                    elif event.type == "raw_response_event" and event.data.type == "response.completed":
                        print("completed")          
                    elif event.type == "run_item_stream_event":
                        if event.item.type == "tool_call_item":
                            print("-- Tool was called")

                            if event.item.raw_item.type == "function_call":
                                tool_data = {'message': 'CALL_TOOL', 'tool_name': str(event.item.raw_item.name), 'arguments': str(event.item.raw_item.arguments)}
                            elif event.item.raw_item.type == "web_search_call": # build-in tool
                                tool_data = {'message': 'CALL_TOOL', 'tool_name': 'web_search_call'}

                            yield f"data: {json.dumps(tool_data)}\n\n"
                            chunks_result.append(tool_data)

                        elif event.item.type == "tool_call_output_item":
                            #print(f"-- Tool output: {event.item.output}")                            
                            print(f"search_source: {result.context_wrapper.context.search_source}") # 也可以看到最新更新後的 context (這個沒有傳給 LLM，只是我們內部用)

                        elif event.item.type == "message_output_item":
                            data = { "content": ItemHelpers.text_message_output(event.item) }
                            chunks_result.append(data)
                        else:
                            pass  # Ignore other event types          

                follow_up_questions_result = await follow_up_questions_task
                questions = follow_up_questions_result.final_output_as(ExtractFollowupQuestionsResult).followup_questions
                data = { "following_questions": questions }
        
                yield f"data: {json.dumps(data)}\n\n"
                chunks_result.append(data)

            done_event = { "message": "DONE" }
            yield f"data: {json.dumps(done_event)}\n\n"
            chunks_result.append(done_event)

            token_usage = result.context_wrapper.usage
            braintrust_span.log(output={ "chunks": chunks_result }, tags=tags, metadata={ "token_usage": token_usage })

                            
    print(f"result: {result.context_wrapper}")