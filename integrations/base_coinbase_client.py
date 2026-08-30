"""
integrations/base_coinbase_client.py

Base (Coinbase) / CDP client for NEXUS-AI-CORE.
Credentials resolved via core.secrets (Vault-first).

Capabilities:
  - CDP SDK wallet management (create, load, export)
  - ETH / USDC transfers on Base mainnet & testnet
  - Smart contract invocation
  - Onchain revenue collection
  - Balance queries
"""

import logging
from decimal import Decimal
from typing import Any, Optional

from core.secrets import SecretKey, require_secret, get_secret

logger = logging.getLogger(__name__)

BASE_MAINNET = "base-mainnet"
BASE_TESTNET = "base-sepolia"


class BaseCoinbaseClient:
    """Coinbase Developer Platform (CDP) client for Base network."""

    def __init__(self, network: str = BASE_MAINNET):
        self._api_key_name = require_secret(SecretKey.CDP_API_KEY_NAME)
        self._api_key_private = require_secret(SecretKey.CDP_API_KEY_PRIVATE_KEY)
        self._wallet_address = get_secret(SecretKey.BASE_WALLET_ADDRESS)
        self._network = network
        self._sdk = None
        self._wallet = None
        logger.info("[Base/CDP] Client initialised (network=%s)", network)

    def _get_sdk(self):
        if self._sdk is None:
            try:
                from cdp import Cdp, Wallet  # type: ignore
                Cdp.configure(self._api_key_name, self._api_key_private)
                self._sdk = Cdp
                logger.info("[Base/CDP] SDK configured")
            except ImportError:
                raise RuntimeError("[Base/CDP] cdp-sdk not installed. pip install cdp-sdk")
        return self._sdk

    def create_wallet(self) -> Any:
        """Create a new managed wallet on Base."""
        from cdp import Wallet  # type: ignore
        self._get_sdk()
        self._wallet = Wallet.create(network_id=self._network)
        addr = self._wallet.default_address.address_id
        logger.info("[Base/CDP] Wallet created: %s", addr)
        return self._wallet

    def load_wallet(self, wallet_id: str, seed: str) -> Any:
        """Load an existing wallet by ID + seed."""
        from cdp import Wallet, WalletData  # type: ignore
        self._get_sdk()
        data = WalletData(wallet_id=wallet_id, seed=seed)
        self._wallet = Wallet.import_data(data)
        logger.info("[Base/CDP] Wallet loaded: %s", wallet_id)
        return self._wallet

    def get_balance(self, asset: str = "eth") -> Decimal:
        if not self._wallet:
            raise RuntimeError("[Base/CDP] No wallet loaded. Call create_wallet() or load_wallet() first.")
        balance = self._wallet.balance(asset)
        logger.info("[Base/CDP] Balance (%s): %s", asset, balance)
        return balance

    def transfer(self, amount: Decimal | float, asset: str, destination: str, gasless: bool = True) -> Any:
        """Transfer asset to destination address."""
        if not self._wallet:
            raise RuntimeError("[Base/CDP] No wallet loaded.")
        transfer = self._wallet.transfer(amount, asset, destination, gasless=gasless).wait()
        logger.info("[Base/CDP] Transfer complete: %s %s → %s | tx=%s", amount, asset, destination, transfer.transaction_hash)
        return transfer

    def invoke_contract(self, contract_address: str, method: str, abi: list, args: dict) -> Any:
        """Call a smart contract method."""
        if not self._wallet:
            raise RuntimeError("[Base/CDP] No wallet loaded.")
        result = self._wallet.invoke_contract(
            contract_address=contract_address,
            method=method,
            abi=abi,
            args=args,
        ).wait()
        logger.info("[Base/CDP] Contract invoked: %s.%s", contract_address, method)
        return result
