from dotenv import load_dotenv
load_dotenv(".env", override=True)

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
import braintrust
from dataclasses import asdict

app = FastAPI()

# 掛載靜態文件目錄
app.mount("/static", StaticFiles(directory="static"), name="static")


from agents import Runner, trace, ItemHelpers
from agent_core import (
    CustomAgentContext,
    ExtractFollowupQuestionsResult,
    create_followup_questions_agent,
    create_lead_agent,
    init_braintrust,
    check_input_guardrail,
    extract_user_background,
    get_previous_items,
    save_agent_turn
)

braintrust_logger, openai_client = init_braintrust()

@app.get("/api/v3/agent_stream")
async def get_agent_stream_v3(query: str, thread_id: str):
    response = StreamingResponse(generate_agent_stream_v3(query, thread_id), media_type="text/event-stream")
    response.headers["X-Accel-Buffering"] = "no"
    return response

async def generate_agent_stream_v3(query: str, thread_id: str, user_id: int = 1):
    # Create agents using factory functions
    extract_followup_questions_agent = create_followup_questions_agent()
    lead_agent = create_lead_agent()

    # 從資料庫讀取歷史對話
    input_items = await get_previous_items(thread_id)
    all_input_items = input_items + [{ "role": "user", "content": query }]

    custom_agent_context = CustomAgentContext(search_source={})

    chunks_result = []
    tags = []
    last_token_usage = {}

    with braintrust_logger.start_span(name="agent_v3") as braintrust_span:
        with trace("FastAPI Agent v3", trace_id=f"trace_{thread_id}"):

            braintrust_span.log(input={ "query": query },
                                metadata={ "thread_id": thread_id })

            async with asyncio.TaskGroup() as tg:
                ta = tg.create_task( check_input_guardrail(all_input_items) ) # Need check whole conversation history
                tb = tg.create_task( extract_user_background() )

            result = ta.result()

            if not result.final_output.is_investment_question:
                content = { "content": result.final_output.refusal_answer }
                yield f"data: {json.dumps(content)}\n\n"
                chunks_result.append(content)
                tags.append("gg")
            else:

                background_data = tb.result()
                print(f"background_data: {background_data}")

                follow_up_questions_task = asyncio.create_task(
                    Runner.run(extract_followup_questions_agent, input=all_input_items)
                )

                result = Runner.run_streamed(lead_agent, input=all_input_items, context=custom_agent_context)

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

                        last_response_id = event.data.response.id 
                        last_prompt_cache_hit_ratio = round((event.data.response.usage.input_tokens_details.cached_tokens / event.data.response.usage.input_tokens) * 100, 2)

                        last_token_usage = {
                            "input_tokens": event.data.response.usage.input_tokens,
                            "cached_tokens": event.data.response.usage.input_tokens_details.cached_tokens,
                            "output_tokens": event.data.response.usage.output_tokens,
                            "reasoning_tokens": event.data.response.usage.output_tokens_details.reasoning_tokens,
                            "total_tokens": event.data.response.usage.total_tokens,
                            "prompt_cache_hit_ratio": last_prompt_cache_hit_ratio
                        }                                            
                                                
                    elif event.type == "run_item_stream_event":
                        if event.item.type == "tool_call_item":
                            print("-- Tool was called")
                            #print(event.item.raw_item)

                            if event.item.raw_item.type == "function_call":
                                tool_data = {'message': 'CALL_TOOL', 'tool_name': str(event.item.raw_item.name), 'arguments': str(event.item.raw_item.arguments)}
                            elif event.item.raw_item.type == "web_search_call": # build-in tool
                                tool_data = {'message': 'CALL_TOOL', 'tool_name': 'web_search_call', 'arguments': event.item.raw_item.action.query }
                            elif event.item.raw_item.type == "file_search_call": # build-in tool
                                tool_data = {'message': 'CALL_TOOL', 'tool_name': 'file_search_call', 'arguments': event.item.raw_item.queries }

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

            # 儲存對話到資料庫
            raw_items = [json.dumps(item) for item in result.to_input_list()]
            token_usage = result.context_wrapper.usage
            metadata = {
                #"token_usage": asdict(token_usage),
                "last_token_usage": last_token_usage,
                "tags": tags
            }
            await save_agent_turn(thread_id, user_id, query, chunks_result, raw_items, metadata)

            braintrust_span.log(output={ "chunks": chunks_result }, tags=tags, metadata={ "total_token_usage": token_usage, "last_token_usage": last_token_usage })


    print(f"result: {result.context_wrapper}")