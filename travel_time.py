"ybus",
                          "suburban_train", "mcd", "shuttle_bus"],
            "max_result_count": 1,
        }
    elif depart_at > 0:
        payload["departure_time"] = depart_ts
    data = _http(url, payload)
    routes = data.get("routes") or []
    if not routes or routes[0].get("status") != "OK":
        return _fail("Маршрут не построился. Укажи время вручную.")
    minutes = max(1, round(int(routes[0]["duration"]) / 60))
    distance_km = round(int(routes[0].get("distance", 0)) / 100) / 10
    return 200, {"ok": True, "minutes": minutes, "distance_km": distance_km,
                 "provider": "2gis", "mode": mode}


def handle_body(raw):
    try:
        body = json.loads(raw or "{}")
    except Exception:
        return _fail("Некорректный запрос.")
    from_text = str(body.get("from") or "").strip()[:300]
    to_text = str(body.get("to") or "").strip()[:300]
    mode = str(body.get("mode") or "")
    if not from_text or not to_text:
        return _fail("Укажи оба адреса: откуда и куда.")
    try:
        depart_at = int(body.get("depart_at") or 0)
    except (TypeError, ValueError):
        depart_at = 0
    if depart_at < 0 or depart_at > int(time.time()) + 14 * 86400:
        depart_at = 0
    try:
        return _travel(from_text, to_text, mode, depart_at)
    except urllib.error.URLError:
        return _fail("Сервис карт временно недоступен.")
    except Exception:
        return _fail("Не удалось посчитать дорогу. Укажи время вручную.")


def handler(event, context):
    """Точка входа Yandex Cloud Function."""
    status, payload = handle_body(event.get("body") if isinstance(event, dict) else None)
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload, ensure_ascii=False)}


if __name__ == "__main__":
    class H(BaseHTTPRequestHandler):
        def _send(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self._send(200, {})

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            status, payload = handle_body(self.rfile.read(min(length, 8192)))
            self._send(status, payload)

        def log_message(self, *args):
            pass

    port = int(os.environ.get("PORT", "8080"))
    print(f"travel_time proxy on :{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

def _http(url, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _geocode(query, city=None):
    """Возвращает {"lat","lon","full_name"}; при указании города сначала ищет в нём."""
    queries = [f"{city}, {query}"] if city else []
    queries.append(query)
    for q in queries:
        url = f"{GEOCODE_URL}?q={urllib.parse.quote(q)}&fields=items.point&key={TGIS_KEY}"
        data = _http(url)
        items = (data.get("result") or {}).get("items") or []
        for item in items:
            point = item.get("point")
            if point and "lat" in point and "lon" in point:
                full = item.get("full_name") or ""
                if city and city.lower() not in full.lower():
                    continue
                return {"lat": point["lat"], "lon": point["lon"], "full_name": full}
    return None


def _fail(message, status=200):
    return status, {"ok": False, "error": message}


def _travel(from_text, to_text, mode):
    if not TGIS_KEY:
        return _fail("Сервис карт не настроен (нет ключа).")
    if mode not in TRANSPORT:
        return _fail("Неизвестный способ передвижения.")
    from_point = _geocode(from_text)
    if not from_point:
        return _fail("Не нашёл адрес отправления. Уточни его или укажи время вручную.")
    city = (from_point.get("full_name") or "").split(",")[0].strip() or None
    to_point = _geocode(to_text, city=city)
    if not to_point:
        return _fail("Не нашёл адрес события. Уточни его или укажи время вручную.")
    url = f"{MATRIX_URL}?key={TGIS_KEY}&version=2.0"
    payload = {
        "points": [from_point, to_point],
        "sources": [0],
        "targets": [1],
        "transport": TRANSPORT[mode],
    }
    if mode == "transit":
        start = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(time.time() + 600))
        payload["public_transport_params"] = {
            "start_time": start,
            "transport": ["bus", "metro", "tram", "trolleybus",
                          "suburban_train", "mcd", "shuttle_bus"],
            "max_result_count": 1,
        }
    data = _http(url, payload)
    routes = data.get("routes") or []
    if not routes or routes[0].get("status") != "OK":
        return _fail("Маршрут не построился. Укажи время вручную.")
    minutes = max(1, round(int(routes[0]["duration"]) / 60))
    distance_km = round(int(routes[0].get("distance", 0)) / 100) / 10
    return 200, {"ok": True, "minutes": minutes, "distance_km": distance_km,
                 "provider": "2gis", "mode": mode}
