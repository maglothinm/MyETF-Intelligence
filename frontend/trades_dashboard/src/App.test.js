import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import axios from 'axios';
import App from './App';

jest.mock('axios', () => ({
  get: jest.fn(),
}));
jest.mock('./components/StockInfo', () => () => null);
jest.mock('./components/Politician', () => () => null);

test('renders the trades dashboard after loading data', async () => {
  axios.get.mockResolvedValue({ data: [] });

  render(<App />);

  expect(
    await screen.findByRole('heading', { name: /polititrack/i })
  ).toBeInTheDocument();
  expect(axios.get).toHaveBeenCalledWith('http://127.0.0.1:5000/trades');
});
