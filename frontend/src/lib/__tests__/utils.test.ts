import { describe, expect, it } from 'vitest';
import { cn } from '@/lib/utils';

describe('utils.ts — cn', () => {
  it('joins plain class strings', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('ignores falsy values (false, undefined, null, empty string, numbers)', () => {
    expect(cn('a', false && 'b', undefined, null, '', 0, 'c')).toBe('a c');
  });

  it('supports conditional class objects and arrays', () => {
    expect(cn({ foo: true, bar: false })).toBe('foo');
    expect(cn(['a', ['b', 'c']])).toBe('a b c');
  });

  it('resolves tailwind-merge conflicts, keeping the LAST class', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
    expect(cn('flex', 'flex-col')).toBe('flex flex-col');
    // Order of surviving classes is an implementation detail of twMerge;
    // assert on SET membership, not order.
    expect(cn('px-2 py-1', 'px-4').split(/\s+/).sort()).toEqual(['py-1', 'px-4'].sort());
  });
});
