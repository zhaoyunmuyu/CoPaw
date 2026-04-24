# -*- coding: utf-8 -*-
"""Standalone test for ES write to diagnose data not appearing in index."""
import asyncio
import os
from datetime import datetime


async def test_es_write():
    """Test direct ES write and verify data."""
    from elasticsearch import AsyncElasticsearch

    # Get config from env or use defaults
    host = os.environ.get("SWE_ES_HOST", "")
    port = int(os.environ.get("SWE_ES_PORT", "9200"))
    user = os.environ.get("SWE_ES_USER", "")
    password = os.environ.get("SWE_ES_ACCESS", "")
    if password and len(password) > 4:
        password = password[4:]  # Strip prefix
    index = os.environ.get("SWE_ES_INDEX", "swe_model_outputs")

    if not host:
        print("ERROR: SWE_ES_HOST not set, skipping test")
        return

    # Build URL with scheme
    scheme = "https" if port == 443 else "http"
    hosts = [f"{scheme}://{host}:{port}"]
    kwargs = {"hosts": hosts}

    if user and password:
        kwargs["basic_auth"] = (user, password)

    print(f"Connecting to ES: {hosts}, index={index}")

    es = AsyncElasticsearch(**kwargs)

    try:
        # Test ping
        ping_result = await es.ping()
        print(f"Ping result: {ping_result}")

        # Check if index exists
        exists_resp = await es.indices.exists(index=index)
        print(f"Index exists response: {exists_resp}")
        print(f"Index exists type: {type(exists_resp)}")
        print(f"Index exists bool: {bool(exists_resp)}")

        # Create index if not exists
        if not exists_resp:
            print(f"Creating index: {index}")
            mappings = {
                "properties": {
                    "trace_id": {"type": "keyword"},
                    "model_output": {"type": "text"},
                    "created_at": {"type": "date"},
                },
            }
            create_result = await es.indices.create(
                index=index,
                mappings=mappings,
            )
            print(f"Create result: {create_result}")

        # Write a test document
        trace_id = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        doc = {
            "trace_id": trace_id,
            "model_output": "This is a test message from test_es_write.py",
            "created_at": datetime.utcnow().isoformat(),
        }

        print(f"\nWriting document: trace_id={trace_id}")
        index_result = await es.index(
            index=index,
            id=trace_id,
            document=doc,
            refresh=True,
        )
        print(f"Index result type: {type(index_result)}")
        print(f"Index result: {index_result}")

        # Immediately try to read it back
        print(f"\nReading document back: trace_id={trace_id}")
        get_result = await es.get(index=index, id=trace_id)
        print(f"Get result: {get_result}")

        # Search for it
        print("\nSearching for document...")
        search_result = await es.search(index=index, query={"match_all": {}})
        print(f"Search result: {search_result}")

    except Exception as e:
        import traceback

        print(f"ERROR: {e}")
        traceback.print_exc()
    finally:
        await es.close()
        print("\nES connection closed")


if __name__ == "__main__":
    asyncio.run(test_es_write())
