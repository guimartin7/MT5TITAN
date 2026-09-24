"""Avalon broker adapter boundary.

No undocumented/private Avalon endpoint is used here. The adapter intentionally
remains disabled until an official API, SDK, documented integration contract, or
explicit broker authorization is available.
"""


class AvalonIntegrationUnavailable(RuntimeError):
    pass


class AvalonBrokerAdapter:
    name = "avalon"
    execution_enabled = False

    def status(self) -> dict:
        return {
            "broker": self.name,
            "connected": False,
            "execution_enabled": False,
            "integration_mode": "OFFICIAL_API_REQUIRED",
            "reason": (
                "Avalon public trading API/SDK is not configured. "
                "Private browser endpoints are intentionally not reverse engineered."
            ),
        }

    def connect(self) -> None:
        raise AvalonIntegrationUnavailable(
            "Avalon integration requires an official documented API or broker-provided integration."
        )

    def place_order(self, *args, **kwargs):
        raise AvalonIntegrationUnavailable(
            "Live Avalon order execution is disabled without an official integration."
        )
