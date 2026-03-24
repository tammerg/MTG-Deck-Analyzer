import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDropdown } from '../useDropdown';

describe('useDropdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initialises with open=false', () => {
    const { result } = renderHook(() => useDropdown());
    expect(result.current.open).toBe(false);
  });

  it('toggle opens the dropdown', () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.toggle());
    expect(result.current.open).toBe(true);
  });

  it('toggle closes an open dropdown', () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(result.current.open).toBe(false);
  });

  it('setOpen can set state directly', () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.setOpen(true));
    expect(result.current.open).toBe(true);
    act(() => result.current.setOpen(false));
    expect(result.current.open).toBe(false);
  });

  it('closes on Escape key when open', () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.toggle());
    expect(result.current.open).toBe(true);

    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });

    expect(result.current.open).toBe(false);
  });

  it('does not close on non-Escape key when open', () => {
    const { result } = renderHook(() => useDropdown());
    act(() => result.current.toggle());

    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });

    expect(result.current.open).toBe(true);
  });

  it('does not attach keydown listener when closed', () => {
    const addSpy = vi.spyOn(document, 'addEventListener');
    const { result } = renderHook(() => useDropdown());
    // dropdown starts closed — no listeners should be attached
    expect(result.current.open).toBe(false);
    const keydownCalls = addSpy.mock.calls.filter(([ev]) => ev === 'keydown');
    expect(keydownCalls).toHaveLength(0);
    addSpy.mockRestore();
  });

  it('exposes a containerRef', () => {
    const { result } = renderHook(() => useDropdown());
    expect(result.current.containerRef).toBeDefined();
    expect(result.current.containerRef).toHaveProperty('current');
  });
});
