---
name: Crypto Risk Management
description: Crypto-specific risks including smart contract, oracle, regulatory, and custody risks
version: "1.0.0"
author: ROOT
tags: [crypto, risk, smart-contract, regulatory, custody, security]
platforms: [all]
---

# Crypto-Specific Risk Management

Identify and mitigate risks unique to cryptocurrency and DeFi investments.

## Smart Contract Risk

### Assessment Criteria
- **Audit status**: Audited by top firms (Trail of Bits, OpenZeppelin, Certora)?
- **Code complexity**: Simpler contracts have smaller attack surface
- **Upgrade mechanism**: Upgradeable proxies can be changed — check timelock duration
- **Battle-tested duration**: Unmodified code live for 12+ months = lower risk
- **Bug bounty**: Active Immunefi bounty signals confidence and incentivizes white hats

### Mitigation
- Never allocate > 10% of crypto portfolio to a single protocol
- Prefer protocols with > $100M TVL and > 12 months without exploit
- Monitor exploit databases (Rekt, DeFiLlama hacks) for similar protocol vulnerabilities
- Use DeFi insurance (Nexus Mutual, InsurAce) for large positions

## Oracle Risk

### How Oracles Fail
- **Price manipulation**: Flash loan attacks manipulate spot price → oracle reads bad price
- **Stale data**: Oracle stops updating during high congestion → liquidations on stale prices
- **Single source**: Oracle relies on one exchange — exchange manipulation = oracle manipulation

### Mitigation
- Prefer Chainlink or Pyth (multi-source, decentralized) over custom oracles
- Check oracle heartbeat — updates should be at least every 60 seconds for volatile assets
- TWAP (time-weighted average price) oracles resist flash loan attacks
- Verify the protocol uses circuit breakers on oracle price deviations

## Regulatory Risk

### Current Landscape
- SEC enforcement actions against tokens classified as securities
- Stablecoin regulation evolving (reserve requirements, issuer licensing)
- DeFi KYC/AML requirements expanding in EU (MiCA), US, and Asia
- Exchange delistings can cause immediate 30-50% price drops

### Mitigation
- Avoid tokens with ongoing SEC investigations
- Diversify across jurisdictions — not all regulatory action is global
- Maintain ability to exit positions within 24 hours
- Track regulatory calendar and comment periods for major rule proposals

## Custody Risk

### Self-Custody
- Hardware wallet for long-term holdings (Ledger, Trezor)
- Multi-sig (2-of-3) for amounts > $50K
- Secure seed phrase storage: metal backup, geographically distributed

### Exchange Custody
- Never hold > 20% of portfolio on any single exchange
- Choose exchanges with proof-of-reserves and regulatory licenses
- Enable all security features: 2FA, withdrawal whitelist, anti-phishing codes

## Risk Budget by Category

| Risk Category | Max Allocation | Monitoring Frequency |
|--------------|---------------|---------------------|
| Blue chip (BTC, ETH) | 60-70% | Weekly |
| Large DeFi protocols | 15-25% | Daily |
| Mid-cap altcoins | 5-10% | Daily |
| New/unaudited protocols | 0-5% | Real-time |
