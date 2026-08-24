# WalletQuest — Autonomous On-Chain RPG Character Generation & Duel Engine

> **"The world's first on-chain RPG protocol that converts real-world cross-chain wallet transaction history into verifiable game characters and adjudicates PvP arena duels via GenLayer AI consensus."**

---

## 🔗 Verified Deployments & Links
- **GenLayer Explorer Contract**: [`0x037A962c2be3781Fb31a5faF3fb22D6CBb555049`](https://explorer-studio.genlayer.com/address/0x037A962c2be3781Fb31a5faF3fb22D6CBb555049)
- **GitHub Repository**: [`https://github.com/theshahali/wallet-quest`](https://github.com/theshahali/wallet-quest)
- **Live DApp Dashboard**: [`https://wallet-quest.vercel.app/`](https://wallet-quest.vercel.app/)

---

## ❖ PROTOCOL OVERVIEW
WalletQuest transforms static blockchain transaction histories into living, verifiable RPG champions. Using GenLayer's natural language perception and AI consensus, the protocol audits lifetime transaction graphs, protocol diversity, and liquidation scars to assign balanced stats, discrete classes, and customized lore.

---

## ❖ ARCHITECTURAL INVARIANTS & STEWARD COMPLIANCE
1. **Multi-Layer Anti-Replay Uniqueness**:
   - **Unique Summon ID**: Prevents duplicate summon attempts (`[ERR_REPLAY_01]`).
   - **One-Hero-Per-Wallet Binding**: Enforces strict uniqueness so a wallet address cannot forge duplicate characters (`[ERR_REPLAY_02]`). Verified on-chain via live revert.
2. **Anti-Self-Matching PvP Arena Guard**:
   - In Arena duels, the contract asserts `challenger != defender`, blocking self-challenging exploits (`[ERR_SELF_DUEL]`). Both duelists must be verified summoned heroes.
3. **Deterministic Attribute Mathematical Calibration**:
   - Level, HP, Mana, Attack, Defense, and Critical Hit rates are calculated from actual verified on-chain metrics (transaction count, volume, liquidation scars), ensuring 100% fair gameplay balance.
4. **Single-Round Unified AI Consensus**:
   - Evaluates the 24/7 UTC Atomic Clock (`timeapi.io`) and wallet telemetry in 1 parallel prompt pass (0 leader rotations).
5. **Production Signed Web3 EVM Escrow**:
   - `relay/WalletQuestRelay.py` validates participant binding and duel escrow state on `WalletQuestHero.sol`, signing ECDSA transactions and confirming on-chain receipts (`status == 1`).

---

## ❖ HERO ARCHETYPES & STAT MATRIX
- **`DEFI_ARCHMAGE`**: High lending/borrowing volume, complex smart contracts (High Mana & Arcane Attack).
- **`DEX_BERSERKER`**: High-frequency swaps, liquidation scars (High Physical Attack & 28% Critical Rate).
- **`NFT_SHADOW_ROGUE`**: Extensive collection minting & marketplace flips (High Agility & 32% Stealth Crit).
- **`YIELD_CLERIC`**: Long holding periods, conservative staking pools (High Base HP & 400 Defense).
