import pytest
from conftest import chat_request

from bladesight.meta import (
    MetaAuthError,
    MetaClient,
    MetaInvalidResponseError,
    MetaRateLimitError,
    MetaServerError,
    MetaTimeoutError,
    RetryPolicy,
    SpendCapExceededError,
    SpendTracker,
    StubProvider,
)
from bladesight.meta.spend import estimate_chat_usd


def make_client(
    stub: StubProvider, sleeps: list[float], policy: RetryPolicy | None = None
) -> MetaClient:
    return MetaClient(
        stub,
        spend=SpendTracker.unlimited(),
        retry=policy,
        sleep=sleeps.append,
        rng=lambda: 1.0,
    )


def test_succeeds_after_transient_failures() -> None:
    sleeps: list[float] = []
    stub = StubProvider(failures=[MetaServerError("boom", status_code=503)] * 2)
    client = make_client(stub, sleeps)

    result = client.chat(chat_request())

    assert result.text == "stub response"
    assert stub.call_count == 3
    record = client.records[0]
    assert record.attempts == 3
    assert record.retried_codes == ["503", "503"]
    assert sleeps == [0.5, 1.0]  # exponential, jitter pinned at the maximum


def test_gives_up_after_max_attempts_with_last_error() -> None:
    sleeps: list[float] = []
    stub = StubProvider(failures=[MetaServerError("boom", status_code=502)] * 10)
    client = make_client(stub, sleeps, RetryPolicy(max_attempts=3))

    with pytest.raises(MetaServerError) as info:
        client.chat(chat_request())

    assert info.value.attempts == 3
    assert stub.call_count == 3
    assert len(sleeps) == 2
    assert client.records == []  # a failed call is not a record and costs nothing
    assert client.spend.spent_usd == 0  # the reservation was released


def test_auth_error_is_not_retried() -> None:
    sleeps: list[float] = []
    stub = StubProvider(failures=[MetaAuthError("no", status_code=401)])
    client = make_client(stub, sleeps)

    with pytest.raises(MetaAuthError):
        client.chat(chat_request())

    assert stub.call_count == 1
    assert sleeps == []


def test_timeout_is_retried() -> None:
    stub = StubProvider(failures=[MetaTimeoutError("slow")])
    client = make_client(stub, [])
    client.chat(chat_request())
    assert client.records[0].retried_codes == ["timeout"]


def test_backoff_is_capped_and_jittered() -> None:
    policy = RetryPolicy(base_delay=1.0, max_delay=4.0)
    error = MetaServerError("x")
    assert [policy.delay(a, error, lambda: 1.0) for a in (1, 2, 3, 4, 5)] == [1, 2, 4, 4, 4]
    assert policy.delay(3, error, lambda: 0.25) == 1.0
    assert policy.delay(3, error, lambda: 0.0) == 0.0


def test_retry_after_is_a_floor_never_shortened() -> None:
    policy = RetryPolicy(base_delay=0.5)
    assert policy.delay(1, MetaRateLimitError("x", retry_after=3.0), lambda: 0.0) == 3.0
    assert policy.delay(1, MetaRateLimitError("x", retry_after=90.0), lambda: 0.0) == 90.0
    assert policy.delay(5, MetaRateLimitError("x", retry_after=0.1), lambda: 1.0) == 8.0


def test_absurd_retry_after_is_not_waited_for() -> None:
    sleeps: list[float] = []
    stub = StubProvider(
        failures=[MetaRateLimitError("slow down", status_code=429, retry_after=9999)]
    )
    client = make_client(stub, sleeps, RetryPolicy(max_retry_after=120.0))

    with pytest.raises(MetaRateLimitError):
        client.chat(chat_request())

    assert sleeps == []
    assert stub.call_count == 1


# --- #23: a 2xx whose body cannot be parsed -------------------------------------------------


def garbled() -> MetaInvalidResponseError:
    return MetaInvalidResponseError("non-JSON body", status_code=200, request_id="r-bad")


def test_unparsable_2xx_is_retried_once_then_succeeds() -> None:
    sleeps: list[float] = []
    stub = StubProvider(failures=[garbled()])
    client = make_client(stub, sleeps)

    result = client.chat(chat_request())

    assert result.text == "stub response"
    assert stub.call_count == 2
    assert client.records[0].attempts == 2
    assert client.records[0].retried_codes == ["200"]
    assert sleeps == [0.5]
    # The stub bills nothing real; the garbled attempt is still counted (simulated) at its
    # estimate on top of the good reply.
    estimate = estimate_chat_usd(chat_request())
    good = client.records[0].simulated_cost_usd
    assert client.spend.spent_usd == pytest.approx(estimate + good)
    assert client.records[0].cost_usd == 0


def test_two_unparsable_2xx_raise_the_typed_error_and_stay_counted() -> None:
    sleeps: list[float] = []
    stub = StubProvider(failures=[garbled(), garbled(), garbled()])
    client = make_client(stub, sleeps)

    with pytest.raises(MetaInvalidResponseError) as info:
        client.chat(chat_request())

    assert stub.call_count == 2  # one retry only, not max_attempts
    assert info.value.attempts == 2
    assert client.records == []
    assert client.spend.spent_usd == pytest.approx(2 * estimate_chat_usd(chat_request()))


def test_the_retry_of_an_unparsable_2xx_rechecks_the_spend_cap() -> None:
    estimate = estimate_chat_usd(chat_request())
    stub = StubProvider(failures=[garbled()])
    client = MetaClient(
        stub, spend=SpendTracker(estimate * 1.5, provider="stub"), sleep=lambda _: None
    )

    with pytest.raises(SpendCapExceededError):
        client.chat(chat_request())

    assert stub.call_count == 1  # the second call was refused before it was made
    assert client.spend.spent_usd == pytest.approx(estimate)


def test_server_errors_before_an_unparsable_2xx_still_count_as_attempts() -> None:
    stub = StubProvider(failures=[MetaServerError("boom", status_code=503), garbled()])
    client = make_client(stub, [])

    client.chat(chat_request())

    assert stub.call_count == 3
    assert client.records[0].attempts == 3
