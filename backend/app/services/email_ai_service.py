import json
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.email_account import EmailDraft, EmailConversation, EmailConversationMessage
from app.services.email_compose_service import create_draft, send_draft


EMAIL_GENERATION_PROMPT = """You are an expert B2B email copywriter for {company_name}.
Your task is to write a professional, personalized outreach email.

Company context:
- Company: {company_name}
- Services: {services}
- USP: {usp}
- Industry: {industry}

Target lead:
- Name: {lead_name}
- Company: {lead_company}
- Email: {lead_email}

Instructions:
1. Write a compelling subject line
2. Write a personalized email body (3-5 paragraphs)
3. Keep it professional but friendly
4. Include a clear call-to-action
5. Make it feel personal, not spammy

Return JSON format:
{{
    "subject": "email subject line",
    "body": "email body in HTML format"
}}"""


async def generate_email_with_ai(
    prompt: str,
    lead_name: str = "",
    lead_company: str = "",
    lead_email: str = "",
    company_name: str = "Crawlio",
    services: str = "B2B lead generation and email automation",
    usp: str = "AI-powered outreach that converts",
    industry: str = "SaaS",
) -> dict:
    if not settings.mistral_api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    full_prompt = EMAIL_GENERATION_PROMPT.format(
        company_name=company_name,
        services=services,
        usp=usp,
        industry=industry,
        lead_name=lead_name,
        lead_company=lead_company,
        lead_email=lead_email,
    )

    payload = {
        "model": "mistral-small-latest",
        "messages": [
            {"role": "system", "content": full_prompt},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


async def generate_email_draft(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    prompt: str,
    lead_id: Optional[str] = None,
    lead_name: str = "",
    lead_company: str = "",
    lead_email: str = "",
) -> EmailDraft:
    result = await generate_email_with_ai(
        prompt=prompt,
        lead_name=lead_name,
        lead_company=lead_company,
        lead_email=lead_email,
    )

    draft = await create_draft(
        session=session,
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        subject=result.get("subject", ""),
        body=result.get("body", ""),
        kind="ai_generated",
        recipient_emails=[lead_email] if lead_email else None,
        lead_id=lead_id,
        ai_prompt=prompt,
    )
    return draft


async def approve_and_send_ai_email(
    session: AsyncSession, draft_id: str
) -> Optional[dict]:
    result = await session.execute(select(EmailDraft).where(EmailDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.kind != "ai_generated":
        return None

    email_message = await send_draft(session, draft_id)
    return {"draft_id": draft.id, "email_message_id": email_message.id if email_message else None}


async def initialize_agent_session(
    session: AsyncSession,
    workspace_id: str,
    email_account_id: str,
    lead_id: Optional[str] = None,
    subject: str = "Outreach Conversation",
) -> EmailConversation:
    conversation = EmailConversation(
        workspace_id=workspace_id,
        email_account_id=email_account_id,
        lead_id=lead_id,
        subject=subject,
        status="active",
        ai_agent_active=True,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_agent_conversation_history(
    session: AsyncSession, conversation_id: str
) -> list[EmailConversationMessage]:
    result = await session.execute(
        select(EmailConversationMessage)
        .where(EmailConversationMessage.conversation_id == conversation_id)
        .order_by(EmailConversationMessage.created_at)
    )
    return list(result.scalars().all())


async def agent_collect_business_info(
    session: AsyncSession, conversation_id: str, user_input: str
) -> str:
    conversation_result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = conversation_result.scalar_one_or_none()
    if not conversation:
        raise RuntimeError("Conversation not found")

    user_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="user",
        content=user_input,
    )
    session.add(user_msg)

    existing_context = conversation.business_context or ""
    conversation.business_context = f"{existing_context}\nUser: {user_input}".strip()
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    ai_response = f"Samajh gaya! Maine ye note kar liya hai: {user_input}. Koi aur detail hai jo aap share karna chahenge?"

    ai_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="ai",
        content=ai_response,
    )
    session.add(ai_msg)
    await session.commit()
    return ai_response


async def agent_generate_outreach(
    session: AsyncSession, conversation_id: str
) -> EmailDraft:
    conv_result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise RuntimeError("Conversation not found")

    business_context = conversation.business_context or "No business context provided"

    ai_result = await generate_email_with_ai(
        prompt=f"Generate outreach email based on this business context: {business_context}",
        company_name="Crawlio",
        services="B2B lead generation",
        usp="AI-powered outreach",
    )

    draft = await create_draft(
        session=session,
        workspace_id=conversation.workspace_id,
        email_account_id=conversation.email_account_id,
        subject=ai_result.get("subject", ""),
        body=ai_result.get("body", ""),
        kind="ai_generated",
        lead_id=conversation.lead_id,
        ai_prompt=business_context,
        conversation_id=conversation_id,
    )

    preview_msg = EmailConversationMessage(
        conversation_id=conversation_id,
        sender_type="ai",
        content=f"Maine outreach email generate kar diya hai. Subject: {draft.subject}",
    )
    session.add(preview_msg)
    await session.commit()

    return draft


async def agent_stop_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        return False

    conversation.ai_agent_active = False
    conversation.status = "paused"
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await session.commit()
    return True


async def agent_resume_conversation(
    session: AsyncSession, conversation_id: str
) -> bool:
    result = await session.execute(
        select(EmailConversation).where(EmailConversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        return False

    conversation.ai_agent_active = True
    conversation.status = "active"
    conversation.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    await session.commit()
    return True
