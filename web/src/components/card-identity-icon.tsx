/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
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
import { Brain, Compass, MessageSquareCode, type LucideIcon } from 'lucide-react';
import { useState } from 'react';

/** The card families that carry a vector identity mark. */
export type CardIdentityKind = 'chat' | 'search' | 'memory';

const CARD_IDENTITY_ICONS: Record<CardIdentityKind, LucideIcon> = {
  chat: MessageSquareCode,
  search: Compass,
  memory: Brain,
};

/**
 * The 32px box the card avatar occupied, kept exactly so swapping the fallback
 * for a vector mark does not move the card's outer box or its text column.
 */
const HALO_CLASS =
  'flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-cable-hairline';

type CardIdentityIconProps = {
  kind: CardIdentityKind;
  /** Owner-supplied image. When present it replaces the vector mark. */
  avatar?: string;
  className?: string;
};

/**
 * The mark that opens a card row on the chat, search and memory pages.
 *
 * These cards used to fall back to `RAGFlowAvatar`, which paints the first one or
 * two letters of the name onto one of four hardcoded saturated gradients. That
 * block repeats a character the title already shows and reads as a broken image,
 * so the fallback is a vector mark for the card's own kind instead — the same
 * halo the knowledge-base cards give their class icon. An uploaded image still
 * wins, in a frame cut to the same geometry, and a broken URL degrades back to
 * the vector mark rather than to the browser's broken-image glyph.
 */
export function CardIdentityIcon({
  kind,
  avatar,
  className,
}: CardIdentityIconProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const Icon = CARD_IDENTITY_ICONS[kind];

  if (avatar && !imageFailed) {
    return (
      <span className={cn(HALO_CLASS, className)}>
        <img
          src={avatar}
          alt=""
          className="size-full object-cover"
          onError={() => setImageFailed(true)}
        />
      </span>
    );
  }

  return (
    <span className={cn(HALO_CLASS, 'bg-cable-icon', className)}>
      <Icon className="size-4 text-cable-icon-foreground" aria-hidden />
    </span>
  );
}
