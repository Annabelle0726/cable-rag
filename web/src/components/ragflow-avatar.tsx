/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import { cn } from '@/lib/utils';
import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { LucideUser } from 'lucide-react';
import { forwardRef, memo, useMemo } from 'react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';

const PREDEFINED_COLORS = [
  { from: '#4F6DEE', to: '#67BDF9' },
  { from: '#38A04D', to: '#93DCA2' },
  { from: '#C35F2B', to: '#EDB395' },
  { from: '#633897', to: '#CBA1FF' },
];

const getStringHash = (str: string): number => {
  if (typeof str !== 'string') return 0;

  const normalized = str.trim().toLowerCase();
  let hash = 104729;
  const seed = 0x9747b28c;

  for (let i = 0; i < normalized.length; i++) {
    hash ^= seed ^ normalized.charCodeAt(i);
    hash = (hash << 13) | (hash >>> 19);
    hash = (hash * 5 + 0x52dce72d) | 0;
  }

  return Math.abs(hash);
};

const getInitials = (name?: string) => {
  if (typeof name !== 'string' || !name) return '';
  const parts = name?.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0][0].toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};

/**
 * The single character a person's avatar falls back to.
 *
 * Candidates are tried in the order the caller passes them — nickname, then
 * name, then email — and the first one holding text wins. `Array.from` keeps a
 * surrogate pair (an emoji, or most CJK extensions) in one piece.
 */
export const getAvatarInitial = (...candidates: Array<string | undefined>) => {
  for (const candidate of candidates) {
    const value = candidate?.trim();
    if (value) {
      return Array.from(value)[0].toUpperCase();
    }
  }

  return '';
};

const getColorForName = (name: string): { from: string; to: string } => {
  const hash = getStringHash(name);
  const index = hash % PREDEFINED_COLORS.length;
  return PREDEFINED_COLORS[index];
};

export const RAGFlowAvatar = memo(
  forwardRef<
    React.ElementRef<typeof AvatarPrimitive.Root>,
    React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root> & {
      name?: string;
      /** Second source for a person's initial, used when the name is empty. */
      email?: string;
      avatar?: string;
      isPerson?: boolean;
    }
  >(({ name, email, avatar, isPerson = false, className, ...props }, ref) => {
    // Generate initial letter logic
    const { initials, from, to } = useMemo(
      () => ({
        // A person falls back to one character of their name or email; other
        // avatars (datasets, agents) keep the two-letter form of their name.
        initials: isPerson ? getAvatarInitial(name, email) : getInitials(name),
        from: 'hsl(0, 0%, 30%)',
        to: 'hsl(0, 0%, 80%)',
        ...(name ? getColorForName(name) : {}),
      }),
      [email, isPerson, name],
    );

    return (
      <Avatar
        ref={ref}
        {...props}
        className={cn(className, { 'rounded-md': !isPerson })}
      >
        <AvatarImage src={avatar} />
        <AvatarFallback
          className={cn(
            'flex items-center justify-center',
            isPerson
              ? 'bg-cable-avatar text-cable-avatar-foreground'
              : 'bg-gradient-to-b text-white',
          )}
          style={
            isPerson
              ? undefined
              : { backgroundImage: `linear-gradient(to bottom, ${from}, ${to})` }
          }
          role="presentation"
          aria-hidden="true"
          data-testid="avatar-fallback"
        >
          {initials ? (
            <svg
              className="size-full block text-current select-none"
              viewBox={`${-(50 + 22.5 * (initials.length - 1))} -50 ${100 + 45 * (initials.length - 1)} 100`}
              preserveAspectRatio="xMinYMid meet"
            >
              <text
                fontSize={55}
                fill="currentColor"
                textAnchor="middle"
                dominantBaseline="central"
              >
                {initials}
              </text>
            </svg>
          ) : (
            // Nothing to initialise from: a neutral person glyph beats an
            // empty coloured disc.
            <LucideUser className="h-1/2 w-1/2" />
          )}
        </AvatarFallback>
      </Avatar>
    );
  }),
);

RAGFlowAvatar.displayName = 'RAGFlowAvatar';
