import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.agents import AgentState, create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command
from tavily import TavilyClient

load_dotenv()
DB_PATH = Path(__file__).resolve().parent.parent / "resources" / "Chinook.db"


class WeddingState(AgentState):
    origin: str
    destination: str
    guest_count: str
    genre: str


def make_model():
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("Set GROQ_API_KEY in .env or your deployment secrets")
    return init_chat_model(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        model_provider="openai",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0,
        max_completion_tokens=2048,
        model_kwargs={"parallel_tool_calls": False},
    )


@tool
def web_search(query: str) -> dict[str, Any]:
    """Find current wedding venues and related information on the web."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return {"error": "TAVILY_API_KEY is not configured"}
    return TavilyClient(api_key=key).search(query, max_results=5)


@tool
def query_playlist_db(query: str) -> str:
    """Run a read-only SELECT query on the Chinook music catalog; limit results."""
    statement = query.strip().rstrip(";").strip()
    # This is defense in depth: SQLite read-only URI + query_only PRAGMA also apply.
    if not re.match(r"(?is)^select\s", statement) or ";" in statement:
        return "Only one SELECT statement is permitted."
    try:
        uri = f"file:{DB_PATH.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.set_progress_handler(lambda: 1, 200000)  # abort overly costly queries
            cur = conn.execute(f"SELECT * FROM ({statement}) LIMIT 30")
            rows = cur.fetchall()
            return str({"columns": [d[0] for d in cur.description], "rows": rows})[:5000]
    except sqlite3.Error as exc:
        return f"Database query failed: {exc}"


@tool
async def find_flights(origin: str, destination: str) -> str:
    """Search available one-way economy flights using the Kiwi MCP flight search tool."""
    client = MultiServerMCPClient({
        "travel_server": {
            "transport": "streamable_http",
            "url": os.getenv("KIWI_MCP_URL", "https://mcp.kiwi.com"),
        }
    })
    try:
        flight_tools = [t for t in await client.get_tools() if t.name == "search-flight"]
        if not flight_tools:
            return "Kiwi MCP search-flight tool unavailable. Do not invent flight prices."
        specialist = create_agent(
            model=model,
            tools=flight_tools,
            system_prompt=(
                "You are a travel specialist. Find one-way economy flight options "
                "for one traveler. Compare price and duration. If travel dates "
                "are unknown, clearly state that real quotes require dates. "
                "Never invent prices, schedules, or availability."
            ),
        )
        result = await specialist.ainvoke({"messages": [HumanMessage(content=f"Find flights from {origin} to {destination}.")]})
        return str(result["messages"][-1].content)[:5000]
    except Exception as exc:
        return f"Flight search temporarily unavailable ({type(exc).__name__})."


model = make_model()
venue_agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt=("You are a wedding venue specialist. Search for venues in the "
                   "requested destination and capacity. Distinguish verified "
                   "details from estimates; never claim a booking is confirmed."),
)
playlist_agent = create_agent(
    model=model,
    tools=[query_playlist_db],
    system_prompt=("You are a wedding playlist specialist. Use the Chinook "
                   "SQLite catalog to suggest tracks for the requested genre. "
                   "Only recommend tracks returned by the database."),
)


@tool
async def search_flights(runtime: ToolRuntime) -> str:
    """Delegate flight search using the saved wedding origin and destination."""
    state = runtime.state
    return await find_flights.ainvoke({"origin": state["origin"], "destination": state["destination"]})


@tool
async def search_venues(runtime: ToolRuntime) -> str:
    """Find wedding venues for the saved destination and guest count."""
    state = runtime.state
    response = await venue_agent.ainvoke({"messages": [HumanMessage(content=(
        f"Find wedding venues in {state['destination']} for {state['guest_count']} guests."
    ))]})
    return str(response["messages"][-1].content)[:5000]


@tool
async def suggest_playlist(runtime: ToolRuntime) -> str:
    """Curate wedding music from the saved genre using the Chinook database."""
    response = await playlist_agent.ainvoke({"messages": [HumanMessage(content=(
        f"Find tracks in the Chinook database for a {runtime.state['genre']} wedding playlist."
    ))]})
    return str(response["messages"][-1].content)[:5000]


@tool
def update_state(origin: str, destination: str, guest_count: str, genre: str, runtime: ToolRuntime) -> Command:
    """Save the four wedding preferences; call alone before specialist tools."""
    return Command(update={
        "origin": origin,
        "destination": destination,
        "guest_count": guest_count,
        "genre": genre,
        "messages": [ToolMessage(content="Wedding preferences saved.", tool_call_id=runtime.tool_call_id)],
    })


graph = create_agent(
    model=model,
    tools=[update_state, search_flights, search_venues, suggest_playlist],
    state_schema=WeddingState,
    system_prompt=(
        """
    You are an expert AI Wedding Coordinator.

    Your job is to coordinate a complete wedding plan using
    the available specialist agents.

    Required information:
    - origin
    - destination
    - guest_count
    - genre

    Rules:

    1. Collect only the four required fields.
    2. If all four fields are available, do not ask additional questions.
    3. Call update_state first.
    4. Wait until update_state completes successfully.
    5. Then call all three specialist tools:
       - search_flights
       - search_venues
       - suggest_playlist
    6. The travel agent will choose a suitable travel date. Do not ask the user for departure or return dates.
    7. Do not invent flight prices, venues, or songs.
    8. If a specialist tool fails, explain the failure and continue with the remaining specialists.
    9. After receiving the results, generate a complete wedding plan.

    Your final response must include:
      - Wedding destination
      - Guest count
      - Flight options
      - Wedding venues
      - Romantic wedding playlist
      - Final recommendations
   """
    ),
)
