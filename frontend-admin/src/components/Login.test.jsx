import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import Login from './Login';

describe('Login Component', () => {
  it('renders login form correctly', () => {
    const setToken = vi.fn();
    const setUser = vi.fn();
    
    render(<Login setToken={setToken} setUser={setUser} />);
    
    expect(screen.getByText('Welcome back')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('admin or email@example.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
  });

  it('switches to register form when clicking create account', async () => {
    const setToken = vi.fn();
    const setUser = vi.fn();
    
    render(<Login setToken={setToken} setUser={setUser} />);
    
    const registerBtn = screen.getByText('New customer? Create account');
    await userEvent.click(registerBtn);
    
    expect(screen.getByText('Register as a customer to start ordering')).toBeInTheDocument();
  });
});
