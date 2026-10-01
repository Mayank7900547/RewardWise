# Git workflow for the first review

These are real commands you run yourself, one branch at a time, so the history you show is genuine.
Do them over the course of your work session rather than in one burst; write each commit message in your own words if you prefer.
(The commit plan was dry-run in a scratch repository: the test suite passed after every merge.)

**Layout assumed:** the starter project is in `RewardWise/` and the updated project (from
`RewardWise_v0.2.zip`) is unzipped next to it as `RewardWise_new/`. Run everything from inside `RewardWise/`.
The commands use plain `cp` and forward slashes so they work in Git Bash, macOS/Linux and PowerShell.

## 0. One-time setup
```
git init -b main
git config user.name "Your Name"
git config user.email "you@example.com"
git add .
git commit -m "Import starter prototype"
```
Create an empty repository on GitHub (no README), then:
```
git remote add origin https://github.com/<your-username>/RewardWise.git
git push -u origin main
```

## 1. Project hygiene
```
git switch -c chore/project-hygiene
cp ../RewardWise_new/pytest.ini pytest.ini
cp ../RewardWise_new/.gitignore .gitignore
cp ../RewardWise_new/.dockerignore .dockerignore
cp ../RewardWise_new/requirements.txt requirements.txt
git add pytest.ini .gitignore .dockerignore requirements.txt
git commit -m "chore: add pytest config, dockerignore and updated dependency pins"
cp ../RewardWise_new/Dockerfile Dockerfile
cp ../RewardWise_new/docker-compose.yml docker-compose.yml
git add Dockerfile docker-compose.yml
git commit -m "chore(docker): add healthcheck, data volume and test profile"
python -m pytest -q
git switch main
git merge --no-ff chore/project-hygiene -m "Merge chore/project-hygiene"
```

## 2. Data schema
```
git switch -c feature/data-schema
cp ../RewardWise_new/data/cards.json data/cards.json
cp ../RewardWise_new/data/expenses.csv data/expenses.csv
cp ../RewardWise_new/docs/data_dictionary.md docs/data_dictionary.md
git add data docs/data_dictionary.md
git commit -m "feat(data): schema v2 with issuer, exclusions, min transaction, balances; add Card D and expense description/card columns"
cp ../RewardWise_new/rewardwise/__init__.py rewardwise/__init__.py
cp ../RewardWise_new/rewardwise/formatting.py rewardwise/formatting.py
cp ../RewardWise_new/rewardwise/data.py rewardwise/data.py
cp ../RewardWise_new/tests/conftest.py tests/conftest.py
cp ../RewardWise_new/tests/test_data.py tests/test_data.py
git add rewardwise/__init__.py rewardwise/formatting.py rewardwise/data.py tests/conftest.py tests/test_data.py
git commit -m "feat(data): validated loaders for cards and expenses (rejects NaN/inf amounts)"
python -m pytest -q
git switch main
git merge --no-ff feature/data-schema -m "Merge feature/data-schema"
```

## 3. Reward engine and monthly allocation
```
git switch -c feature/reward-engine
cp ../RewardWise_new/rewardwise/rewards.py rewardwise/rewards.py
cp ../RewardWise_new/tests/test_rewards.py tests/test_rewards.py
git add rewardwise/rewards.py tests/test_rewards.py
git commit -m "feat(rewards): eligibility, exclusions, minimum transaction and capped card rewards"
cp ../RewardWise_new/rewardwise/goals.py rewardwise/goals.py
cp ../RewardWise_new/tests/test_goals.py tests/test_goals.py
git add rewardwise/goals.py tests/test_goals.py
git commit -m "feat(goals): milestone status, whole-month allocation with explanations and labeled heuristic fallback"
python -m pytest -q
git switch main
git merge --no-ff feature/reward-engine -m "Merge feature/reward-engine"
```

## 4. Expense tracker
```
git switch -c feature/expense-tracker
cp ../RewardWise_new/rewardwise/tracker.py rewardwise/tracker.py
cp ../RewardWise_new/tests/test_tracker.py tests/test_tracker.py
git add rewardwise/tracker.py tests/test_tracker.py
git commit -m "feat(tracker): monthly totals, category and card summaries, prior milestone spend from actuals"
python -m pytest -q
git switch main
git merge --no-ff feature/expense-tracker -m "Merge feature/expense-tracker"
```

## 5. Card recommendation
```
git switch -c feature/card-recommendation
cp ../RewardWise_new/rewardwise/recommend.py rewardwise/recommend.py
cp ../RewardWise_new/tests/test_recommend.py tests/test_recommend.py
git add rewardwise/recommend.py tests/test_recommend.py
git commit -m "feat(recommend): rank cards for one purchase with milestone-aware explanations"
python -m pytest -q
git switch main
git merge --no-ff feature/card-recommendation -m "Merge feature/card-recommendation"
```

## 6. Streamlit dashboard (and retire the old engine)
```
git switch -c feature/streamlit-dashboard
cp ../RewardWise_new/app.py app.py
cp ../RewardWise_new/tests/test_app_smoke.py tests/test_app_smoke.py
git add app.py tests/test_app_smoke.py
git commit -m "feat(ui): five-page dashboard: overview, portfolio, expenses, comparison, monthly allocation"
git rm rewardwise/engine.py tests/test_engine.py
git commit -m "refactor: remove engine.py, now split into rewards.py and goals.py"
python -m pytest -q
git switch main
git merge --no-ff feature/streamlit-dashboard -m "Merge feature/streamlit-dashboard"
```

## 7. Documentation
```
git switch -c docs/first-review
cp ../RewardWise_new/README.md README.md
cp ../RewardWise_new/docs/architecture.md docs/architecture.md
cp ../RewardWise_new/docs/design_decisions.md docs/design_decisions.md
cp ../RewardWise_new/docs/DEMO_SCRIPT.md docs/DEMO_SCRIPT.md
cp ../RewardWise_new/docs/GIT_WORKFLOW.md docs/GIT_WORKFLOW.md
git add README.md docs
git commit -m "docs: README, architecture diagram, design decisions, demo script and git workflow"
git switch main
git merge --no-ff docs/first-review -m "Merge docs/first-review"
git tag -a v0.2.0-first-review -m "First project review"
git push origin --all
git push origin --tags
```

## 7b. Stage 2 (v0.3): reliability and explainability
Unzip `RewardWise_v0_3.zip` next to your project as `RewardWise_v0_3/`. Run from inside `RewardWise/`, after v0.2 is merged
into `main` (steps 0 to 7). If you already did steps 0 to 7, just continue here. This adds history on top of v0.2; it does not rewrite it.
```
git switch main
git switch -c feature/explainable-allocation
cp ../RewardWise_v0_3/rewardwise/formatting.py rewardwise/formatting.py
cp ../RewardWise_v0_3/rewardwise/goals.py rewardwise/goals.py
cp ../RewardWise_v0_3/rewardwise/recommend.py rewardwise/recommend.py
git add rewardwise
git commit -m "feat(recommend): plain-language plan explanations, milestone story and voucher-aware baseline"
cp ../RewardWise_v0_3/tests/test_readme_scenario.py tests/test_readme_scenario.py
cp ../RewardWise_v0_3/tests/test_explanations.py tests/test_explanations.py
cp ../RewardWise_v0_3/data/demo_shortfall.csv data/demo_shortfall.csv
git add tests data
git commit -m "test: end-to-end README scenario, explanation and no-extra-spending tests"
python -m pytest -q
cp ../RewardWise_v0_3/app.py app.py
cp ../RewardWise_v0_3/tests/test_app_scenarios.py tests/test_app_scenarios.py
git add app.py tests/test_app_scenarios.py
git commit -m "feat(ui): separate actual/planned and direct/milestone rewards, show current/projected/remaining, fictional-data notice"
python -m pytest -q
git switch main
git merge --no-ff feature/explainable-allocation -m "Merge feature/explainable-allocation"

git switch -c docs/v0.3-demo-and-checklists
cp ../RewardWise_v0_3/README.md README.md
cp ../RewardWise_v0_3/CHANGELOG.md CHANGELOG.md
cp ../RewardWise_v0_3/docs/architecture.md docs/architecture.md
cp ../RewardWise_v0_3/docs/design_decisions.md docs/design_decisions.md
cp ../RewardWise_v0_3/docs/DEMO_SCRIPT.md docs/DEMO_SCRIPT.md
cp ../RewardWise_v0_3/docs/DOCKER_CHECKLIST.md docs/DOCKER_CHECKLIST.md
cp ../RewardWise_v0_3/docs/GIT_WORKFLOW.md docs/GIT_WORKFLOW.md
git add README.md CHANGELOG.md docs
git commit -m "docs: v0.3 demo script, honest baselines, Docker checklist and changelog"
git switch main
git merge --no-ff docs/v0.3-demo-and-checklists -m "Merge docs/v0.3-demo-and-checklists"
git tag -a v0.3.0-first-review -m "First review: reliable, explainable baseline"
git push origin --all
git push origin --tags
```

## 8. Show it at the review
```
git log --oneline --graph --decorate --all
python -m pytest -q
```

## Afterwards
Branch names for the second review (suggested): `feature/goal-selection`, `feature/html-report`,
`feature/edge-case-rules`, `test/expanded-suite`. Same pattern: branch, commit in small pieces, test, merge with `--no-ff`.
