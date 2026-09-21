import { fireEvent, render, screen } from '@testing-library/react';
import ModelServiceUnavailable from '..';
import { ModelServiceErrorType } from '@/utils/model-service-error';

jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      key === 'common.retry'
        ? 'Retry'
        : key === 'message.embeddingQuotaExhausted'
          ? 'The vector service is out of quota.'
          : key,
  }),
}));

describe('the stand-in for a refused request', () => {
  it('says which capability is down and what to do about it', () => {
    render(
      <ModelServiceUnavailable
        errorType={ModelServiceErrorType.EmbeddingQuotaExhausted}
        title="Search is unavailable"
      />,
    );

    expect(screen.getByTestId('model-service-unavailable')).toBeInTheDocument();
    expect(screen.getByText('Search is unavailable')).toBeInTheDocument();
    expect(
      screen.getByText('The vector service is out of quota.'),
    ).toBeInTheDocument();
  });

  it('offers a retry only when the caller can retry', () => {
    const { rerender } = render(
      <ModelServiceUnavailable
        errorType={ModelServiceErrorType.EmbeddingRateLimited}
        title="Search is unavailable"
      />,
    );

    expect(screen.queryByTestId('model-service-retry')).toBeNull();

    const onRetry = jest.fn();
    rerender(
      <ModelServiceUnavailable
        errorType={ModelServiceErrorType.EmbeddingRateLimited}
        title="Search is unavailable"
        onRetry={onRetry}
      />,
    );

    fireEvent.click(screen.getByTestId('model-service-retry'));
    expect(onRetry).toHaveBeenCalled();
  });
});
