import base64
import json

import respx
from httpx import Response


async def test_reply_requires_conversation_id_in_body(client_factory):
    async with client_factory("user_reply") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.post(
            "/api/v1/email-conversations/conv-123/reply",
            json={"message": "hi"},
        )
    assert resp.status_code == 422


async def test_reply_with_full_payload_passes_validation(client_factory):
    async with client_factory("user_reply2") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.post(
            "/api/v1/email-conversations/conv-123/reply",
            json={"conversation_id": "conv-123", "message": "hi", "sender_type": "user"},
        )
    assert resp.status_code == 404  # validation passed, conversation not found


async def test_business_info_requires_email_account_and_conversation_ids(client_factory):
    async with client_factory("user_biz") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.post(
            "/api/v1/email-conversations/conv-123/business-info",
            json={"business_name": "Acme", "business_subject": "Plumbing"},
        )
    assert resp.status_code == 422


async def test_business_info_with_full_payload_passes_validation(client_factory):
    async with client_factory("user_biz2") as client:
        created = await client.post("/api/v1/workspaces", json={"name": "Acme"})
        await client.patch(f"/api/v1/workspaces/{created.json()['id']}/plan", json={"plan": "pro"})
        resp = await client.post(
            "/api/v1/email-conversations/conv-123/business-info",
            json={
                "email_account_id": "acct-123",
                "conversation_id": "conv-123",
                "business_name": "Acme",
                "business_subject": "Plumbing",
                "business_additional_info": "",
            },
        )
    assert resp.status_code == 404  # validation passed, account not found


async def test_send_gmail_message_threads_with_thread_id():
    from app.services.automation.email_sync_service import send_gmail_message


    with respx.mock:
        route = respx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        ).mock(return_value=Response(200, json={"id": "msg-1"}))
        result = await send_gmail_message(
            "token", "a@b.com", "Re: Hi", "<p>Hi</p>", thread_id="thread-123"
        )

    assert result == {"id": "msg-1"}
    payload = json.loads(route.calls[0].request.content)
    assert payload["threadId"] == "thread-123"


async def test_send_gmail_message_adds_in_reply_to_for_message_ids():
    from app.services.automation.email_sync_service import send_gmail_message


    with respx.mock:
        route = respx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
        ).mock(return_value=Response(200, json={"id": "msg-2"}))
        await send_gmail_message(
            "token", "a@b.com", "Re: Hi", "<p>Hi</p>",
            thread_id="<orig@mail.gmail.com>",
        )

    payload = json.loads(route.calls[0].request.content)
    raw = base64.urlsafe_b64decode(payload["raw"]).decode()
    assert "In-Reply-To: <orig@mail.gmail.com>" in raw
    assert "References: <orig@mail.gmail.com>" in raw
