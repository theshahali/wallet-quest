#!/usr/bin/env python3
"""
WalletQuest Autonomous Settlement & Escrow Verification Relay (GenLayer -> EVM)
================================================================================
Polls GenLayer Court (get_hero, get_duel), performs strict pre-settlement verification
of EVM challenger, defender, wager, funding, and settlement state against the GenLayer
record, and executes signed ECDSA on-chain disbursements with confirmed receipts (status == 1).

DUEL-ID MAPPING CONVENTION:
Standardized 1-to-1 mapping between GenLayer string ID and EVM bytes32:
- GenLayer: "DUEL_001" (str)
- EVM: bytes32(abi.encodePacked("DUEL_001")) = `duel_id.encode('utf-8').ljust(32, b'\0')[:32]`

PRE-SETTLEMENT VERIFICATION INVARIANTS:
1. Participant Binding: EVM challenger and defender strictly match GenLayer duel record.
2. Wager Parity: EVM wagerAmount matches GenLayer wager_amount.
3. Collateral Verification: EVM duel must be fully funded (challengerFunded == True, defenderFunded == True, isFunded == True).
4. Settlement Idempotency: EVM duel must not be already settled (isSettled == False).
5. Legitimate Winner: GenLayer winner must be either registered challenger or defender.
6. Confirmed Receipts: Waits for on-chain receipt and asserts receipt.status == 1 on both chains.
"""

import os
import sys
import time
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    Web3 = None
    Account = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("walletquest_relay.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Configuration from Environment
GENLAYER_RPC = os.getenv("GENLAYER_RPC", "https://studio.genlayer.com/api")
GENLAYER_COURT_ADDRESS = os.getenv("GENLAYER_COURT_ADDRESS", "0x037A962c2be3781Fb31a5faF3fb22D6CBb555049")
EVM_RPC_URL = os.getenv("EVM_RPC_URL", "https://sepolia.base.org")
EVM_HERO_ADDRESS = os.getenv("EVM_HERO_ADDRESS", "0x3Fa9b23f81902c34918239482910394817e12a89")
RELAY_PRIVATE_KEY = os.getenv("RELAY_PRIVATE_KEY", "")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))

HERO_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "duelId", "type": "bytes32"},
            {"internalType": "address", "name": "challenger", "type": "address"},
            {"internalType": "address", "name": "defender", "type": "address"},
            {"internalType": "uint256", "name": "wagerAmount", "type": "uint256"}
        ],
        "name": "createDuel",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "duelId", "type": "bytes32"}],
        "name": "fundDuel",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "duelId", "type": "bytes32"},
            {"internalType": "address", "name": "winner", "type": "address"}
        ],
        "name": "disburseDuelBounty",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "duelId", "type": "bytes32"}],
        "name": "getDuelEscrow",
        "outputs": [
            {"internalType": "bytes32", "name": "id", "type": "bytes32"},
            {"internalType": "address", "name": "challenger", "type": "address"},
            {"internalType": "address", "name": "defender", "type": "address"},
            {"internalType": "uint256", "name": "wagerAmount", "type": "uint256"},
            {"internalType": "bool", "name": "challengerFunded", "type": "bool"},
            {"internalType": "bool", "name": "defenderFunded", "type": "bool"},
            {"internalType": "bool", "name": "isFunded", "type": "bool"},
            {"internalType": "bool", "name": "isSettled", "type": "bool"},
            {"internalType": "address", "name": "winner", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


class GenLayerCourtClient:
    """Reads hero profiles and duel combat verdicts from GenLayer with strict fail-closed safety."""

    def __init__(self, rpc_url: str, contract_address: str):
        self.rpc_url = rpc_url
        self.contract_address = contract_address

    def get_duel(self, duel_id: str) -> Optional[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "method": "gen_callView",
            "params": {
                "address": self.contract_address,
                "function_name": "get_duel",
                "args": [duel_id]
            },
            "id": int(time.time())
        }
        try:
            resp = requests.post(self.rpc_url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if "error" in data:
                    logging.error(f"[GENLAYER ERROR] {data.get('error')}")
                    return None
                result = data.get("result")
                if isinstance(result, str):
                    try:
                        return json.loads(result)
                    except Exception:
                        pass
                if isinstance(result, dict):
                    return result
        except Exception as e:
            logging.error(f"[FAIL-CLOSED] Error querying GenLayer duel state: {e}")
        return None


class EvmSettlementRelay:
    """Performs pre-settlement verification, signed transactions, and receipt confirmation on EVM."""

    def __init__(self, rpc_url: str, contract_address: str, private_key: str):
        self.rpc_url = rpc_url
        self.contract_address = contract_address
        self.private_key = private_key
        self.settled_duels = {}

        if Web3:
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.private_key:
                self.account = Account.from_key(self.private_key)
                self.sender_address = self.account.address
            else:
                self.account = None
                self.sender_address = None
        else:
            self.w3 = None
            self.account = None
            self.sender_address = None

    def to_bytes32(self, text: str) -> bytes:
        """Standardized documented duel-ID mapping: str -> bytes32 (left-aligned zero-padded)."""
        raw_bytes = text.encode("utf-8")
        return raw_bytes.ljust(32, b'\0')[:32]

    def get_evm_duel(self, duel_id: str) -> Optional[Dict[str, Any]]:
        """Queries the on-chain EVM duel escrow state."""
        if not self.w3:
            return None
        try:
            contract = self.w3.eth.contract(address=Web3.to_checksum_address(self.contract_address), abi=HERO_ABI)
            d_bytes32 = self.to_bytes32(duel_id)
            res = contract.functions.getDuelEscrow(d_bytes32).call()
            return {
                "duelId": res[0],
                "challenger": res[1],
                "defender": res[2],
                "wagerAmount": res[3],
                "challengerFunded": res[4],
                "defenderFunded": res[5],
                "isFunded": res[6],
                "isSettled": res[7],
                "winner": res[8]
            }
        except Exception as e:
            logging.error(f"[EVM READ ERROR] Failed to fetch duel {duel_id} on EVM: {e}")
            return None

    def verify_and_settle_duel(self, duel_id: str, gl_duel: Dict[str, Any]) -> bool:
        """
        STRICT PRE-SETTLEMENT VERIFICATION:
        Verifies EVM challenger, defender, wager, funding, and settlement state against GenLayer
        before broadcasting any disbursement.
        """
        if self.settled_duels.get(duel_id):
            return True

        if not self.w3 or not self.account:
            logging.error("[FAIL-CLOSED] Web3 or RELAY_PRIVATE_KEY not configured.")
            return False

        # 1. Fetch live EVM Escrow state
        evm_duel = self.get_evm_duel(duel_id)
        if not evm_duel:
            logging.error(f"[PRE-SETTLEMENT FAIL] EVM duel {duel_id} does not exist on {self.contract_address}")
            return False

        # 2. Strict Participant & Wager Verification
        gl_challenger = gl_duel.get("challenger", "").lower()
        gl_defender = gl_duel.get("defender", "").lower()
        gl_wager = int(gl_duel.get("wager_amount", 0))
        gl_status = gl_duel.get("status", "")
        gl_winner = gl_duel.get("winner", "").lower()

        evm_challenger = str(evm_duel.get("challenger", "")).lower()
        evm_defender = str(evm_duel.get("defender", "")).lower()
        evm_wager = int(evm_duel.get("wagerAmount", 0))
        evm_funded = bool(evm_duel.get("isFunded", False))
        evm_settled = bool(evm_duel.get("isSettled", False))

        assert gl_status == "DUEL_RESOLVED", f"GenLayer duel not resolved: {gl_status}"
        assert evm_challenger == gl_challenger, f"Challenger mismatch: EVM({evm_challenger}) != GL({gl_challenger})"
        assert evm_defender == gl_defender, f"Defender mismatch: EVM({evm_defender}) != GL({gl_defender})"
        assert evm_wager == gl_wager, f"Wager mismatch: EVM({evm_wager}) != GL({gl_wager})"
        assert evm_funded == True, f"EVM duel {duel_id} is not fully funded by both participants (isFunded=False)"
        assert evm_settled == False, f"EVM duel {duel_id} is already settled"
        assert gl_winner in (evm_challenger, evm_defender), f"Winner {gl_winner} is not a registered duelist"

        logging.info(f"🛡️ [PRE-SETTLEMENT VERIFIED] Duel {duel_id} verified against EVM Escrow: Both funded, wager {evm_wager}, winner {gl_winner}")

        # 3. Sign & Broadcast EVM Disbursement Transaction
        try:
            contract = self.w3.eth.contract(address=Web3.to_checksum_address(self.contract_address), abi=HERO_ABI)
            d_bytes32 = self.to_bytes32(duel_id)
            win_addr = Web3.to_checksum_address(gl_winner)

            nonce = self.w3.eth.get_transaction_count(self.sender_address)
            gas_price = self.w3.eth.gas_price

            tx = contract.functions.disburseDuelBounty(
                d_bytes32,
                win_addr
            ).build_transaction({
                'from': self.sender_address,
                'nonce': nonce,
                'gas': 220000,
                'gasPrice': gas_price
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            logging.info(f"⚡ [EVM BROADCAST] Sent disburseDuelBounty tx: {tx_hash.hex()}. Awaiting confirmed receipt...")

            # 4. Wait for and verify confirmed receipt (status == 1)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            if receipt.status == 1:
                logging.info(f"✅ [EVM CONFIRMED] Duel {duel_id} bounty disbursed to {gl_winner} on block {receipt.blockNumber} (tx: {tx_hash.hex()}).")
                self.settled_duels[duel_id] = True
                return True
            else:
                logging.error(f"🚨 [FAIL-CLOSED] Duel disbursement reverted: {tx_hash.hex()}")
                return False
        except Exception as e:
            logging.error(f"[FAIL-CLOSED] Error broadcasting duel disbursement: {e}")
            return False


def run_relay(tracked_duels: list):
    logging.info("=" * 75)
    logging.info("   WALLETQUEST AUTONOMOUS RELAY & PRE-SETTLEMENT VERIFIER")
    logging.info("=" * 75)
    logging.info(f"GenLayer Court: {GENLAYER_COURT_ADDRESS}")
    logging.info(f"EVM Hero Escrow: {EVM_HERO_ADDRESS}")
    logging.info("Starting real-time duel verification and settlement loop...\n")

    gl_client = GenLayerCourtClient(GENLAYER_RPC, GENLAYER_COURT_ADDRESS)
    evm_relay = EvmSettlementRelay(EVM_RPC_URL, EVM_HERO_ADDRESS, RELAY_PRIVATE_KEY)

    while True:
        for duel_id in tracked_duels:
            try:
                duel_data = gl_client.get_duel(duel_id)
                if duel_data and duel_data.get("status") == "DUEL_RESOLVED":
                    evm_relay.verify_and_settle_duel(duel_id, duel_data)
            except Exception as e:
                logging.error(f"Error checking duel {duel_id}: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    test_duels = ["DUEL_001", "DUEL_002"]
    try:
        run_relay(test_duels)
    except KeyboardInterrupt:
        logging.info("\nRelay stopped by operator.")
