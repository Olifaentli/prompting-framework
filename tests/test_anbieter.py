"""Was tatsaechlich an die Anbieter geschickt wird.

Die Anfragen werden abgefangen, bevor sie das Netz erreichen. Geprueft wird
der Inhalt, den die Bibliotheken erzeugen - nicht, was der eigene Code
uebergeben wollte. Anlass: Die Anthropic-Bibliothek 1.x kennt `temperature`
nicht mehr als Argument. Wuerde der Wert still verworfen, liefe ein Modell
mit der Standardeinstellung, und die dokumentierte Temperatur waere nie
gesetzt worden.
"""

import json

import anthropic
import httpx2
import openai
import pytest

import models
from design import generate_trials
from runner import AnthropicProvider, OpenAIProvider
from runner_batch import _einreichen


def _abfangen(antwort):
    gesendet = []

    def handler(req):
        gesendet.append(json.loads(req.content))
        return httpx2.Response(200, json=antwort(req))

    return gesendet, httpx2.Client(transport=httpx2.MockTransport(handler))


def _anthropic_antwort(req):
    if req.url.path.endswith("/batches"):
        return {"id": "msgbatch_x", "type": "message_batch", "processing_status": "in_progress",
                "request_counts": {"processing": 1, "succeeded": 0, "errored": 0,
                                   "canceled": 0, "expired": 0},
                "created_at": "2026-10-10T00:00:00Z", "expires_at": "2026-10-11T00:00:00Z",
                "ended_at": None, "cancel_initiated_at": None, "archived_at": None,
                "results_url": None}
    return {"id": "msg_x", "type": "message", "role": "assistant",
            "model": "claude-haiku-4-5-20251001", "content": [{"type": "text", "text": "A"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1}}


def _openai_antwort(req):
    return {"id": "c", "object": "chat.completion", "created": 0, "model": "gpt-6-luna",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "B"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}


@pytest.fixture(scope="module")
def durchlauf():
    return next(generate_trials(2, only_item="asian_disease", je_stufe=False))


def test_haiku_einzelaufruf_sendet_temperatur(durchlauf):
    gesendet, http = _abfangen(_anthropic_antwort)
    p = AnthropicProvider.__new__(AnthropicProvider)
    p.spec, p.temperature = models.get("haiku-4.5"), 1.0
    p.client = anthropic.Anthropic(api_key="test", http_client=http)
    antwort = p(durchlauf)
    assert gesendet[0]["temperature"] == 1.0
    assert gesendet[0]["model"] == "claude-haiku-4-5-20251001"
    assert gesendet[0]["max_tokens"] == 8
    assert antwort["served_model"] == "claude-haiku-4-5-20251001"


def test_haiku_stapel_sendet_temperatur(durchlauf):
    gesendet, http = _abfangen(_anthropic_antwort)
    client = anthropic.Anthropic(api_key="test", http_client=http)
    _einreichen(client, models.get("haiku-4.5"), [durchlauf], 1.0)
    params = gesendet[0]["requests"][0]["params"]
    assert params["temperature"] == 1.0
    assert params["model"] == "claude-haiku-4-5-20251001"


def test_luna_sendet_temperatur_ohne_reasoning(durchlauf):
    gesendet, http = _abfangen(_openai_antwort)
    p = OpenAIProvider.__new__(OpenAIProvider)
    p.spec, p.temperature = models.get("luna"), 1.0
    p.client = openai.OpenAI(api_key="test", http_client=http)
    p(durchlauf)
    assert gesendet[0]["temperature"] == 1.0
    assert gesendet[0]["reasoning_effort"] == "none"
    assert gesendet[0]["model"] == "gpt-6-luna"
