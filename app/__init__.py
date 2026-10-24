"""Simple enterprise knowledge assistant (RAG + a small agent)."""

# Use the Windows/macOS certificate store for HTTPS. Without this, antivirus or a company
# proxy that inspects HTTPS makes model downloads and Claude calls fail with
# CERTIFICATE_VERIFY_FAILED.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass
