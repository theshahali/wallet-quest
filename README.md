# WalletQuest — Autonomous On-Chain RPG Character Generation & Duel Engine

> **"The world's first on-chain RPG protocol that converts real-world cross-chain wallet transaction history into verifiable game characters and adjudicates PvP arena duels via GenLayer AI consensus."**

---

## 🔗 Verified Deployments & Links
- **GenLayer Explorer Contract**: [`0x037A962c2be3781Fb31a5faF3fb22D6CBb555049`](https://explorer-studio.genlayer.com/address/0x037A962c2be3781Fb31a5faF3fb22D6CBb555049)
- **GitHub Repository**: [`https://github.com/theshahali/wallet-quest`](https://github.com/theshahali/wallet-quest)
- **Live DApp Dashboard**: [`https://wallet-quest-delta.vercel.app/`](https://wallet-quest-delta.vercel.app/)
- **Target Evidence Snapshot**: [`https://theshahali.github.io/wallet-quest/demo/mock_wallet_degen.html`](https://theshahali.github.io/wallet-quest/demo/mock_wallet_degen.html)

---

## 🛡️ Complete Collateral Path & Pre-Settlement Verification (Pavel Kolosov Hardening)

### 1. Documented Duel-ID Mapping
Standardized 1-to-1 mapping between GenLayer string identifier (e.g. `"DUEL_001"`) and EVM `bytes32`:
- **EVM Solidity**: `bytes32 duelId = bytes32(abi.encodePacked("DUEL_001"))` (left-aligned, zero-padded to 32 bytes).
- **Python Web3 Relay**: `duel_id.encode('utf-8').ljust(32, b'\0')[:32]`.

### 2. Matching 2-Sided EVM Duel Creation & Collateral Funding
- **Creation**: `createDuel(bytes32 duelId, address challenger, address defender, uint256 wagerAmount)` on `contracts/WalletQuestHero.sol`.
- **Challenger Funding**: Challenger deposits exact native collateral (`fundDuel` with `msg.value == wagerAmount`).
- **Defender Funding**: Defender deposits exact native collateral (`fundDuel` with `msg.value == wagerAmount`).
- **Collateralization Guard**: `isFunded` is set to `true` strictly when both registered participants have funded their respective sides.

### 3. Strict Pre-Settlement State Verification
Before broadcasting any payout transaction, `relay/WalletQuestRelay.py` queries `duels(duelId)` and `getDuelEscrow(duelId)` on EVM and asserts:
- `evm_duel.challenger == genlayer_duel.challenger`
- `evm_duel.defender == genlayer_duel.defender`
- `evm_duel.wagerAmount == genlayer_duel.wager_amount`
- `evm_duel.isFunded == True` (both participants verified funded)
- `evm_duel.isSettled == False` (idempotency guard)
- `genlayer_duel.status == "DUEL_RESOLVED"`
- `genlayer_duel.winner in (evm_duel.challenger, evm_duel.defender)`

### 4. Verified Transaction Receipts on Both Chains
- Evaluates GenLayer single-round consensus output via `gen_callView`.
- Broadcasts signed ECDSA transaction `disburseDuelBounty(duelId, winner)` to EVM.
- Awaits `w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)` and asserts `receipt.status == 1`.

### 5. Dynamic Confirmed On-Chain State in Frontend
- Frontend calls `gen_callView("get_duel", [duelId])` upon resolution and displays the confirmed winner, payout amount ($2 \times \text{wager}$), and finalized combat log rather than a fixed success message.
