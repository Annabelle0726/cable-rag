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

import { RAGFlowAvatar } from '@/components/ragflow-avatar';
import { TruncatedText } from '@/components/truncated-text';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { formatDate } from '@/utils/date';
import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

interface IProps {
  data: {
    name: string;
    description?: string;
    avatar?: string;
    update_time?: string | number;
    release_time?: number;
  };
  onClick?: () => void;
  moreDropdown: React.ReactNode;
  sharedBadge?: ReactNode;
  icon?: React.ReactNode;
  /**
   * Replaces the avatar block on the left of the card. Knowledge-base cards put
   * their class icon here instead of the first letter of the name.
   */
  leading?: ReactNode;
  /** Classification chip, rendered in the title row next to the actions. */
  badge?: ReactNode;
  testId?: string;
  showReleaseTime?: boolean;
  extra?: ReactNode;
}

function Time({ time }: { time: string | number | undefined }) {
  return <p className="truncate text-sm text-cable-muted">{formatDate(time)}</p>;
}

export function HomeCard({
  data,
  onClick,
  moreDropdown,
  sharedBadge,
  icon,
  leading,
  badge,
  testId,
  showReleaseTime = false,
  extra,
}: IProps) {
  const { t } = useTranslation();

  return (
    <Card
      as="article"
      data-testid={testId}
      data-agent-name={data.name}
      onClick={() => {
        // navigateToSearch(data?.id);
        onClick?.();
      }}
      tabIndex={0}
      className={cn(
        // `card-interactive` supplies the pointer cursor and the colour-only
        // hover tint. No transform or scale: these cards render inside
        // `overflow-hidden` grids, which clip a lifted card, so the lift comes
        // from the ceramic shadow rather than from a translate.
        'card-interactive group flex h-full w-full items-start gap-3 rounded-xl px-4 py-4',
        // Translucent glass tint, so the page's own glow reads through the card
        // instead of stopping dead at an opaque surface. The ceramic shell adds
        // the inner rim light and the drop shadow, in whichever theme is active.
        'border border-ceramic-border bg-glass shadow-ceramic',
        'hover:border-ceramic-border-hover hover:shadow-ceramic-hover',
        // Needed because `Card` ships `transition-shadow`, which would otherwise
        // pin transition-property to box-shadow and drop the colour transition.
        // The ceramic hover moves the shadow too, so both are named here.
        'transition-[background-color,border-color,box-shadow,opacity] duration-200 ease-in-out',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cable-accent',
      )}
    >
      <div>
        {leading ?? (
          <RAGFlowAvatar
            className="w-[32px] h-[32px]"
            avatar={data.avatar}
            name={data.name}
          />
        )}
      </div>

      <div className="flex-1 w-0">
        <CardHeader
          as="header"
          className="p-0 flex-1 flex flex-row items-center gap-2 space-y-0"
        >
          <CardTitle className="flex-1 inline-flex w-0 me-auto">
            <TruncatedText
              as="h3"
              className="flex-1 truncate text-base font-bold leading-snug"
              testId="agent-name"
              tooltip={data.name}
            >
              {data.name}
            </TruncatedText>

            {icon}
          </CardTitle>

          <div className="flex shrink-0 items-center gap-1">
            {badge}
            {moreDropdown}
          </div>
        </CardHeader>

        <CardContent className="p-0">
          <div className="flex flex-col justify-between gap-1 flex-1 h-full w-[calc(100%-50px)]">
            <section className="flex justify-between"></section>

            <section className="flex flex-col gap-1 mt-1">
              <TruncatedText
                className="whitespace-nowrap overflow-hidden text-ellipsis"
                tooltip={data.description}
              >
                {data.description}
              </TruncatedText>
              {extra}
              <div className="flex justify-between items-center min-w-0">
                {showReleaseTime ? (
                  <section className="text-sm text-text-secondary space-y-1 min-w-0">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="whitespace-nowrap">
                        {t('flow.lastSavedAt')}:
                      </span>
                      <Time time={data.update_time}></Time>
                    </div>
                    {data.release_time && (
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="whitespace-nowrap">
                          {t('flow.publishedAt')}:
                        </span>
                        <Time time={data.release_time}></Time>
                      </div>
                    )}
                  </section>
                ) : (
                  <Time time={data.update_time}></Time>
                )}
                {sharedBadge}
              </div>
            </section>
          </div>
        </CardContent>
      </div>
    </Card>
  );
}
