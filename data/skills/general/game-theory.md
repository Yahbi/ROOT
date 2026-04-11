---
name: Game Theory
description: Nash equilibrium, dominant strategies, mechanism design, and auction theory for strategic decision-making
version: "1.0.0"
author: ROOT
tags: [general, game-theory, strategy, equilibrium, auctions]
platforms: [all]
---

# Game Theory

Apply mathematical models of strategic interaction to predict behavior, design incentive systems, and make optimal decisions under competition.

## Nash Equilibrium

- **Definition**: Strategy profile where no player can improve their payoff by unilaterally changing strategy
- **Existence**: Every finite game has at least one Nash equilibrium (possibly in mixed strategies)
- **Pure strategy NE**: Each player chooses a single action; found by checking all best-response combinations
- **Mixed strategy NE**: Players randomize over actions; indifference condition: `E[payoff(action_1)] = E[payoff(action_2)]`
- **Finding NE**: For 2x2 games, use best-response underlining; for larger games, use support enumeration or Lemke-Howson
- **Multiple equilibria**: Many games have multiple NE; refinements (trembling hand, subgame perfect) narrow selection

## Dominant Strategies

- **Strictly dominant**: Strategy A is better than B regardless of opponent's choice; always play dominant strategy
- **Weakly dominant**: Strategy A is at least as good as B for all opponent choices, strictly better for some
- **Iterated dominance**: Eliminate dominated strategies iteratively; remaining strategies form rationalizable set
- **Prisoner's Dilemma**: Both players have dominant strategy to defect; mutual defection is NE but Pareto-suboptimal
- **Application in trading**: If a strategy is dominant regardless of market direction, it should always be employed

## Key Game Models

### Repeated Games
- **Folk theorem**: In infinitely repeated games, cooperation can be sustained if discount factor delta > (payoff_defect - payoff_cooperate) / (payoff_defect - payoff_punish)
- **Tit-for-tat**: Cooperate initially, then mirror opponent's last move; robust in tournaments
- **Grim trigger**: Cooperate until opponent defects, then defect forever; harshest punishment
- **Application**: Repeated market interactions (supplier relationships, market making) enable cooperative equilibria

### Sequential Games
- **Extensive form**: Game tree with decision nodes; solve by backward induction
- **Subgame perfect equilibrium**: NE in every subgame; eliminates non-credible threats
- **Commitment value**: Ability to commit to a strategy (first-mover advantage) can increase payoff
- **Stackelberg**: Leader commits to quantity/price, follower best-responds; leader advantage

### Bayesian Games (Incomplete Information)
- **Type**: Private information each player holds; Harsanyi transformation converts to game of imperfect information
- **Bayes-Nash equilibrium**: Strategy maximizes expected payoff given beliefs about opponents' types
- **Signaling**: Informed player sends costly signal to reveal type (education as ability signal)
- **Screening**: Uninformed player designs menu to induce self-selection (insurance deductibles)

## Mechanism Design

- **Reverse game theory**: Design the rules of the game to achieve desired outcomes
- **Revelation principle**: Any mechanism can be replicated by a direct mechanism where truthful reporting is optimal
- **VCG mechanism**: Vickrey-Clarke-Groves; achieves efficient allocation with truthful reporting; each player pays externality they impose
- **Incentive compatibility**: Mechanism where truthful reporting is a dominant strategy (strategy-proof)
- **Individual rationality**: Participation must be voluntary; expected payoff from participating exceeds outside option
- **Applications**: Token economics, marketplace rules, compensation design, voting systems

## Auction Theory

### Auction Formats
| Format | Rules | Revenue Equivalence |
|--------|-------|-------------------|
| English (ascending) | Open outcry, highest bid wins | Yes (risk-neutral) |
| Dutch (descending) | Price drops until someone accepts | Equivalent to first-price sealed |
| First-price sealed | Highest sealed bid wins at bid price | Bid shading optimal |
| Second-price (Vickrey) | Highest bid wins at second-highest price | Truthful bidding is dominant |

### Bidding Strategy
- **Second-price**: Bid your true value; dominant strategy regardless of opponents
- **First-price**: Shade bid below value; `optimal_bid = value * (n-1)/n` for n symmetric risk-neutral bidders
- **Common value**: Winner's curse — winning means you likely overestimated; adjust downward
- **Revenue equivalence**: Under standard assumptions, all four auction formats yield same expected revenue

### Auction Design
- **Reserve price**: Minimum acceptable bid; optimal reserve excludes some bidders to extract more surplus
- **Entry fees**: Reduce participation but increase bid intensity among entrants
- **Information disclosure**: Revealing common-value signals reduces winner's curse; increases bids and revenue
- **Bundle auctions**: Selling items together vs separately; complements favor bundling, substitutes favor separation

## Risk Management

- **Equilibrium multiplicity**: When multiple NE exist, prediction is uncertain; use refinements or simulation
- **Bounded rationality**: Real players don't perfectly optimize; incorporate behavioral models (quantal response)
- **Model sensitivity**: Small changes in payoffs can shift equilibria; robustness check all assumptions
- **Evolutionary dynamics**: In large populations, replicator dynamics determine which strategies survive long-term
- **Cooperative vs non-cooperative**: Many real situations blend both; pure non-cooperative models may be too pessimistic
