# ARC-AGI-3 Emoji Glyph Engine

## Status

Experimental Python architecture added alongside the existing ARC3 controller. It is not a verified benchmark solver and has not been run against the official private benchmark.

## Research mapping

The architecture draws on established research; this is not a claim that every university library worldwide was exhaustively searched.

- Sutton & Barto, Reinforcement Learning: An Introduction — action-value estimation, exploration/exploitation, model-based planning.
- Browne et al., A Survey of Monte Carlo Tree Search Methods (2012) — selection, expansion, simulation and backup.
- Kochenderfer, Wheeler & Wray, Algorithms for Decision Making — belief states, uncertainty and sequential decisions.
- Zuccotto et al., Online model adaptation in Monte Carlo tree search planning (2024) — adapting approximate transition models from new observations.
- ARC Prize Foundation, ARC-AGI-3 technical report (2026) — goal discovery, environment modeling and action efficiency.

Public sources:
- https://arcprize.org/media/ARC_AGI_3_Technical_Report.pdf
- https://www.incompleteideas.net/book/the-book-2nd.html
- https://link.springer.com/article/10.1007/s11081-024-09896-2
- https://mitpress.mit.edu/9780262047012/algorithms-for-decision-making/

## Glyph vocabulary

| Glyph | Canonical operation | Meaning |
|---|---|---|
| 👁️ | observe | Read current observation |
| 🔍 | segment | Extract candidate objects |
| 🧩 | relate | Describe spatial relationships |
| 📐 | geometry | Compute shape and topology |
| ↔️ | track | Compare observations over time |
| 🧠 | hypothesize | Maintain candidate mechanics |
| 🔮 | predict | Produce evidence-tagged outcomes |
| 🧪 | probe | Select an informative legal experiment |
| 🌳 | search | Run bounded planning |
| 🎯 | select | Choose among supplied legal actions |
| ▶️ | act | Cross the environment action boundary |
| ↩️ | undo | Use only if supplied as legal |
| ✔️ | verify | Compare prediction with observation |
| 💾 | memorize | Store verified transition evidence |

Emoji are readable aliases only. Canonical operation names and typed Python contracts carry semantics.

## Architecture

1. arc3/glyph_dsl.py parses and validates the glyph program. It does not call the game environment.
2. arc3/transition_learner.py learns exact-coordinate grid edit templates from observed before/after pairs. Predictions require matching preconditions and remain labeled predictions.
3. arc3/belief_mcts.py searches only actions supplied as legal at the root. Predicted outcomes are one-step leaf estimates; deeper rollout uses observed transitions only.
4. arc3/glyph_agent.py connects the existing strategy-prior generator, world model, transition learner and belief MCTS.
5. The current belief search is a bounded root-action UCB controller with sampled observed rollouts and predicted one-step leaves; it is not yet a fully branching belief-state tree.

## Limitations

- The transition learner supports one 2-D grid, not layered frames.
- Exact-coordinate templates may not generalize to moving or translated objects.
- Predicted leaf values are heuristic estimates, not calibrated win probabilities.
- The new agent still needs wiring into the official SDK runner.
- Benchmark performance and action efficiency have not been measured.
- No live benchmark, paid inference, or private-set evaluation is performed by the unit tests.

## Suggested local validation

Run the focused test with:
    python -m unittest tests.test_arc3_glyph_engine

Then run the full repository test suite. Integrate GlyphArc3Agent behind an explicit runner policy option and compare against the existing policy on identical public games, seeds and action budgets.
