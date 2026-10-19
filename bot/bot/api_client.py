import aiohttp


class BackendClient:
    """Calls the catalog backend. Stateless: a fresh session per request."""

    def __init__(self, base_url: str, internal_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._internal_token = internal_token

    async def create_product(
        self, name: str, data: bytes, filename: str, content_type: str
    ) -> dict:
        form = aiohttp.FormData()
        form.add_field("name", name)
        form.add_field("file", data, filename=filename, content_type=content_type)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/api/products",
                data=form,
                headers={"X-Internal-Token": self._internal_token},
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
