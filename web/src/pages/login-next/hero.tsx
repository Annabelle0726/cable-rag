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

import { BrandLogo } from '@/components/brand-logo';
import { LucideBrain, LucideFileText, LucideZap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * Feature list of the brand column. The icon carries the brand green, the row
 * holds the copy, and both come from tokens so the two themes stay a token swap
 * rather than a stack of `dark:` variants.
 */
const Features = [
  {
    icon: LucideZap,
    title: 'hero.featureHybridSearch',
    description: 'hero.featureHybridSearchDesc',
  },
  {
    icon: LucideFileText,
    title: 'hero.featureDocumentParsing',
    description: 'hero.featureDocumentParsingDesc',
  },
  {
    icon: LucideBrain,
    title: 'hero.featureAgentMemory',
    description: 'hero.featureAgentMemoryDesc',
  },
];

/**
 * Brand column shown beside the sign-in form from `lg` up.
 *
 * The identity block reads top to bottom — square logo, product wordmark, the
 * system's full name, then the one-line pitch — and the feature list is a single
 * 1px-ruled panel rather than a stack of floating cards. Everything is solid:
 * no gradient title, no bloom behind the text, no backdrop blur.
 */
export function LoginHero() {
  const { t } = useTranslation('translation', { keyPrefix: 'login' });
  const { t: tHeader } = useTranslation('translation', { keyPrefix: 'header' });

  return (
    <section className="relative hidden min-w-0 flex-col gap-6 lg:col-span-5 lg:flex">
      <div className="flex flex-col gap-3">
        {/* The poster is the company artwork, so the product wordmark stays real
            text beside it — the same company-and-product pair the app bar shows.
            The artwork is drawn on white, hence the plinth. */}
        <span className="flex h-12 w-fit items-center justify-center gap-3 bg-white px-3">
          <BrandLogo variant="poster" className="h-9 w-auto" />
          <span className="text-lg font-semibold tracking-tight text-text-primary">
            {tHeader('brandShort')}
          </span>
        </span>

        {/* 系统全称：国网绿指示条 + 实色标题 */}
        <h1 className="mt-1 flex items-start gap-2 text-2xl leading-snug font-bold text-text-primary">
          <span
            aria-hidden
            className="mt-1.5 h-5 w-1 shrink-0 bg-cable-brand"
          />
          {tHeader('heroTitle')}
        </h1>

        <p className="text-sm text-content-secondary">
          {tHeader('heroSubtitle')}
        </p>
      </div>

      <ul className="flex flex-col border border-panel-border bg-bg-component">
        {Features.map(({ icon: Icon, title, description }) => (
          <li
            key={title}
            className="flex items-start gap-3 border-b border-table-border p-3 last:border-b-0"
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-cable-brand" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text-primary">
                {t(title)}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-content-secondary">
                {t(description)}
              </p>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-2">
        {[t('hero.badgeLatency'), t('hero.badgeIsolation')].map((badge) => (
          <span
            key={badge}
            className="inline-flex items-center border border-status-available-border bg-status-available px-2 py-1 text-xs leading-none text-status-available-ink"
          >
            {badge}
          </span>
        ))}
      </div>
    </section>
  );
}