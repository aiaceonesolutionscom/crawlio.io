class PrivateNetworkAccessMiddleware:
    """Chrome's Private Network Access (PNA) policy requires a preflight
    response to explicitly opt in via `Access-Control-Allow-Private-Network`
    whenever the browser sends `Access-Control-Request-Private-Network: true`
    — this happens for any cross-origin fetch targeting a loopback/private
    address, which is every request this local dev API ever receives.
    Starlette's CORSMiddleware (as of 0.41) has no PNA support and never
    sends this header, so Chrome silently blocks the request in DevTools as
    a generic CORS failure even though every "normal" CORS header is already
    correct. This wraps the app to add the one header Chrome is actually
    checking for."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        wants_pna = headers.get(b"access-control-request-private-network") == b"true"

        if not wants_pna:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers") or []) + [
                    (b"access-control-allow-private-network", b"true")
                ]
            await send(message)

        await self.app(scope, receive, send_wrapper)
