"""Bound request size before JSON decoding, including chunked requests."""
from fastapi.responses import Response


class BodyLimitMiddleware:
    def __init__(self, app, maximum=131072):
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        body = bytearray()
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.maximum:
                await Response(status_code=413)(scope, receive, send)
                return
            more = message.get("more_body", False)
        consumed = False

        async def buffered_receive():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, buffered_receive, send)
