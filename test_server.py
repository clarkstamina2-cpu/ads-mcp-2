"""
Suíte de testes do servidor MCP do Google Ads (contra um servidor em execução).

Uso:
  MCP_URL=https://<dominio> MCP_TOKEN=xxx python test_server.py
  SKIP_REAL=1  -> pula as chamadas reais ao Google Ads (útil para testar o servidor local com credenciais falsas)

As chamadas reais ao Google Ads são SOMENTE de leitura. Nada é criado, alterado ou excluído.
Os testes unitários (sem servidor) ficam em tests/ e rodam com: python -m pytest tests --ignore=tests/smoke
"""
import asyncio
import os

from fastmcp import Client

try:
    import httpx
except ImportError:  # o FastMCP 4.x instala o cliente HTTP como "httpx2"
    import httpx2 as httpx

BASE = os.environ.get("MCP_URL", "http://localhost:8080").rstrip("/")
TOKEN = os.environ["MCP_TOKEN"]
SKIP_REAL = os.environ.get("SKIP_REAL") == "1"
MIN_TOOLS = 68


def data_of(result):
    return result.data if result.data is not None else [getattr(c, "text", "") for c in result.content]


async def main():
    async with httpx.AsyncClient() as h:
        r = await h.get(f"{BASE}/health")
        assert r.status_code == 200, f"/health falhou: {r.status_code}"
        print(f"OK  /health público -> {r.json()}")
        r = await h.post(f"{BASE}/mcp", json={})
        assert r.status_code == 401, f"sem token deveria ser 401, veio {r.status_code}"
        print("OK  sem token -> 401")
        r = await h.post(f"{BASE}/mcp?token=errado", json={})
        assert r.status_code == 401, f"token errado deveria ser 401, veio {r.status_code}"
        print("OK  token errado -> 401")
        r = await h.post(f"{BASE}/mcp", json={}, headers={"Authorization": f"Bearer {TOKEN}"})
        assert r.status_code == 401, f"token só no header deveria ser 401, veio {r.status_code}"
        print("OK  token só no header -> 401 (apenas ?token= é aceito)")

    async with Client(f"{BASE}/mcp?token={TOKEN}") as c:
        tools = [t.name for t in await c.list_tools()]
        assert len(tools) >= MIN_TOOLS, f"esperava pelo menos {MIN_TOOLS} tools, vieram {len(tools)}"
        assert len(set(tools)) == len(tools), "há tools duplicadas"
        for needed in (
            "list_accessible_customers",
            "list_client_accounts",
            "search",
            "update_conversion_action",
            "list_recommendation_subscriptions",
            "set_recommendation_subscription_status",
            "resolve_audience_names",
            "create_conversion_action",
        ):
            assert needed in tools, f"tool ausente: {needed}"
        print(f"OK  token certo -> {len(tools)} tools registradas")

        if SKIP_REAL:
            print("--  chamadas reais ao Google Ads NÃO testadas (SKIP_REAL=1)")
        else:
            ids = data_of(await c.call_tool("list_accessible_customers", {}))
            ids = ids.get("result", ids) if isinstance(ids, dict) else ids
            assert ids, "list_accessible_customers não retornou contas"
            print(f"OK  list_accessible_customers (Google Ads real) -> {len(ids)} conta(s)")

            clients = data_of(await c.call_tool("list_client_accounts", {}))
            clients = clients.get("result", clients) if isinstance(clients, dict) else clients
            assert isinstance(clients, list) and clients, "list_client_accounts não retornou contas"
            print(f"OK  list_client_accounts (Google Ads real) -> {len(clients)} conta(s) de cliente")

            names = data_of(await c.call_tool("resolve_audience_names", {"ids": ["uservertical::3", "99999999"]}))
            assert names["resolved"]["3"][0]["name"], f"resolve_audience_names não traduziu o ID 3: {names}"
            assert names["not_found"] == ["99999999"], f"ID inexistente deveria vir em not_found: {names}"
            print(f"OK  resolve_audience_names (Google Ads real) -> uservertical::3 = {names['resolved']['3'][0]['name']}")

            sample = next((x for x in clients if not x.get("is_manager")), None)
            if sample:
                subs = data_of(await c.call_tool("list_recommendation_subscriptions", {"customer_id": str(sample["customer_id"])}))
                assert "subscriptions" in subs and subs["total"] == len(subs["subscriptions"]), subs
                print(f"OK  list_recommendation_subscriptions (Google Ads real) -> {subs['total']} assinatura(s), {subs['auto_apply_enabled_count']} com auto-aplicar ligado")

        try:
            await c.call_tool("update_conversion_action", {"customer_id": "1", "conversion_action_id": "1"})
            raise AssertionError("update sem nenhum campo deveria dar erro")
        except AssertionError:
            raise
        except Exception as e:
            print(f"OK  update_conversion_action sem campos -> erro claro ({str(e)[:70]})")

    print("\nTODOS OS TESTES PASSARAM")


asyncio.run(main())
