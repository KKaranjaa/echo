import os
import json
from django.http import StreamingHttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from apps.uploads.models import Session
from apps.transcription.models import Transcript
from apps.summarisation.models import Summary
from .models import ChatMessage
from .rag import retrieve_relevant_chunks
from groq import Groq
import anthropic
from google import genai as google_genai

SYSTEM_PROMPT_TEMPLATE = """You are ECHO, an AI academic assistant. You have access to the transcript,
summary, and key points from a specific lecture or study session.

Your role: act as a helpful tutor and assistant.
- Prioritize the session's content when answering questions directly related to the lecture. Be specific and cite relevant parts of the session.
- If the user asks a question not explicitly covered in the transcript, or asks for general knowledge, feel free to use your broader knowledge base to provide a helpful answer.
- When drawing on general knowledge outside the provided transcript, clearly distinguish it from the session content (e.g., "While this wasn't covered in the lecture, generally...").
- Keep answers concise — 1-3 short paragraphs max.
- Use the same language as the session.

Session summary:
{summary_paragraph}

Key points:
{key_points_joined}

Relevant transcript excerpts (for reference):
{transcript_text}"""

GROQ_CHAT_MODEL = "llama-3.1-8b-instant"


def chat_page(request):
    """Full-page chat view. Expects ?session=<uuid> and optional ?q=<question>."""
    session_id = request.GET.get('session')
    if not session_id:
        return HttpResponseBadRequest('Missing session parameter.')
    session = get_object_or_404(Session, id=session_id)
    try:
        summary = Summary.objects.get(session=session)
    except Summary.DoesNotExist:
        summary = None
    initial_question = request.GET.get('q', '')
    return render(request, 'chat/chat_page.html', {
        'session': session,
        'summary': summary,
        'initial_question': initial_question,
    })


@csrf_exempt
@require_POST
def chat_api(request, session_id):
    try:
        session = Session.objects.get(id=session_id)
        transcript = Transcript.objects.get(session=session)
        summary = Summary.objects.get(session=session)
    except (Session.DoesNotExist, Transcript.DoesNotExist, Summary.DoesNotExist):
        return HttpResponseBadRequest("Session, transcript, or summary not found.")

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest(
            json.dumps({"error": "Invalid JSON."}),
            content_type="application/json"
        )

    user_message = data.get('message')
    if not user_message:
        return HttpResponseBadRequest(
            json.dumps({"error": "Message is required."}),
            content_type="application/json"
        )

    # Save user message
    ChatMessage.objects.create(session=session, role='user', content=user_message)

    # Build system prompt
    key_points_joined = "\n".join(summary.key_points) if summary.key_points else ""
    
    # Build message history (includes the just-saved user message)
    # Limit to last 6 messages (3 turns) to prevent token bloat
    history = list(ChatMessage.objects.filter(session=session).order_by('-created_at')[:6])
    messages = [{"role": msg.role, "content": msg.content} for msg in reversed(history)]
    
    # Retrieve relevant chunks using RAG (BM25)
    # Combine previous message context if available to improve search
    search_query = user_message
    if len(messages) > 0:
        search_query = f"{messages[-1]['content']} {user_message}"
    
    relevant_excerpts = retrieve_relevant_chunks(search_query, transcript.raw_text, top_k=2)
    
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        summary_paragraph=summary.summary_paragraph,
        key_points_joined=key_points_joined,
        transcript_text=relevant_excerpts,
    )

    # Build full messages array
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    def event_stream():
        full_response = []
        
        # 1. TRY GROQ
        groq_api_key = os.environ.get('GROQ_API_KEY')
        if groq_api_key:
            client = Groq(api_key=groq_api_key)
            try:
                stream = client.chat.completions.create(
                    model=GROQ_CHAT_MODEL,
                    max_tokens=1000,
                    messages=full_messages,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        text = delta.content
                        full_response.append(text)
                        yield f"data: {json.dumps({'chunk': text})}\n\n"
                        
                assistant_text = "".join(full_response)
                ChatMessage.objects.create(session=session, role='assistant', content=assistant_text)
                yield f"data: {json.dumps({'done': True})}\n\n"
                return  # Success, exit stream
            except Exception as e:
                print(f"Groq API failed: {e}. Falling back to Anthropic...")
        
        # 2. FALLBACK TO ANTHROPIC
        anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
        if anthropic_api_key:
            try:
                client = anthropic.Anthropic(api_key=anthropic_api_key)
                
                # Anthropic handles system prompt differently
                anthropic_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
                
                with client.messages.stream(
                    max_tokens=1000,
                    system=system_prompt,
                    messages=anthropic_messages,
                    model="claude-3-5-sonnet-20241022",
                ) as stream:
                    for text in stream.text_stream:
                        full_response.append(text)
                        yield f"data: {json.dumps({'chunk': text})}\n\n"
                        
                assistant_text = "".join(full_response)
                ChatMessage.objects.create(session=session, role='assistant', content=assistant_text)
                yield f"data: {json.dumps({'done': True})}\n\n"
                return  # Success, exit stream
            except Exception as e:
                print(f"Anthropic API failed: {e}. Falling back to Gemini...")

        # 3. FALLBACK TO GEMINI
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        if gemini_api_key:
            try:
                client = google_genai.Client(api_key=gemini_api_key)

                # Build contents list for Gemini (user/model roles)
                gemini_contents = []
                for m in messages:
                    role = 'model' if m['role'] == 'assistant' else 'user'
                    gemini_contents.append({"role": role, "parts": [{"text": m['content']}]})

                response = client.models.generate_content_stream(
                    model='gemini-1.5-pro',
                    contents=gemini_contents,
                    config={"system_instruction": system_prompt},
                )

                for chunk in response:
                    text = chunk.text
                    if text:
                        full_response.append(text)
                        yield f"data: {json.dumps({'chunk': text})}\n\n"

                assistant_text = "".join(full_response)
                ChatMessage.objects.create(session=session, role='assistant', content=assistant_text)
                yield f"data: {json.dumps({'done': True})}\n\n"
                return  # Success, exit stream
            except Exception as e:
                print(f"Gemini API failed: {e}.")
                
        # 4. IF ALL FAIL
        error_msg = "I'm sorry, all of our AI providers are currently experiencing rate limits or downtime. Please try again later."
        yield f"data: {json.dumps({'chunk': error_msg})}\n\n"
        ChatMessage.objects.create(session=session, role='assistant', content=error_msg)
        yield f"data: {json.dumps({'done': True})}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
