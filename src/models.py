"""Registry der eingesetzten Modelle.

WICHTIG - methodische Einschraenkung:
Die aktuellen Anthropic-Spitzenmodelle (claude-opus-5, claude-sonnet-5,
claude-opus-4-8/4-7) akzeptieren den Parameter `temperature` nicht mehr; ein
Request mit `temperature` wird mit HTTP 400 abgelehnt. Fuer ein Experiment, das
Antwortverteilungen ueber viele Durchlaeufe erzeugt und die Temperatur als
dokumentierte Kontrollvariable fuehrt, sind daher nur Modelle mit
`supports_temperature=True` uneingeschraenkt geeignet.

Modelle ohne Temperatursteuerung sind weiterhin stochastisch (die Antworten
variieren zwischen Aufrufen), aber die Streuung ist nicht einstellbar und ein
Determinismus-Check bei T=0 ist nicht moeglich.

Preise in USD je 1 Mio. Token, Stand 2026-06.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_id: str
    supports_temperature: bool
    usd_per_mtok_in: float
    usd_per_mtok_out: float
    note: str = ""


REGISTRY: dict[str, ModelSpec] = {
    # --- Anthropic: Temperatur steuerbar (fuer dieses Experiment geeignet) ---
    # Datierte Kennung statt des Sammelnamens claude-haiku-4-5: Der Sammelname
    # kann auf eine neuere Version umgelenkt werden, die datierte nicht.
    "haiku-4.5": ModelSpec(
        "anthropic", "claude-haiku-4-5-20251001", True, 1.00, 5.00,
        "Guenstigstes Modell mit Temperatursteuerung; Standard fuer den Hauptlauf.",
    ),
    "sonnet-4.6": ModelSpec(
        "anthropic", "claude-sonnet-4-6", True, 3.00, 15.00,
        "Mittlere Leistungsklasse mit Temperatursteuerung.",
    ),
    "opus-4.6": ModelSpec(
        "anthropic", "claude-opus-4-6", True, 5.00, 25.00,
        "Staerkstes Anthropic-Modell mit Temperatursteuerung.",
    ),

    # --- Anthropic: keine Temperatursteuerung (nur eingeschraenkt geeignet) ---
    "opus-5": ModelSpec(
        "anthropic", "claude-opus-5", False, 5.00, 25.00,
        "Aktuelles Spitzenmodell; `temperature` wird mit 400 abgelehnt.",
    ),
    "sonnet-5": ModelSpec(
        "anthropic", "claude-sonnet-5", False, 3.00, 15.00,
        "`temperature` wird mit 400 abgelehnt.",
    ),

    # --- OpenAI: zweite Modellfamilie ---
    # Die aktuellen GPT-6-Modelle sind Reasoning-Modelle. Temperatur ist nur
    # nutzbar, wenn das Reasoning abgeschaltet wird (reasoning_effort="none").
    # Das ist hier ohnehin erwuenscht: Payne (2025) zeigt, dass der
    # Framing-Effekt verschwindet, sobald ein Modell die Erwartungswerte
    # ausrechnet. Der Runner setzt reasoning_effort fuer diese Modelle.
    # Fuer luna ist keine datierte Kennung bekannt; in der Vorabpruefung (M2)
    # ueber die Modellliste von OpenAI zu klaeren. Bis dahin haelt der Runner
    # die ausgelieferte Version und den system_fingerprint je Antwort fest.
    "luna": ModelSpec(
        "openai", "gpt-6-luna", True, 0.10, 0.50,
        "Guenstigstes GPT-6-Modell, laut Anbieter fuer wiederholbare Laeufe "
        "in grossem Umfang. Reasoning abschaltbar, damit Temperatur nutzbar "
        "ist. Standard fuer die zweite Modellfamilie.",
    ),
    "sol": ModelSpec(
        "openai", "gpt-6-sol", True, 2.00, 10.00,
        "Mittlere Leistungsklasse; Reasoning ebenfalls abschaltbar.",
    ),
    "astra": ModelSpec(
        "openai", "gpt-6-astra", False, 10.00, 50.00,
        "Spitzenmodell, aber reasoning_effort='none' wird mit 400 abgelehnt; "
        "damit ist die Temperatur nicht steuerbar. Fuer dieses Experiment "
        "nicht geeignet.",
    ),

    # --- Simulation ohne API-Zugriff ---
    "mock": ModelSpec(
        "mock", "mock-v1", True, 0.0, 0.0,
        "Simuliert Antworten aus einem bekannten logistischen Modell. "
        "Dient dem Test der Pipeline, nicht der Beantwortung der Forschungsfragen.",
    ),
}


def get(name: str) -> ModelSpec:
    if name not in REGISTRY:
        raise SystemExit(
            f"Unbekanntes Modell '{name}'. Verfuegbar: {', '.join(REGISTRY)}"
        )
    return REGISTRY[name]


if __name__ == "__main__":
    print(f"{'Alias':<16}{'Provider':<11}{'Modell-ID':<22}{'Temp':<7}{'$/Mtok in/out'}")
    print("-" * 72)
    for alias, m in REGISTRY.items():
        temp = "ja" if m.supports_temperature else "NEIN"
        print(f"{alias:<16}{m.provider:<11}{m.model_id:<22}{temp:<7}{m.usd_per_mtok_in}/{m.usd_per_mtok_out}")
