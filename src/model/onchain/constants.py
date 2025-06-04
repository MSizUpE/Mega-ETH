from decimal import Decimal
from typing import Dict
from dataclasses import dataclass


@dataclass
class Balance:
    """Balance representation in different formats."""

    _wei: int
    decimals: int = 18  # ETH по умолчанию имеет 18 decimals
    symbol: str = "ETH"  # ETH символ по умолчанию

    @property
    def wei(self) -> int:
        """Get balance in wei."""
        return self._wei

    @property
    def formatted(self) -> float:
        """Get balance in token units."""
        return float(Decimal(str(self._wei)) / Decimal(str(10**self.decimals)))

    @property
    def gwei(self) -> float:
        """Get balance in gwei (only for ETH)."""
        if self.symbol != "ETH":
            raise ValueError("gwei is only applicable for ETH")
        return float(Decimal(str(self._wei)) / Decimal("1000000000"))  # 1e9

    @property
    def ether(self) -> float:
        """Get balance in ether (only for ETH)."""
        if self.symbol != "ETH":
            raise ValueError("ether is only applicable for ETH")
        return self.formatted

    @property
    def eth(self) -> float:
        """Alias for ether (only for ETH)."""
        return self.ether

    def __str__(self) -> str:
        """String representation of balance."""
        return f"{self.formatted} {self.symbol} ({self._wei} wei)"

    def __repr__(self) -> str:
        """Detailed string representation of balance."""
        base_repr = f"Balance(wei={self._wei}, formatted={self.formatted}, symbol={self.symbol})"
        if self.symbol == "ETH":
            base_repr = (
                f"Balance(wei={self._wei}, gwei={self.gwei}, ether={self.ether})"
            )
        return base_repr

    def to_dict(self) -> Dict[str, float]:
        """Convert balance to dictionary representation."""
        if self.symbol == "ETH":
            return {"wei": self.wei, "gwei": self.gwei, "ether": self.ether}
        return {"wei": self.wei, "formatted": self.formatted}

    @classmethod
    def from_wei(
        cls, wei_amount: int, decimals: int = 18, symbol: str = "ETH"
    ) -> "Balance":
        """Create Balance instance from wei amount."""
        return cls(_wei=wei_amount, decimals=decimals, symbol=symbol)

    @classmethod
    def from_formatted(
        cls, amount: float, decimals: int = 18, symbol: str = "ETH"
    ) -> "Balance":
        """Create Balance instance from formatted amount."""
        wei_amount = int(Decimal(str(amount)) * Decimal(str(10**decimals)))
        return cls(_wei=wei_amount, decimals=decimals, symbol=symbol)

    @classmethod
    def from_ether(cls, ether_amount: float) -> "Balance":
        """Create Balance instance from ether amount."""
        wei_amount = int(Decimal(str(ether_amount)) * Decimal("1000000000000000000"))
        return cls(_wei=wei_amount)

    @classmethod
    def from_gwei(cls, gwei_amount: float) -> "Balance":
        """Create Balance instance from gwei amount."""
        wei_amount = int(Decimal(str(gwei_amount)) * Decimal("1000000000"))
        return cls(_wei=wei_amount)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Balance):
            return NotImplemented
        return self._wei == other._wei

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Balance):
            return NotImplemented
        return self._wei < other._wei

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Balance):
            return NotImplemented
        return self._wei > other._wei

    def __add__(self, other: object) -> "Balance":
        if not isinstance(other, Balance):
            return NotImplemented
        return Balance(_wei=self._wei + other._wei)

    def __sub__(self, other: object) -> "Balance":
        if not isinstance(other, Balance):
            return NotImplemented
        return Balance(_wei=self._wei - other._wei)
