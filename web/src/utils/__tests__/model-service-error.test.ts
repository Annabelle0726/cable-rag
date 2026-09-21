import {
  ModelServiceErrorType,
  modelServiceErrorMessageKey,
  modelServiceErrorOf,
} from '../model-service-error';

describe('recognised model service failures', () => {
  it('maps the types the backend sends', () => {
    expect(
      modelServiceErrorOf({ error_type: 'EMBEDDING_QUOTA_EXHAUSTED' }),
    ).toBe(ModelServiceErrorType.EmbeddingQuotaExhausted);
    expect(
      modelServiceErrorOf({ error_type: 'EMBEDDING_RATE_LIMITED' }),
    ).toBe(ModelServiceErrorType.EmbeddingRateLimited);
  });

  it('leaves anything else to the handling it already had', () => {
    // An unknown type must not be swallowed as if it were understood.
    expect(modelServiceErrorOf({ error_type: 'SOMETHING_NEW' })).toBeNull();
    expect(modelServiceErrorOf({ code: 102, message: 'boom' })).toBeNull();
    expect(modelServiceErrorOf({ error_type: 429 })).toBeNull();
    expect(modelServiceErrorOf(null)).toBeNull();
    expect(modelServiceErrorOf(undefined)).toBeNull();
  });

  it('has a message key for every type, including the retryable one', () => {
    // "Wait a minute" and "this account is out of quota" need different wording:
    // one asks for patience, the other for a new key.
    const keys = Object.values(ModelServiceErrorType).map(
      modelServiceErrorMessageKey,
    );

    expect(new Set(keys).size).toBe(keys.length);
    keys.forEach((key) => expect(key).toMatch(/^message\./));
  });
});
