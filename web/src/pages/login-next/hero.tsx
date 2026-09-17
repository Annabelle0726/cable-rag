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

import { LucideBrain, LucideFileText, LucideZap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/**
 * Feature list of the brand column. The icon carries the accent, the card holds
 * the copy, and both come from the hero tokens so the two themes stay a token
 * swap rather than a stack of `dark:` variants.
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
 * Brand column shown beside the sign-in form from `lg` up. Four blocks read top
 * to bottom — name, slogan, one-line pitch, then the feature cards and the two
 * floating badges — so the page has something to say before anyone signs in.
 */
export function LoginHero() {
  const { t } = useTranslation('translation', { keyPrefix: 'login' });
  const { t: tHeader } = useTranslation('translation', { keyPrefix: 'header' });

  return (
    <section className="relative hidden min-w-0 flex-col gap-7 lg:col-span-5 lg:flex">
      {/* A single accent bloom behind the text: it gives the glass cards
          something to sit on instead of a flat canvas. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -left-24 top-1/4 -z-10 size-72 rounded-full bg-hero-glow blur-3xl"
      />

      <div className="flex flex-col gap-3">
        <h1 className="w-fit bg-gradient-to-r from-hero-title-from via-hero-title-via to-hero-title-to bg-clip-text text-3xl font-bold tracking-tight text-transparent lg:text-4xl">
          {tHeader('brandShort')}
        </h1>
        <p className="text-lg font-medium text-text-primary">
          {t('hero.slogan')}
        </p>
        <p className="max-w-[560px] text-sm leading-relaxed text-text-secondary">
          {t('hero.intro')}
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        {Features.map(({ icon: Icon, title, description }) => (
          <li
            key={title}
            className="flex items-start gap-3 rounded-xl border border-hero-card-border bg-hero-card p-4 backdrop-blur-md transition-colors duration-200 ease-in-out hover:bg-hero-card-hover"
          >
            <Icon className="mt-0.5 size-4 shrink-0 text-hero-icon" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-text-primary">
                {t(title)}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-text-secondary">
                {t(description)}
              </p>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-3">
        <span className="inline-flex items-center rounded-full border border-hero-badge-border bg-hero-badge px-3 py-1 text-xs text-hero-badge-text">
          {t('hero.badgeLatency')}
        </span>
        <span className="inline-flex items-center rounded-full border border-hero-badge-border bg-hero-badge px-3 py-1 text-xs text-hero-badge-text">
          {t('hero.badgeIsolation')}
        </span>
      </div>
    </section>
  );
}
