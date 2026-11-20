from ctb import fusion_client, mock_fusion_api


def test_pagination_round_trip():
    resources = {"items": [{"ItemNumber": f"P-{i}"} for i in range(237)]}
    server, thread = mock_fusion_api.start_server(resources)
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        fetched = fusion_client.fetch_all(base_url, "items", page_size=50)
        assert fetched == resources["items"]
    finally:
        mock_fusion_api.stop_server(server, thread)


def test_unknown_resource_returns_404():
    import urllib.error
    import urllib.request

    server, thread = mock_fusion_api.start_server({"items": []})
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            urllib.request.urlopen(f"{base_url}/nonexistent", timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        mock_fusion_api.stop_server(server, thread)
