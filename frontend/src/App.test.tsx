import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';

function mockResponse(status: number, payload: unknown): Response {
  return {
    status,
    ok: status >= 200 && status < 300,
    statusText: '',
    text: async () => JSON.stringify(payload),
  } as Response;
}

beforeEach(() => {
  jest.restoreAllMocks();
});

test('shows username and password sign in without a client-selected role', async () => {
  jest.spyOn(global, 'fetch').mockResolvedValue(mockResponse(401, { detail: 'Authentication required.' }));

  render(<App />);
  expect(await screen.findByRole('heading', { name: /welcome back/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
  expect(screen.getByLabelText('Password', { exact: true })).toBeInTheDocument();
  expect(screen.queryByRole('group', { name: /your role/i })).not.toBeInTheDocument();
});

test('uses the authenticated account role to show its workspace', async () => {
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/auth/me/')) {
      return mockResponse(401, {});
    }
    if (url.endsWith('/auth/csrf/')) {
      return mockResponse(200, { csrfToken: 'test-token' });
    }
    if (url.endsWith('/auth/login/')) {
      const payload = JSON.parse(String(init?.body));
      expect(payload).toEqual({ username: 'teacher1', password: 'secretpass' });
      return mockResponse(200, { user: { id: 1, username: 'teacher1', name: 'Jane Teacher', role: 'TEACHER' } });
    }
    if (url.endsWith('/dashboard/')) {
      return mockResponse(200, {
          stats: { students: 0, teachers: 1, classes: 0, subjects: 0, approved_results: 0, pending_results: 0 },
          result_status: {},
          recent_results: [],
          top_students: [],
        });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<App />);
  fireEvent.change(await screen.findByLabelText(/username/i), { target: { value: 'teacher1' } });
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), { target: { value: 'secretpass' } });
  fireEvent.click(screen.getByRole('button', { name: /sign in securely/i }));

  expect(await screen.findByText('TEACHER WORKSPACE')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Enter Results' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Users' })).not.toBeInTheDocument();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
    expect.stringMatching(/\/auth\/login\/$/),
    expect.objectContaining({ credentials: 'include', method: 'POST' })
  ));
});

test('Super Admin can create an account from the user management workspace', async () => {
  const createdUser = {
    id: 4,
    username: 'new-teacher',
    first_name: 'New',
    last_name: 'Teacher',
    email: 'teacher@school.local',
    role: 'TEACHER',
    phone_number: '',
    is_active: true,
  };
  const fetchMock = jest.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/auth/me/')) {
      return mockResponse(200, { user: { id: 1, username: 'root', name: 'Root Admin', role: 'SUPER_ADMIN' } });
    }
    if (url.endsWith('/dashboard/')) {
      return mockResponse(200, {
          stats: {},
          result_status: {},
          recent_results: [],
          top_students: [],
        });
    }
    if (url.endsWith('/users/') && init?.method === 'POST') {
      expect(JSON.parse(String(init.body))).toEqual({
        username: 'new-teacher',
        first_name: 'New',
        last_name: 'Teacher',
        email: 'teacher@school.local',
        role: 'TEACHER',
        phone_number: '',
        password: 'a-safe-password',
      });
      return mockResponse(201, createdUser);
    }
    if (url.endsWith('/users/')) {
      return mockResponse(200, [createdUser]);
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<App />);
  expect(await screen.findByText('Data Management')).toBeInTheDocument();
  expect(screen.getByText('Academic Settings')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Users & Access' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add user' }));
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'new-teacher' } });
  fireEvent.change(screen.getByLabelText('First name'), { target: { value: 'New' } });
  fireEvent.change(screen.getByLabelText('Last name'), { target: { value: 'Teacher' } });
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'teacher@school.local' } });
  fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'TEACHER' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-safe-password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

  expect(await screen.findByRole('status')).toHaveTextContent('User account created.');
  expect(await screen.findByText('new-teacher')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringMatching(/\/users\/$/),
    expect.objectContaining({ method: 'POST', credentials: 'include' })
  );
});
