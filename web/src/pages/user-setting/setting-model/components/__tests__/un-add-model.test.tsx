import React from 'react';
import { render, screen } from '@testing-library/react';
import { AvailableModels } from '../un-add-model';

describe('AvailableModels', () => {
  it('does not render the available models panel', () => {
    render(<AvailableModels handleAddModel={jest.fn()} />);

    expect(screen.queryByTestId('available-models-section')).toBeNull();
  });
});
