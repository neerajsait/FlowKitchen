import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Login from './Login';

describe('Customer Login Component', () => {
  it('renders login form correctly', () => {
    const setToken = vi.fn();
    const setUser = vi.fn();
    
    render(<Login setToken={setToken} setUser={setUser} />);
    
    expect(screen.getByText('Welcome back')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('admin or email@example.com')).toBeInTheDocument();
  });
});
