# Docker checklist (verify this yourself on Windows before you say "it runs in Docker")

Docker configuration is included but Docker was not executed in the current development environment because Docker was unavailable.

## What has and has not been verified
| Check | Status |
|---|---|
| Dockerfile / compose files parse; two services (`rewardwise`, `tests`); no CRLF-sensitive shell scripts | checked statically |
| `pip install -r requirements.txt` in a clean Python 3.12 virtualenv, then the full test suite (Streamlit 1.64 + pandas 3.0 and Streamlit 1.50 + pandas 2.3) | passed |
| The exact `CMD` (`streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true`) and the exact `HEALTHCHECK` command outside Docker | worked (`ok`, HTTP 200) |
| Only the files that survive `.dockerignore` are needed to run the tests | passed |
| **`docker build`, `docker compose up`, container health, the data bind mount, the test container on Windows** | **NOT verified: Docker was not available where this was prepared** |

## Steps (PowerShell, from the project folder)
1. Start **Docker Desktop** and wait until it says it is running. Check: `docker --version` and `docker compose version`
   (you need Compose v2, the `docker compose` form with a space).
2. `docker compose config` should print the resolved configuration with no error.
3. Stop any local `streamlit run` first (port 8501 must be free), then: `docker compose up --build`.
   The first build downloads the Python image and packages (a few minutes). Success looks like a line
   "You can now view your Streamlit app in your browser".
4. Open **http://localhost:8501** (not 0.0.0.0). Click through all five pages.
5. In a second terminal: `docker compose ps`. The status should become **healthy** (it may say "health: starting" for up to about a minute).
6. Tests in the container: `docker compose --profile test run --rm tests`. Expect `124 passed`.
7. Optional bind-mount check: edit `data\expenses.csv` on your machine, press F5 in the browser; the change should appear.
8. Stop with Ctrl+C, then `docker compose down`.

## If something fails
| Symptom | Likely cause / fix |
|---|---|
| `port is already allocated` | another process uses 8501: stop local Streamlit or change the left side of `"8501:8501"` |
| `docker: command not found` or the daemon is not running | start Docker Desktop, wait for it to be ready |
| `unknown flag: --profile` or `docker compose` not found | old Docker; update Docker Desktop |
| bind-mount / "drive not shared" error | keep the project under `C:\Users\<you>` or enable file sharing in Docker Desktop settings |
| build stops at the `pip install` step | network/VPN/proxy problem; retry, and copy the error text if it persists |
| the page does not load but the container is up | you opened 0.0.0.0 instead of localhost |

Do not claim "Docker works" in the review until steps 3 to 6 succeed on your machine. If they do, say exactly that.
If any step fails, copy the terminal output and it can be fixed.
