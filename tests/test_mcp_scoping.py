"""Offline integration test for the MCP changes. Needs NO API keys, Neo4j or Qdrant.

It starts the REAL MCP server (mcp_server.server) with a fake graph + fake vector search behind it,
then runs the REAL auditor and quant nodes against it with a fake LLM. It checks that:
  1. the auditor's LLM sees exactly ONE tool and can only search the current document,
  2. the auditor's prompt contains no risk score,
  3. each node can only call the MCP tools on its own allow-list,
  4. the quant node goes through MCP (read history, search, save, centrality) and nothing else,
  5. the server refuses a document search without a document_hash.

Run from the project root:   python tests/test_mcp_scoping.py
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PORT = 8123
DOC = "hash_FY2025"
OLD_DOC = "hash_FY2024"
LEAK = "SECRET_RISK_MARKER"          # planted in the fake risk data; must never reach the auditor
STORE = os.environ.get("TEST_STORE") or os.path.join(tempfile.gettempdir(), "arthik_test_store.json")


# ---------------------------------------------------------------- stubs for everything outside the code under test
def install_stubs():
    def module(name, **attrs):
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m
        return m

    module("config", GEMINI_MODEL="x", GROQ_MODEL="x", QDRANT_COLLECTION="x")
    module("langchain_google_genai", ChatGoogleGenerativeAI=object)
    module("langchain_groq", ChatGroq=object)

    class AllProvidersExhausted(Exception):
        pass

    from langchain_core.runnables import RunnableLambda
    fake_metrics = json.dumps({"company_name": "Brightwater", "total_debt": 800, "total_equity": 400,
                               "current_assets": 500, "current_liabilities": 250,
                               "revenue": 1000, "net_income": 90})
    module("llm.provider", get_llm=lambda: FakeToolModel(), AllProvidersExhausted=AllProvidersExhausted,
           get_extraction_llm=lambda: RunnableLambda(lambda _prompt: fake_metrics))

    def log(event):
        with open(STORE + ".log", "a") as f:
            f.write(json.dumps(event) + "\n")

    def search_chunks(query, top_k=5, document_hash=None):
        log({"search": query, "document_hash": document_hash, "top_k": top_k})
        return [{"text": f"passage about {query}", "filename": "f.pdf", "score": 0.9}]

    module("vectorstore.indexer", search_chunks=search_chunks)

    class FakeNeo4j:
        def run_query(self, query, params=None):
            params = params or {}
            store = json.load(open(STORE))
            if "RETURN c.id AS id, c.name AS name, c.description AS description" in query:
                return [{"id": params["company_id"], "name": "Brightwater", "description": "industrial", "relationship_count": 4}]
            if "connected.id AS id" in query:
                return [{"id": "s1", "name": "Sub One", "type": "Subsidiary", "relationship_path": ["OWNS"]}]
            if "degree" in query and "ORDER BY degree" in query:
                return [{"id": "other", "name": "Other", "type": "Company", "degree": 9},
                        {"id": "brightwater", "name": "Brightwater", "type": "Company", "degree": 4}]
            if "r.final_risk_level AS final_risk_level" in query:
                return store["assessments"]
            if "MERGE (r:RiskAssessment" in query:
                log({"write": {k: params[k] for k in ("company_id", "document_hash", "risk_level", "debt_to_equity")}})
                return [{"r": 1}]
            raise AssertionError(f"unexpected query: {query[:80]}")

    module("graph.neo4j_client", neo4j_client=FakeNeo4j())


# ---------------------------------------------------------------- fake chat model (records what it was given)
from langchain_core.language_models.chat_models import BaseChatModel          # noqa: E402
from langchain_core.messages import AIMessage                                # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult                # noqa: E402

SEEN = {"tool_names": None, "first_prompt": None}


class FakeToolModel(BaseChatModel):
    @property
    def _llm_type(self):
        return "fake"

    def bind_tools(self, tools, **kwargs):
        SEEN["tool_names"] = [t.name for t in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        SEEN["first_prompt"] = SEEN["first_prompt"] or messages[0].content
        if any(m.type == "tool" for m in messages):
            msg = AIMessage(content="- Related-party lender found\n- Heavy supplier concentration")
        else:
            msg = AIMessage(content="", tool_calls=[{"name": "search_this_document",
                                                     "args": {"query": "related party loans"}, "id": "call_1"}])
        return ChatResult(generations=[ChatGeneration(message=msg)])


# ---------------------------------------------------------------- the tests
def fresh_store(with_current_doc: bool):
    assessments = [{"debt_to_equity": 1.0, "current_ratio": 1.5, "net_margin": 0.05, "risk_level": "MEDIUM",
                    "notes": [LEAK], "status": "APPROVED", "created_at": "2025-01-01T00:00:00",
                    "final_risk_level": "LOW", "overridden": True,
                    "document_hash": OLD_DOC, "document_filename": "FY2024.pdf"}]
    if with_current_doc:
        assessments.insert(0, {"debt_to_equity": 2.0, "current_ratio": 2.0, "net_margin": 0.09, "risk_level": "HIGH",
                               "notes": [LEAK], "status": "DRAFT", "created_at": "2026-01-01T00:00:00",
                               "final_risk_level": None, "overridden": None,
                               "document_hash": DOC, "document_filename": "FY2025.pdf"})
    json.dump({"assessments": assessments}, open(STORE, "w"))
    open(STORE + ".log", "w").close()


def events():
    return [json.loads(line) for line in open(STORE + ".log") if line.strip()]


STATE = {"company_id": "brightwater", "company_name": "Brightwater", "document_hash": DOC,
         "reviewer": "t", "review_history": [], "final_score": None, "iteration": 0, "max_iterations": 3}


async def run_tests():
    install_stubs()
    import workflow.mcp_client as mcp_client
    mcp_client.MCP_URL = f"http://127.0.0.1:{PORT}/mcp"
    mcp_client._client = None
    from workflow.nodes.auditor import auditor_node
    from workflow.nodes.quant import quant_node

    ok = lambda name: print(f"  PASS  {name}")

    # 1+2: auditor ------------------------------------------------------------------------------------------
    fresh_store(with_current_doc=True)
    out = await auditor_node(dict(STATE))
    assert SEEN["tool_names"] == ["search_this_document"], SEEN["tool_names"]
    ok("auditor's LLM is bound to exactly one tool: search_this_document")
    searches = [e for e in events() if "search" in e]
    assert searches and all(e["document_hash"] == DOC for e in searches), searches
    ok("auditor's document search is locked to the current document_hash")
    assert LEAK not in SEEN["first_prompt"] and "HIGH" not in SEEN["first_prompt"]
    assert "debt_to_equity" not in SEEN["first_prompt"].lower()
    ok("auditor prompt contains no risk score / ratio")
    assert "Sub One" in SEEN["first_prompt"] and "relationship" in SEEN["first_prompt"]
    ok("auditor prompt contains the pre-fetched graph facts (profile + connections)")
    assert len(out["auditor_findings"]) == 2

    # 3: allow-lists ----------------------------------------------------------------------------------------
    async with mcp_client.node_toolbox("quant") as tools:
        for banned in ("get_company_profile", "get_connected_entities"):
            try:
                await tools.call(banned, {"company_id": "x"})
                raise AssertionError(f"quant could call {banned}")
            except PermissionError:
                pass
    async with mcp_client.node_toolbox("auditor") as tools:
        for banned in ("get_debt_ratios", "calculate_graph_centrality", "save_risk_assessment"):
            try:
                await tools.call(banned, {})
                raise AssertionError(f"auditor could call {banned}")
            except PermissionError:
                pass
        # 5: server-side guard
        try:
            await tools.call("retrieve_footnote_context", {"query": "q", "document_hash": ""})
            raise AssertionError("server accepted an empty document_hash")
        except RuntimeError as e:
            assert "document_hash is required" in str(e)
    ok("each node is blocked from tools outside its allow-list")
    ok("server refuses a document search with no document_hash")

    # 4a: quant, first round, assessment from ingestion already exists -> reuse, no search, no write -------------
    fresh_store(with_current_doc=True)
    out = await quant_node(dict(STATE))
    ev = events()
    assert not [e for e in ev if "search" in e or "write" in e], ev
    assert out["risk_score"]["risk_level"] == "HIGH" and out["iteration"] == 1
    ctx = out["quant_context"]
    assert ctx["prior_assessments"][0]["risk_level"] == "LOW" and ctx["prior_assessments"][0]["overridden"]
    assert ctx["centrality"] == {"rank": 2, "degree": 4, "top_n": 100}
    ok("quant reuses the existing assessment via MCP (no search, no LLM, no write)")
    ok("quant gathers earlier-year assessments (approved level) and centrality via MCP")

    # 4b: quant, nothing exists for this document -> search x5, score, save through MCP -------------------------
    fresh_store(with_current_doc=False)
    out = await quant_node(dict(STATE))
    ev = events()
    searches = [e for e in ev if "search" in e]
    writes = [e for e in ev if "write" in e]
    assert len(searches) == 5 and all(e["document_hash"] == DOC for e in searches), searches
    assert len(writes) == 1 and writes[0]["write"]["document_hash"] == DOC
    assert out["risk_score"]["debt_to_equity"] == 2.0 and out["risk_score"]["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    ok("quant scores a new document through MCP: 5 scoped searches + 1 save_risk_assessment")

    # 4c: quant re-run with analyst hint ----------------------------------------------------------------------
    fresh_store(with_current_doc=True)
    out = await quant_node({**STATE, "iteration": 1, "rerun_hint": "current assets are on the balance sheet",
                            "risk_score": {"risk_level": "HIGH"}})
    ev = events()
    assert any(e.get("search") == "current assets are on the balance sheet" for e in ev)
    assert len([e for e in ev if "write" in e]) == 1
    assert out["iteration"] == 2 and out["review_history"][0]["action"] == "rescore"
    ok("quant re-run uses the analyst hint as an extra scoped search, re-saves, and logs a 'rescore' event")

    # 6: whole graph up to the human-review pause ---------------------------------------------------------------
    fresh_store(with_current_doc=True)
    from workflow.workflow import build_workflow
    result = await build_workflow().ainvoke(dict(STATE), config={"configurable": {"thread_id": "t1"}})
    payload = result["__interrupt__"][0].value
    assert payload["quant_context"]["prior_assessments"] and payload["auditor_findings"]
    ok("full workflow runs auditor -> quant -> pauses at hitl with the new quant_context in the payload")
    print("\nALL TESTS PASSED")


def serve():
    install_stubs()
    from mcp_server.server import mcp
    mcp.run(transport="http", host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    if "--serve" in sys.argv:
        serve()
    else:
        fresh_store(with_current_doc=True)
        server = subprocess.Popen([sys.executable, __file__, "--serve"], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={**os.environ, "TEST_STORE": STORE})
        try:
            time.sleep(6)
            asyncio.run(run_tests())
        finally:
            server.terminate()
