import streamlit as st
import tempfile
import asyncio
import json
import re
import traceback

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

from tavily import TavilyClient

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.llms import Ollama

# Google Calendar MCP integration
from mcp_integration import call_calendar_tool
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI API_KEY")
)

tavily = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)



# --------------------------------------------------
# 1. CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="PDF Chatbot",
    page_icon="🤖",
    layout="wide"
)

# Use your actual API keys in your local file.
# Never share your API keys publicly.

client = genai.Client(
    api_key="AQ.Ab8RN6J6U0QtwGWSgqHHGppMz5kLVgdy3gsDybfUgm_6tsewBg"
)
try:
    test = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Reply with OK"
    )
    print("GEMINI TEST SUCCESS:", test.text)

except Exception as e:
    print("GEMINI TEST FAILED:", repr(e))

tavily = TavilyClient(
    api_key="YOUR_TAVILY_API_KEY"
)


# --------------------------------------------------
# 2. LOAD EMBEDDINGS
# --------------------------------------------------

@st.cache_resource
def load_embeddings():
    return HuggingFaceEmbeddings()


# --------------------------------------------------
# 3. CALENDAR QUESTION DETECTION
# --------------------------------------------------

def detect_calendar_request(question):

    if not isinstance(question, str) or not question.strip():
        return False

    q = question.lower()

    calendar_keywords = [
        "calendar",
        "meeting",
        "meetings",
        "event",
        "events",
        "schedule",
        "appointment",
        "appointments",
        "standup",
        "stand-up",
        "upcoming events",
        "upcoming meetings",
        "my next event",
        "my next meeting"
    ]

    return any(word in q for word in calendar_keywords)


# --------------------------------------------------
# 4. GET CALENDAR EVENTS THROUGH MCP
# --------------------------------------------------

def get_calendar_events(question):

    if not isinstance(question, str) or not question.strip():
        return "Please enter a valid calendar question."

    q = question.lower()

    max_results = 10

    number_match = re.search(
        r"(?:next|show|last|upcoming)\s+(\d+)",
        q
    )

    if number_match:
        max_results = min(
            max(int(number_match.group(1)), 1),
            50
        )

    try:

        result = asyncio.run(
            call_calendar_tool(
                "get_events",
                {"max_results": max_results}
            )
        )

        events = json.loads(result)

        india_tz = ZoneInfo("Asia/Kolkata")

        today = datetime.now(india_tz).date()

        target_date = None

        if "tomorrow" in q:
            target_date = today + timedelta(days=1)

        elif "today" in q:
            target_date = today

        # Filter events by date

        if target_date:

            filtered_events = []

            for event in events:

                start_info = event.get("start", {})

                start_value = (
                    start_info.get("dateTime")
                    or start_info.get("date")
                )

                if not start_value:
                    continue

                if "T" in start_value:

                    event_date = datetime.fromisoformat(
                        start_value.replace("Z", "+00:00")
                    ).astimezone(india_tz).date()

                else:

                    event_date = datetime.fromisoformat(
                        start_value
                    ).date()

                if event_date == target_date:
                    filtered_events.append(event)

            events = filtered_events

        if not events:
            return "No upcoming calendar events found."

        output = []

        for event in events:

            summary = event.get(
                "summary",
                "Untitled event"
            )

            start_info = event.get("start", {})
            end_info = event.get("end", {})

            start_value = (
                start_info.get("dateTime")
                or start_info.get("date")
            )

            end_value = (
                end_info.get("dateTime")
                or end_info.get("date")
            )

            # Format start time

            if start_value and "T" in start_value:

                start_dt = datetime.fromisoformat(
                    start_value.replace("Z", "+00:00")
                )

                start_text = start_dt.astimezone(
                    india_tz
                ).strftime("%d-%m-%Y %I:%M %p")

            elif start_value:

                start_text = f"{start_value} (All day)"

            else:

                start_text = "Not available"

            # Format end time

            if end_value and "T" in end_value:

                end_dt = datetime.fromisoformat(
                    end_value.replace("Z", "+00:00")
                )

                end_text = end_dt.astimezone(
                    india_tz
                ).strftime("%I:%M %p")

            else:

                end_text = "Not available"

            location = event.get(
                "location",
                "Not specified"
            )

            meet_link = ""

            for entry in event.get(
                "conferenceData", {}
            ).get("entryPoints", []):

                if entry.get("entryPointType") == "video":

                    meet_link = entry.get("uri", "")

            output.append(
                f"""
📅 **{summary}**

- Start: {start_text}
- End: {end_text}
- Location: {location}
- Google Meet: {meet_link or 'Not available'}
"""
            )

        return "\n".join(output)

    except Exception as e:

        return f"Google Calendar error: {str(e)}"


# --------------------------------------------------
# 4A. UNDERSTAND MEETING REQUEST USING GEMINI
# --------------------------------------------------



    

def understand_meeting_request(question):
    try:
        timezone = ZoneInfo("Asia/Kolkata")
        current_date = datetime.now(timezone).date()

        # Extract meeting title
        title_match = re.search(
            r"called\s+(.+?)(?=\s+(?:on|today|tomorrow|at)\b)",
            question,
            re.IGNORECASE
        )

        title = title_match.group(1).strip() if title_match else "Meeting Schedule"

        # Extract meeting date
        if re.search(r"\btomorrow\b", question, re.IGNORECASE):
            meeting_date = current_date + timedelta(days=1)

        elif re.search(r"\btoday\b", question, re.IGNORECASE):
            meeting_date = current_date

        else:
            date_match = re.search(
                r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",
                question,
                re.IGNORECASE
            )

            if not date_match:
                return None

            date_text = date_match.group(1)

            if re.match(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", date_text):
                separator = "." if "." in date_text else "/" if "/" in date_text else "-"
                day, month, year = date_text.split(separator)

                if len(year) == 2:
                    year = "20" + year

                meeting_date = datetime(
                    int(year),
                    int(month),
                    int(day)
                ).date()

            else:
                meeting_date = datetime.strptime(
                    date_text,
                    "%d %B %Y"
                ).date()

        # Extract time (supports 10AM and 10 AM)
        time_match = re.search(
            r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b",
            question,
            re.IGNORECASE
        )

        if not time_match:
            return None

        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridian = time_match.group(3).upper()

        if hour < 1 or hour > 12 or minute > 59:
            return None

        if meridian == "PM" and hour != 12:
            hour += 12
        elif meridian == "AM" and hour == 12:
            hour = 0

        start = datetime(
            meeting_date.year,
            meeting_date.month,
            meeting_date.day,
            hour,
            minute,
            tzinfo=timezone
        )

        # Extract duration
        duration_match = re.search(
            r"for\s+(\d+)\s+minutes?",
            question,
            re.IGNORECASE
        )

        duration = int(duration_match.group(1)) if duration_match else 30

        if duration <= 0:
            return None

        end = start + timedelta(minutes=duration)

        return {
            "summary": title,
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
            "description": "Created using AI PDF Chatbot",
            "location": "",
            "attendees": [],
            "create_meet_link": True
        }

    except Exception as e:
        print("Meeting parsing error:", e)
        return None


# --------------------------------------------------
# 4B. CREATE GOOGLE CALENDAR MEETING THROUGH MCP
# --------------------------------------------------


def create_calendar_event(question):

    try:
        details = understand_meeting_request(question)

        if not details:
            return "Could not understand meeting details."

        title = details["summary"]

        start_datetime = datetime.fromisoformat(
            details["start_datetime"]
        )

        end_datetime = datetime.fromisoformat(
            details["end_datetime"]
        )

        result = asyncio.run(
            call_calendar_tool(
                "create_event",
                {
                    "summary": title,
                    "start_datetime": start_datetime.isoformat(),
                    "end_datetime": end_datetime.isoformat(),
                    "description": details.get("description", ""),
                    "location": details.get("location", ""),
                    "attendees": details.get("attendees", []),
                    "create_meet_link": True
                }
            )
        )

        event = json.loads(result)

        if event.get("status") != "success":
            return f"Meeting creation failed: {event}"

        return f"""
### Meeting created successfully!

**Title:** {title}

**Start:** {start_datetime.strftime('%d-%m-%Y %I:%M %p')}

**End:** {end_datetime.strftime('%I:%M %p')}

**Google Meet:** {event.get('google_meet_link', 'Not available')}

**Google Calendar:** {event.get('htmlLink', event.get('calendar_link', 'Not available'))}
 """                                                                                                                           
    except Exception as e:
        traceback.print_exc()
        return f"Meeting creation error: {repr(e)}"


# --------------------------------------------------
# 5. SIDEBAR
# --------------------------------------------------


with st.sidebar:

    st.title("⚙️ Settings")

    uploaded_file = st.file_uploader(
        "📄 Upload PDF",
        type="pdf"
    )

    web_toggle = st.toggle(
        "🌐 Enable Web Search"
    )

    st.markdown("---")

    st.markdown(
        "🚀 Built by Keerthana Lakshmanan"
    )


# --------------------------------------------------
# 6. MAIN UI
# --------------------------------------------------

st.title("🤖 AI PDF Chatbot")

st.caption(
    "Ask questions from PDF, Web, Google Calendar or general knowledge."
)


# --------------------------------------------------
# 7. PDF PROCESSING
# --------------------------------------------------

retriever = None

if uploaded_file is not None:

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as tmp_file:

            tmp_file.write(
                uploaded_file.getvalue()
            )

            file_path = tmp_file.name

        loader = PyPDFLoader(file_path)

        documents = loader.load()

        if not documents:

            st.error("Could not read the PDF.")

        elif not any(
            doc.page_content.strip()
            for doc in documents
        ):

            st.error(
                "No text could be extracted from this PDF. "
                "It may be scanned or image-based."
            )

        else:

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

            chunks = splitter.split_documents(
                documents
            )

            embeddings = load_embeddings()

            vectorstore = FAISS.from_documents(
                chunks,
                embeddings
            )

            retriever = vectorstore.as_retriever(
                search_kwargs={"k": 4}
            )

            st.success(
                f"PDF Loaded Successfully! "
                f"Pages: {len(documents)} | Chunks: {len(chunks)}"
            )

    except Exception as e:

        st.error(f"PDF processing error: {e}")


# --------------------------------------------------
# 8. CHAT INPUT
# --------------------------------------------------

query = st.chat_input(
    "Ask your question..."
)


# --------------------------------------------------
# 9. PROCESS USER QUESTION
# --------------------------------------------------

if query:

    # Display user question

    with st.chat_message("user"):

        st.write(query)

    answer = ""

    # ----------------------------------------------
    # ROUTE 1: GOOGLE CALENDAR MCP
    # ----------------------------------------------

    if detect_calendar_request(query):

        with st.chat_message("assistant"):

            # Check whether the user wants to create a meeting

            if re.search(
                r"\b(create|schedule|book|add)\b",
                query,
                re.IGNORECASE
            ):

                with st.spinner(
                    "Understanding and creating meeting..."
                ):

                    answer = create_calendar_event(query)

            else:

                with st.spinner(
                    "Fetching Google Calendar events..."
                ):

                    answer = get_calendar_events(query)

            st.markdown(answer)

    # ----------------------------------------------
    # ROUTE 2: PDF RAG, WEB SEARCH AND GENERAL CHAT
    # ----------------------------------------------

    else:

        pdf_context = ""

        # Search uploaded PDF

        if retriever is not None:

            if isinstance(query, str) and query.strip():

                docs = retriever.invoke(query)

            else:

                st.warning("Please enter a valid question.")

                st.stop()

            relevant_text = " ".join(
                [doc.page_content for doc in docs]
            ).lower()

            query_words = re.findall(
                r'\w+',
                query.lower()
            )

            match_count = sum(
                word in relevant_text
                for word in query_words
            )

            if match_count >= max(
                2,
                len(query_words) // 2
            ):

                pdf_context = "\n".join(
                    [doc.page_content for doc in docs]
                )

        # If PDF exists but answer is not found

        if (
            uploaded_file is not None
            and not pdf_context.strip()
            and not web_toggle
        ):

            with st.chat_message("assistant"):

                st.write(
                    "Not found in the uploaded document."
                )

        else:

            # --------------------------------------
            # ROUTE 3: TAVILY WEB SEARCH
            # --------------------------------------

            web_context = ""

            if web_toggle and tavily is not None:

                try:

                    web_results = tavily.search(
                        query=query
                    )

                    for result in web_results["results"][:3]:

                        content = result.get(
                            "content",
                            ""
                        )

                        if len(content.strip()) > 50:

                            web_context += (
                                content[:800] + "\n"
                            )

                except Exception as e:

                    st.warning(
                        f"Web search error: {e}"
                    )

            # --------------------------------------
            # ROUTE 4: GEMINI + OLLAMA
            # --------------------------------------

            final_context = (
                pdf_context + "\n" + web_context
            )[:5000]

            system_prompt = """
You are an AI assistant and PDF chatbot.

Instructions:

- Answer greetings naturally.
- Use PDF context when available.
- Use web context when available.
- If context is unavailable, answer using general knowledge.
- Give clear and complete answers.
- Do not invent information from the PDF.
"""

            prompt = f"""
{system_prompt}

Context:
{final_context}

User Question:
{query}

Answer:
"""

            with st.chat_message("assistant"):

                with st.spinner("Thinking..."):

                    try:

                        response = client.models.generate_content(
                           model="gemini-3.8-flash",  
                            contents=prompt
                        )

                        answer = response.text or "No response received."

                    except Exception as e:

                        st.warning(
                            "Gemini unavailable. "
                            "Trying local Ollama model."
                        )

                        try:

                            ollama_model = Ollama(
                                model="mistral"
                            )

                            answer = ollama_model.invoke(
                                prompt
                            )

                        except Exception as ollama_error:

                            answer = (
                                f"Gemini error: {e}\n\n"
                                f"Ollama error: {ollama_error}"
                            )

                st.write(answer)


# --------------------------------------------------
# 10. FOOTER
# --------------------------------------------------

st.markdown("---")

st.markdown(
    "Powered by Gemini + FAISS + Tavily + Ollama + Google Calendar MCP"
)
