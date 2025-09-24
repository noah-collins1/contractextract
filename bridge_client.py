"""
Bridge client to call v1 LangExtract service from v2 environment.
Enables calling legacy Pydantic v1 extraction service over HTTP.
"""
import requests
import logging
from typing import Dict, Any, List, Optional

log = logging.getLogger("contractextract.bridge")


def remote_extract(
    text: str,
    prompt: str = "",
    examples: Optional[List] = None,
    url: str = "http://127.0.0.1:8091/extract",
    timeout: float = 120.0
) -> Dict[str, Any]:
    """
    POST JSON to the v1 service and return parsed JSON (raise with clear error on non-200).

    Args:
        text: Document text to extract from
        prompt: Extraction prompt/instructions
        examples: List of example extractions
        url: URL of the v1 LangExtract service
        timeout: Request timeout in seconds

    Returns:
        Dict containing extraction results from v1 service

    Raises:
        requests.ConnectionError: If service is unreachable
        requests.HTTPError: If service returns non-200 status
        ValueError: If response cannot be parsed as JSON
    """
    payload = {
        "text": text,
        "prompt": prompt,
        "examples": examples or []
    }

    try:
        log.info(f"Calling v1 LangExtract service at {url}")
        response = requests.post(
            url,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"}
        )

        # Check for HTTP errors
        if response.status_code != 200:
            error_detail = "Unknown error"
            try:
                error_json = response.json()
                error_detail = error_json.get("error", error_json.get("detail", str(error_json)))
            except:
                error_detail = response.text or f"HTTP {response.status_code}"

            raise requests.HTTPError(
                f"V1 service returned {response.status_code}: {error_detail}"
            )

        # Parse JSON response
        try:
            result = response.json()
            log.info(f"V1 service returned successful response")
            return result

        except ValueError as e:
            raise ValueError(f"V1 service returned invalid JSON: {str(e)}")

    except requests.ConnectionError as e:
        raise requests.ConnectionError(
            f"Cannot connect to v1 LangExtract service at {url}. "
            f"Make sure the service is running. Original error: {str(e)}"
        )
    except requests.Timeout as e:
        raise requests.Timeout(
            f"V1 LangExtract service timed out after {timeout}s. "
            f"Consider increasing timeout or check service performance. Original error: {str(e)}"
        )
    except requests.RequestException as e:
        raise requests.RequestException(
            f"Request to v1 LangExtract service failed: {str(e)}"
        )