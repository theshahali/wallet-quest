// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title WalletQuestHero
 * @notice Production EVM Soulbound Character Badge & 2-Sided Collateralized PvP Arena Escrow.
 * @dev Mints on-chain RPG character credentials and manages 2-player native collateral duels
 * settled autonomously by GenLayer AI Game Master consensus signals.
 *
 * DUEL-ID MAPPING CONVENTION:
 * Standardized 1-to-1 mapping between GenLayer string identifier (e.g. "DUEL_001") and EVM bytes32:
 * `bytes32 duelId = bytes32(abi.encodePacked("DUEL_001"))` (left-aligned, zero-padded to 32 bytes).
 * Python / Web3 representation: `duel_id.encode('utf-8').ljust(32, b'\0')[:32]`.
 */
contract WalletQuestHero {
    string public name = "WalletQuest Hero Badge";
    string public symbol = "WQHERO";
    address public owner;
    address public oracleRelay;
    uint256 public nextTokenId;
    uint256 public totalVaultCollateral;

    struct HeroBadge {
        address wallet;
        string heroName;
        string heroClass;
        uint256 level;
        uint256 hp;
        uint256 attack;
        uint256 defense;
        bytes32 dnaHash;
        uint256 mintedAt;
    }

    struct DuelEscrow {
        bytes32 duelId;
        address challenger;
        address defender;
        uint256 wagerAmount;
        bool challengerFunded;
        bool defenderFunded;
        bool isFunded;
        bool isSettled;
        address winner;
    }

    mapping(uint256 => HeroBadge) public badges;
    mapping(address => uint256) public walletToBadge;
    mapping(bytes32 => DuelEscrow) public duels;

    event HeroBadgeMinted(uint256 indexed tokenId, address indexed wallet, string heroName, string heroClass, uint256 level);
    event DuelEscrowCreated(bytes32 indexed duelId, address indexed challenger, address indexed defender, uint256 wagerAmount);
    event DuelFunded(bytes32 indexed duelId, address indexed duelist, uint256 amount, bool isFullyFunded);
    event DuelSettled(bytes32 indexed duelId, address indexed winner, uint256 payout);

    modifier onlyOracle() {
        require(msg.sender == oracleRelay || msg.sender == owner, "Unauthorized: Only oracle relay or owner");
        _;
    }

    modifier onlyOwner() {
        require(msg.sender == owner, "Unauthorized: Only owner");
        _;
    }

    constructor(address _oracleRelay) {
        owner = msg.sender;
        oracleRelay = _oracleRelay;
        nextTokenId = 1;
    }

    function setOracleRelay(address _newRelay) external onlyOwner {
        require(_newRelay != address(0), "Invalid relay address");
        oracleRelay = _newRelay;
    }

    /**
     * @notice Mints a Soulbound RPG Character Badge bound to GenLayer hero stats.
     */
    function mintHeroBadge(
        address wallet,
        string calldata heroName,
        string calldata heroClass,
        uint256 level,
        uint256 hp,
        uint256 attack,
        uint256 defense,
        bytes32 dnaHash
    ) external onlyOracle returns (uint256) {
        require(wallet != address(0), "Invalid wallet address");
        require(walletToBadge[wallet] == 0, "Wallet already owns a Hero Badge");

        uint256 tokenId = nextTokenId++;
        badges[tokenId] = HeroBadge({
            wallet: wallet,
            heroName: heroName,
            heroClass: heroClass,
            level: level,
            hp: hp,
            attack: attack,
            defense: defense,
            dnaHash: dnaHash,
            mintedAt: block.timestamp
        });

        walletToBadge[wallet] = tokenId;
        emit HeroBadgeMinted(tokenId, wallet, heroName, heroClass, level);
        return tokenId;
    }

    /**
     * @notice Creates a new 2-player PvP Duel Escrow bound to GenLayer registered participants.
     */
    function createDuel(bytes32 duelId, address challenger, address defender, uint256 wagerAmount) external {
        require(duels[duelId].wagerAmount == 0, "Duel already exists");
        require(challenger != address(0) && defender != address(0), "Invalid duelist addresses");
        require(challenger != defender, "Self-duels prohibited");
        require(wagerAmount > 0, "Wager must be > 0");

        duels[duelId] = DuelEscrow({
            duelId: duelId,
            challenger: challenger,
            defender: defender,
            wagerAmount: wagerAmount,
            challengerFunded: false,
            defenderFunded: false,
            isFunded: false,
            isSettled: false,
            winner: address(0)
        });

        emit DuelEscrowCreated(duelId, challenger, defender, wagerAmount);
    }

    /**
     * @notice Funds native collateral for a registered duel. Requires both registered participants to deposit.
     */
    function fundDuel(bytes32 duelId) external payable {
        DuelEscrow storage d = duels[duelId];
        require(d.wagerAmount > 0, "Duel does not exist");
        require(!d.isSettled, "Duel already settled");
        require(msg.value == d.wagerAmount, "Exact native wager amount required");

        if (msg.sender == d.challenger) {
            require(!d.challengerFunded, "Challenger already funded");
            d.challengerFunded = true;
        } else if (msg.sender == d.defender) {
            require(!d.defenderFunded, "Defender already funded");
            d.defenderFunded = true;
        } else {
            revert("Sender is not a registered duelist for this duel");
        }

        totalVaultCollateral += msg.value;

        if (d.challengerFunded && d.defenderFunded) {
            d.isFunded = true;
        }

        emit DuelFunded(duelId, msg.sender, msg.value, d.isFunded);
    }

    /**
     * @notice Disburses the full combat prize pool (2x wager) to the winning duelist upon verified GenLayer resolution.
     */
    function disburseDuelBounty(bytes32 duelId, address winner) external onlyOracle {
        DuelEscrow storage d = duels[duelId];
        require(d.isFunded, "Duel escrow not fully funded by both participants");
        require(!d.isSettled, "Duel already settled");
        require(winner == d.challenger || winner == d.defender, "Winner must be registered duelist");

        uint256 payout = d.wagerAmount * 2;
        require(address(this).balance >= payout, "[ERR_UNDERFUNDED] Vault balance insufficient for duel payout");

        d.isSettled = true;
        d.winner = winner;

        (bool sent, ) = payable(winner).call{value: payout}("");
        require(sent, "Native transfer to winner failed");

        emit DuelSettled(duelId, winner, payout);
    }

    /**
     * @notice View function to retrieve full duel escrow state for relay pre-settlement verification.
     */
    function getDuelEscrow(bytes32 duelId) external view returns (
        bytes32 id,
        address challenger,
        address defender,
        uint256 wagerAmount,
        bool challengerFunded,
        bool defenderFunded,
        bool isFunded,
        bool isSettled,
        address winner
    ) {
        DuelEscrow memory d = duels[duelId];
        return (
            d.duelId,
            d.challenger,
            d.defender,
            d.wagerAmount,
            d.challengerFunded,
            d.defenderFunded,
            d.isFunded,
            d.isSettled,
            d.winner
        );
    }

    receive() external payable {}
}
