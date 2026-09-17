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
import { changeLanguageAsync, supportedLanguages } from '@/locales/config';
import { useTranslation } from 'react-i18next';

/**
 * 简体中文 / English switch for the sign-in page. This route renders without the
 * app header, so the switcher lives on the page itself.
 *
 * It goes through `changeLanguageAsync` rather than `i18n.changeLanguage`: that
 * is the call which fetches the bundle for the target language, so the login and
 * register copy is actually loaded instead of falling back to the preloaded
 * English bundle (or, for a language nobody preloaded, to raw keys).
 */
export function LoginLanguageToggle() {
  const { i18n } = useTranslation();
  const currentLanguage = i18n.resolvedLanguage ?? i18n.language;

  const handleChangeLanguage = (code: string) => {
    changeLanguageAsync(code);
  };

  return (
    <div className="ceramic-pill flex items-center gap-1 rounded-full p-1">
      {supportedLanguages.map(({ code, displayName }) => {
        const isActive = currentLanguage === code;

        return (
          <button
            key={code}
            type="button"
            onClick={() => handleChangeLanguage(code)}
            aria-pressed={isActive}
            className={cn(
              'rounded-full px-3 py-1 text-xs transition-colors duration-200 ease-in-out',
              isActive
                ? 'bg-accent-color font-medium text-accent-contrast'
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {displayName}
          </button>
        );
      })}
    </div>
  );
}
