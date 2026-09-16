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
import { t } from 'i18next';
import { useIsDarkTheme } from '../theme-provider';

import { Plus } from 'lucide-react';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import SvgIcon from '../svg-icon';
import { EmptyCardData, EmptyCardType, EmptyType } from './constant';
import { EmptyCardProps, EmptyProps } from './interface';

const EmptyIcon = ({ name, width }: { name: string; width?: number }) => {
  return <SvgIcon name={name || 'empty/no-data-dark'} width={width || 42} />;
};

const Empty = (props: EmptyProps) => {
  const { className, children, type, text, iconWidth } = props;
  const isDarkTheme = useIsDarkTheme();

  const name = useMemo(() => {
    return isDarkTheme
      ? `empty/no-${type || EmptyType.Data}-dark`
      : `empty/no-${type || EmptyType.Data}-bri`;
  }, [isDarkTheme, type]);

  return (
    <div
      className={cn(
        'flex flex-col justify-center items-center text-center gap-2',
        className,
      )}
    >
      <EmptyIcon name={name} width={iconWidth} />

      {!children && (
        <div className="empty-text text-text-secondary text-sm">
          {text ||
            (type === 'data' ? t('common.noData') : t('common.noResults'))}
        </div>
      )}
      {children}
    </div>
  );
};

export default Empty;

export const EmptyCard = (props: EmptyCardProps) => {
  const { icon, className, children, title, description, style, ...restProps } =
    props;
  return (
    <article
      className={cn(
        // One centred column at every breakpoint, with a floor for its height:
        // the tile holds an icon, a plus and sometimes a message, and the whole
        // group has to sit in the middle of the card. It used to switch to a
        // left-aligned, width-to-fit layout from md up, which collapsed the card
        // to the width of its icon once the placeholder text was removed.
        'flex min-h-[160px] w-full flex-col items-center justify-center gap-3 p-5 text-center',
        'rounded-md border border-dashed border-border-button',
        className,
      )}
      style={style}
      {...restProps}
    >
      {icon}
      {title && <div className="text-sm text-text-primary">{title}</div>}
      {description && (
        <p className="text-sm text-text-secondary">{description}</p>
      )}
      {children}
    </article>
  );
};

export const EmptyAppCard = (props: {
  type: EmptyCardType;
  onClick?: () => void;
  showIcon?: boolean;
  className?: string;
  isSearch?: boolean;
  size?: 'small' | 'large';
  children?: React.ReactNode;
  testId?: string;
  tabIndex?: number;
}) => {
  const { type, showIcon, className, isSearch, children, testId, tabIndex } =
    props;
  const { t } = useTranslation();
  let style: React.CSSProperties | undefined;
  const cardData = EmptyCardData[type];
  // The create tile states what the click does, and the "nothing matched" state
  // says what came back empty — one line either way, under the icons.
  const title = t(cardData.titleKey);
  const notFound = t(cardData.notFoundKey);

  if (props.size === 'small') {
    style = { width: '256px' };
  }

  return (
    <div className="flex w-full justify-center px-5 md:px-0">
      <EmptyCard
        onClick={isSearch ? undefined : props.onClick}
        data-testid={testId}
        tabIndex={tabIndex ?? (isSearch ? undefined : 0)}
        icon={isSearch && showIcon ? cardData.icon : undefined}
        title={isSearch ? notFound : undefined}
        className={cn(
          // The tile is a button: the pointer cursor, a theme-blue hairline and
          // one soft accent glow on hover. No lift and no scale, so the
          // surrounding grid never clips it.
          !isSearch &&
            'card-interactive transition-[background-color,border-color,box-shadow] duration-200 ease-in-out hover:border-accent-color hover:shadow-accent-glow',
          props.size === 'large' && 'p-14',
          className,
          'w-full max-w-[480px] md:max-w-none',
          props.size === 'large' && 'md:w-[480px]',
          props.size === 'small' && 'max-w-64',
        )}
        style={style}
      >
        {!isSearch && !children && (
          // Icon, plus and prompt read as one group in the middle of the tile.
          <div className="flex flex-col items-center justify-center gap-3">
            <span className="flex flex-col items-center justify-center gap-2">
              {showIcon && cardData.icon}
              <Plus size={24} />
            </span>

            <span className="text-sm text-text-secondary">{title}</span>
          </div>
        )}
        {children}
      </EmptyCard>
    </div>
  );
};
