# telemetry.py
import os, sys, logging, warnings

def go_quiet(default_level="ERROR"):
    """
    Silence 3rd-party telemetry/log spam while keeping:
      - your print(...) statements
      - real warnings/errors
    Call as the FIRST thing in your app, before importing big libs.
    """
    # --- Environment flags to quiet libraries ---
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("ABSL_LOGGING_MIN_SEVERITY", "3")  # absl
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")       # TF/XLA
    os.environ.setdefault("TQDM_DISABLE", "1")               # tqdm progress bars
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")       # OpenTelemetry
    os.environ.setdefault("OTEL_LOG_LEVEL", "error")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")   # HF Hub
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.pop("GRPC_TRACE", None)                       # ensure off
    os.environ.setdefault("OPENAI_LOG", "error")             # if openai sdk present

    # --- Ensure stdout uses UTF-8 on Windows (prevents charmap noise) ---
    if sys.platform.startswith("win"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # --- Force global logging config ---
    # Keep root at ERROR by default (tunable via CE_LOG_LEVEL)
    lvl_name = os.getenv("CE_LOG_LEVEL", default_level).upper()
    lvl = getattr(logging, lvl_name, logging.ERROR)
    logging.basicConfig(
        level=lvl,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,  # override prior handlers from libs
    )

    # --- Silence noisy third-party loggers hard ---
    noisy = [
        # networking / http
        "urllib3", "urllib3.connectionpool", "httpx", "requests",
        # AI/ML frameworks
        "transformers", "accelerate", "torch", "tensorflow", "jax", "jaxlib", "absl",
        # tracing/telemetry
        "opentelemetry", "opentelemetry.sdk", "opentelemetry.exporter",
        # LLM frameworks
        "langchain", "langchain_core", "langsmith",
        # PDF stack
        "pdfminer", "pdfminer.six",
        # web servers (if you run FastAPI later)
        "uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn",
    ]
    for name in noisy:
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False

    # urllib3 TLS warnings, etc.
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass

    # Convert Python warnings -> logging, then silence by default
    logging.captureWarnings(True)
    warnings.simplefilter("ignore")

    # OPTIONAL: keep YOUR app logger chatty if you prefer (only your messages)
    # (Use logger = logging.getLogger("contractextract") in your code)
    app_logger = logging.getLogger("contractextract")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
    if not app_logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter("%(message)s"))
        app_logger.addHandler(h)
