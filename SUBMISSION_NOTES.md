WalletQuest converts on-chain wallet histories into verifiable RPG heroes and adjudicates PvP arena duels via GenLayer AI consensus.

PAVEL KOLOSOV REMEDIATION COMPLETED:
1. Application EVM Connection: page.tsx connects to actual createDuel and fundDuel calls on WalletQuestHero.sol using identical duelId, participants, and wager as GenLayer. Only reports funding after EVM receipt.status == 1.
2. Collision-Safe Mapping: Standardized Keccak-256 (Web3.keccak / viem keccak256) mapping between string duel IDs and EVM bytes32.
3. Autonomous Relay Discovery: relay/WalletQuestRelay.py dynamically discovers application-created duel IDs from EVM DuelEscrowCreated logs, verifying isFunded == true and GenLayer consensus before disbursement.
4. Live E2E Test Suite (No Mocks): test/test_collateral_lifecycle.py & test_live_e2e_contracts.js exercise the live deployed GenLayer contract (0x037A...049) via Studio RPC and real EVM calldata (11/11 passing).
