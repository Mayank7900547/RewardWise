# Data dictionary

All card data is **fictional**.

## data/cards.json (list of cards)
| Field | Required | Meaning |
|---|---|---|
| `id` | yes | unique identifier, referenced by the expense `card` column |
| `name` | yes | display name |
| `issuer` | no | fictional issuer name |
| `reward_type` | yes | `cashback` or `points` |
| `base_rate` | yes | cashback fraction (0.01 = 1%) or points per ₹100 |
| `category_rates` | no | category -> rate, same units as `base_rate` |
| `eligible_categories` | no | if set, ONLY these categories earn direct rewards (default: all) |
| `excluded_categories` | no | categories that earn nothing and do not count towards the milestone |
| `min_transaction` | no | expenses below this earn nothing (₹, default 0) |
| `monthly_reward_cap` | no | maximum estimated direct reward per month in ₹ (null = none) |
| `point_value` | no | assumed ₹ per point (estimate; cashback uses 1) |
| `reward_balance` | no | current balance in native units (₹ cashback or points); display only |
| `milestone` | no | `{name, eligible_spend, voucher_value, period, eligible_categories?}` or null |
| `fictional` | no | `true` for every sample card |

Validation (`data.validate_cards`) rejects negative/NaN rates, unknown categories, duplicate ids,
unknown reward types and zero point values on points cards.

## data/expenses.csv
| Column | Meaning |
|---|---|
| `date` | YYYY-MM-DD; the month is derived from it |
| `description` | merchant or note |
| `category` | groceries, shopping, dining, fuel, travel, utilities, other |
| `amount` | positive, finite amount in ₹ |
| `status` | `planned` (still to spend) or `actual` (already spent) |
| `card` | card id used; meaningful for `actual` rows (feeds milestone progress); blank allowed |

Blank rows are dropped; invalid rows are rejected with their row number.

## Milestone spend
Milestone progress = eligible `actual` spend on that card (from the tracker) + optional extra spend
typed on the allocation page. It is history, never a new expense.

## Optional benefit fields on a card (v0.3 scenario alignment; all default to zero, old files stay valid)
| field | meaning |
|---|---|
| `discount_rules` | list of `{categories|null, rate, flat, min_transaction, max_discount}`; discount value = amount x rate + flat. Not capped. |
| `bonus_points` | `{per_100, categories|null, point_value?}`; bonus points x point value (defaults to the card's `point_value`). Not capped. |
| `other_benefits` | list of `{name, value, categories|null, min_transaction}`; flat rupee value per qualifying expense. Not capped. |

`monthly_reward_cap` limits the **Reward** component only.

## Result fields
`reward_value`, `discount_value`, `points_value`, `other_benefit_value`, `total_benefit` (per expense row); month totals add
`immediate_benefit`, `voucher_value`, `total_value` (= Final Score). `unitemised_value` is used only by scenario fixtures that give a
pairing total without a breakdown.

## Scenario fixtures (`data/scenarios/*.json`)
Cards, expenses and per-pair `pair_benefits` (`{reward, discount, points, other}` or `{"total": n}`) transcribed from the finalized slides.
Pairings not listed are treated as unavailable. Used only for tests/demos; `pair_benefits` overrides the rule-based calculation.
